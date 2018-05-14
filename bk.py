#!/usr/bin/env python
import os
import sys
import numpy as np
import threading
import logging
import logging.config
import argparse
import signal
import datetime
import subprocess
from GUI import GUI
from Tkinter import Tk

SLEEP       = -1
SYNCING     = 0
FINISH_SYNC = 1
WARN_SYNC   = 2

OM_BAGS_PATH = os.path.join(os.path.expanduser("~"), 'octopus_manager', 'bags')
DEV_PRE      = 'Yuan'

class data_syncer:
    _logger = logging.getLogger('data_syncer')
    def __init__(self, args=None):
        self.bag_list  = []
        self.ssd_model = None
        self.hostname  = os.uname()[1]
        
        # GUI interface
        #self.root = Tk()
        #self.root.title('TuSimple Data Syncer')
        #self.root.geometry('550x300')
        #self.gui = GUI(master=self.root)

        # threading
        #self.check_ssd_thread = threading.Thread(target=self.search_ssd)
        #self.check_ssd_thread.start()
        #self.gui.start_button_set(self.start_sync)
        #self.gui.mainloop()

    # this will check if any valid ssd is connected
    @staticmethod
    def search_ssd(f):
        #data_syncer._logger.info('checking ssd')
        dev_path = os.path.join('/media', os.environ.get('USER'))
        dev_name = None
        try:
            devs = os.listdir(dev_path)
            for dev in devs:
                if DEV_PRE in dev:
                    dev_name = dev
            if dev_name:
                f = dev_name 
            else:
                f = 'No SSD found'
        except OSError:
            data_syncer._logger.error('Unable to list dir: {}'.format(dev_path))
            f = 'No SSD found'

    # check if bag is valid: more than bag_num_thres
    @staticmethod
    def check_valid_bag(folder):
        try:
            items = os.listdir(folder)
        except OSError:
            data_syncer._logger.error('Unable to open file: {}'.format(folder))
            return False
        bag_num = 0
        for item in items:
            if item.endswith('.bag'):
                bag_num += 1
        if bag_num >= bag_num_thres:
            return True 
        else:
            return False 

    # add to bag list 
    def add_date_list(self, start_date, end_date):
        try:
            dates = os.listdir(OM_BAGS_PATH)
            for date in dates:
                if date < start_date or date > end_date:
                    continue
                self.bag_list[date] = [] 
                bag_folders = os.listdir(os.path.join(OM_BAGS_PATH, date))
                for f in bag_folders:
                    if self.check_valid_bag(f):
                        self.bag_list[date].append(f)
        except OSError as e:
            data_syncer._logger.error('Unable to open files')

    # checking if to sycn data
    @staticmethod
    def check_condition(ssd_status, sync_status):
        # fetch ssd device
        if ssd_status != 'No SSD found':
            sync_status = 'Unable to sync because no device found'
            return False
        # fetch dates
        start_date = self.gui.start_txt_get() 
        end_date   = self.gui.end_txt_get()
        if start_date == '' or end_date == '':
            sync_status = 'Please fill out the dates'
            return False
        elif start_date > end_date:
            sync_status = 'start date can\'t be later than end date'
            return False
        else:
            self.add_date_list(start_date, end_date)
            if self.bag_list is None:
                sync_status = 'No bag is between these dates'
                return False
            else:
                return True

    # start syncing date if condition is met
    def start_sync(self, ssd_status, sync_status):
        if not self.check_condition(ssd_status):
            return
        for key, f_list in self.bag_list.iteritems():
            for f in f_list: 
                sync_status = 'syncing ' + f
                cmd = ['rsync', '--progress', '-r']
                cmd.append(os.path.join(OM_BAGS_PATH, key, f))
                cmd.append(os.path.join('/media', self.hostname, self.ssd_model, 'import'))
                proc = subprocess.Popen(cmd) 
                proc.communicate()
                if proc.returncode != 0:
                    data_syncer._logger.info('rsync process error code: {}'.format(proc.returncode))

    # check dest result right
    def check_sync_result(self):
        return

    # deal with exception
    def exit(self):
        return


if __name__ == "__main__":
    _ = data_syncer()
