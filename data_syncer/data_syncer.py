#!/usr/bin/env python
# created by Fuheng Deng on 05/10/2018
import os
import sys
import threading
import subprocess
import datetime
from Tkinter import *
from ttk import Progressbar, Style
import tkFont
import threading
import shutil
import logging
import logging.config
from dataset_store import Dataset
import time
import math

logging.config.fileConfig(os.path.join(os.path.expanduser("~"), '.data_syncer', 'ds_config.ini' ), disable_existing_loggers=False)
SYNC_SRC = os.path.join(os.path.expanduser("~"), 'octopus_manager', 'bags')
DEV_PRE = 'infra-az'
NETWORK_IP = '10.162.1.4'
DATASET_MOUNT_POINT = '/mnt/truenas/datasets/v2'
BAG_MOUNT_POINT = '/mnt/truenas/scratch'
USER = os.environ.get('USER')

# timer frequency
UPDATE_FREQ = 300
USB_FREQ    = 500
NET_FREQ    = 2000 
PROG_FREQ   = 2000

# state
SYNC_NOT_READY = 0 
SYNC_READY = 1 
SYNCING = 2 
EXIT = 3

class DataSyncer:
    _logger = logging.getLogger('DataSyncer')    
    def __init__(self):
        self.root = Tk()
        self.file_list = {}
        self.bag_num_thres = 5
        self.file_size = 0
        self.finish_size = 0
        self.usb_model = None
        self._lock = threading.Lock() 
        self.sync_proc = None
        self.sync_thread = None
        self.stop_thread = None
        self.status = SYNC_NOT_READY
        self.sync_dst_bag = ''
        self.sync_dst_dataset = ''
        self.usb_status = ''
        self.net_status = ''
        self.sync_status = ''
        self.cur_time = 0 

        # GUI interface
        self.frame = Frame(self.root)
        self.root.title('TuSimple Data Syncer')
        self.root.geometry('500x700')
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        self.style = Style(self.root)
        self.style.layout('text.Horizontal.TProgressbar',
                     [('Horizontal.Progessbar.trough',
                         {'children': [('Horizontal.Progressbar.pbar',
                                        {'side':'left', 'sticky':'ns'})],
                          'sticky': 'nswe'}),
                         ('Horizontal.Progressbar.label', {'side':'right', 'sticky':''})])
        self.font_size = tkFont.Font(family='Times New Roman', size=15)
        self.create_layout()
        self.gui_update()
        self.search_usb_update()
        self.search_net_update()
        DataSyncer._logger.info('GUI layout created')
        self.root.mainloop()
        
    def create_layout(self):
        # usb label 
        usb_lbl = Label(text='usb status:', height=4, width=20, font=self.font_size)
        usb_lbl.grid(column=0, row=0)

        # usb status label
        self.usb_status_lbl = Label(text=self.usb_status, height=4, width=20, font=self.font_size)
        self.usb_status_lbl.grid(column=1, row=0)

        # network label 
        net_lbl = Label(text='network status:', height=4, width=20, font=self.font_size)
        net_lbl.grid(column=0, row=1)

        # network status label
        self.net_status_lbl = Label(text=self.net_status, height=4, font=self.font_size)
        self.net_status_lbl.grid(column=1, row=1)

        # start date label
        start_lbl = Label(text='start date:', height=4, font=self.font_size)
        start_lbl.grid(column=0, row=2)
        
        # start date text
        self.start_txt = Entry(width=25, font=self.font_size) 
        self.start_txt.grid(column=1, row=2)
        
        # end date label
        end_lbl = Label(text='end date:', height=4, font=self.font_size)
        end_lbl.grid(column=0, row=3)
        
        # end date text
        self.end_txt = Entry(width=25, font=self.font_size) 
        self.end_txt.grid(column=1, row=3)

        # start button
        self.usb_button = Button(text='USB sync', height=3,  command= lambda: self.start_button_click('USB'), font=self.font_size)
        self.usb_button.grid(column=0, row=4, sticky=N+S+E+W) 

        # stop button
        self.stop_button = Button(text='stop sync', height=3, command= lambda: self.stop_button_click(), font=self.font_size)
        self.stop_button.grid(column=1, row=4, sticky=N+S+E+W) 

        # start button
        self.net_button = Button(text='Net sync', height=3, command= lambda: self.start_button_click('Net'), font=self.font_size)
        self.net_button.grid(column=0, row=5, sticky=N+S+E+W) 
        
        # start button
        self.exit_button = Button(text='exit', height=3, command=self.exit, font=self.font_size)
        self.exit_button.grid(column=1, row=5, sticky=N+S+E+W) 

        # sync status label
        self.sync_status_lbl = Label(text=self.sync_status, width=50, height=4, font=self.font_size)
        self.sync_status_lbl.grid(column=0, row=6, columnspan=2)

        # progress bar
        self.progressbar = Progressbar(orient='horizontal', length=240, mode='determinate', style='text.Horizontal.TProgressbar')

        # time estimator
        self.time_est = Label(height=3, font=self.font_size)
        
    def usb_status_set(self, text):
        self.usb_status = text

    def net_status_set(self, text):
        self.net_status = text

    def sync_status_set(self, text):
        self.sync_status = text

    def usb_status_config(self, text):
        self.usb_status_lbl.configure(text=text)

    def net_status_config(self, text):
        self.net_status_lbl.configure(text=text)

    def sync_status_config(self, text):
        self.sync_status_lbl.configure(text=text)

    def prog_status_config(self, val, maximum, text):
        self.progressbar.configure(value=val, maximum=maximum)
        self.style.configure('text.Horizontal.TProgressbar',
                             text=text)

    def start_date_get(self):
        return self.start_txt.get() 
    
    def end_date_get(self):
        return self.end_txt.get() 

    def set_status(self, status):
        with self._lock:
            self.status = status

    def get_status(self):
        with self._lock:
            return self.status

    def forget_progressbar(self):
        self.cur_time = 0 
        self.finish_size = 0 
        if len(self.progressbar.grid_info()) != 0:
            self.progressbar.grid_forget()
        if len(self.time_est.grid_info()) != 0:
            self.time_est.grid_forget()

    def search_usb_update(self):
        self.root.after(USB_FREQ, self.search_usb)

    def search_net_update(self):
        self.root.after(NET_FREQ, self.search_net)
 
    def gui_update(self):
        self.root.after(UPDATE_FREQ, self.status_update)

    def progressbar_update(self):
        self.root.after(PROG_FREQ, self.progressbar_calculator)

    def progressbar_calculator(self):
        if self.get_status() == SYNCING:
            self.progressbar.grid(column=0, row=12, columnspan=2)
            self.time_est.grid(column=0, row=13, columnspan=2)
            finish_size = 0
            for key, folders in self.file_list.iteritems():
                if 'bag' in self.file_list[key].values():
                    path = os.path.join(self.sync_dst_bag, key)
                    if os.path.exists(path):
                        try:
                            finish_size += self.get_size(path)
                        except OSError:
                            DataSyncer._logger.error('Unable to get size at {}'.format(path))
                for data_folder, data_type in folders.iteritems():
                    if data_type == 'dataset':
                        path = os.path.join(self.sync_dst_dataset, data_folder)
                        if os.path.exists(path):
                            try:
                                finish_size += self.get_size(path)
                            except OSError:
                                DataSyncer._logger.error('Unable to get size at {}'.format(path))
            # calculate percent
            val = finish_size * 1. / self.file_size * 100
            maximum = 100 
            self.prog_status_config(val, maximum, '{}/{}'.format(int(val), maximum))
            # calculate speed and estimated time
            if self.cur_time == 0:
                self.cur_time = time.time()
            else:
                t_diff = time.time() - self.cur_time 
                self.cur_time = time.time()
                s_diff = finish_size - self.finish_size
                self.finish_size = finish_size
                # speed in MB/s, t_diff in KB, needs to divide by 1024, time left in min
                sync_speed = s_diff * 1. / t_diff if t_diff != 0 else 0 
                time_left = int(math.ceil((self.file_size - self.finish_size) * 1. / sync_speed / 60) if sync_speed != 0 else 0) 
                self.time_est.configure(text='Sync speed: {:.1f}MB/s, Estimate: {}min'.format(sync_speed/1024, time_left))
            self.progressbar_update()

    def start_button_click(self, sync_type):
        if self.get_status() == SYNCING or (self.sync_thread != None and self.sync_thread.isAlive()):
            self.sync_status_set('Unable to sync: syncing in progress')  
            DataSyncer._logger.warn('Unable to sync: syncing in progress')
            return
        self.sync_thread = threading.Thread(target=self.start_sync, args=(sync_type,))
        self.sync_thread.start()

    def stop_button_click(self):
        '''
        if self.stop_thread != None and self.stop_thread.isAlive(): 
            self.sync_status_set('Unable to stop: stopping now')
            DataSyncer._logger.warn('Unable to sync: stopping now')
            return
        '''
        if self.get_status() != SYNCING:
            self.sync_status_set('Unable to stop: no syncing in progress')
            DataSyncer._logger.warn('Unable to sync: no syncing in progress')
            return
        self.stop_thread = threading.Thread(target=self.stop_sync)
        self.stop_thread.start()

    def status_update(self):
        self.usb_status_config(self.usb_status)
        self.net_status_config(self.net_status)
        self.sync_status_config(self.sync_status)
        self.gui_update()
        '''
        if self.sync_thread != None and self.sync_thread.isAlive() and self.get_status() in [SYNC_NOT_READY, SYNC_STOPPING]:
            self.sync_thread.join()
            DataSyncer._logger.info('sync thread joined!')
        if self.stop_thread != None and self.stop_thread.isAlive() and self.get_status() in [SYNC_NOT_READY]:
            self.stop_thread.join()
            DataSyncer._logger.info('stop thread joined!')
        '''

    # check if usb is availble
    def search_usb(self):
        dev_path = os.path.join('/media', USER)
        dev_name = None
        try:
            devs = os.listdir(dev_path)
            for dev in devs:
                _dev = dev.lower()
                if DEV_PRE.lower() in _dev:
                    dev_name = dev
            if dev_name:
                self.usb_status = dev 
            else:
                self.usb_status = 'No USB found'
            self.usb_model = dev_name
            if self.get_status() != SYNCING:
                self.search_usb_update()
        except OSError:
            self.usb_status = '{} USB not found'.format(DEV_PRE)
            self.usb_model = None
            
    # search if network is available
    def search_net(self):
        try:
            res = os.system("ping -c 1 " + NETWORK_IP + '> /dev/null 2>&1')
            if res == 0:
                if os.path.ismount(BAG_MOUNT_POINT):
                    self.net_status = 'Network is ready for sync'
                else:
                    self.net_status = 'Mount point unfound'
            else:
                self.net_status = 'Network is unreachable'
            if self.get_status() != SYNCING:
                self.search_net_update()
        except OSError:
            print('Unable to check the network availability')

    # check file list
    def check_file_type(self, path):
        items = os.listdir(path)
        if 'top.json' in items:
            return 'dataset'
        elif 'record.json' in items or 'log' in items:
            return 'bag'
        else:
            return None
        
    # count how many bags one folder has 
    def count_bag(self, folder):
        try:
            items = os.listdir(folder)
        except OSError:
            DataSyncer._logger.error('Unable to open file: {}'.format(folder))
            return False
        bag_num = 0
        for item in items:
            if item.endswith('.bag'):
                bag_num += 1
        return bag_num

    # add to bag list 
    def add_file_list(self, start_date, end_date):
        # empty the file list 
        self.file_list = {}
        self.file_size = 0
        # adding into file list
        try:
            dates = os.listdir(SYNC_SRC)
            for date in dates:
                if date < start_date or date > end_date:
                    continue
                self.file_list[date] = {} 
                path = os.path.join(SYNC_SRC, date)
                self.file_size += self.get_size(path)
                bag_folders = os.listdir(path) 
                for f in bag_folders:
                    f_path = os.path.join(SYNC_SRC, date, f)
                    file_type = self.check_file_type(f_path)
                    if file_type == 'dataset':
                        ds = Dataset(f_path)
                        _t = (ds.meta['ts_end'] - ds.meta['ts_begin']) * 1. / 1e9 / 60
                        if _t > self.bag_num_thres * 5:
                            self.file_list[date][f] = 'dataset'
                    elif file_type == 'bag':
                        bag_num = self.count_bag(f_path)
                        if bag_num >= self.bag_num_thres:
                            self.file_list[date][f] = 'bag'
                    else:
                        DataSyncer._logger.warn('{} is not a data folder'.format(f_path))
                if len(self.file_list[date]) == 0:
                    del(self.file_list[date])
        except OSError as e:
            DataSyncer._logger.error('Unable to open files when adding to bag list')

    # check user input format
    @staticmethod 
    def check_date_format(date_text):
        try:
            datetime.datetime.strptime(date_text, '%Y-%m-%d')
            return True
        except ValueError:
            return False

    # check if usb condition is met for sync
    def check_dst_condition(self, sync_type):
        condition = self.usb_model if sync_type == 'USB' else self.net_status
        if not condition:
            self.sync_status_set('Unable to sync: {} is not avaible'.format(sync_type))
            DataSyncer._logger.error('Unable to sync: {} is not avaible'.format(sync_type))
            return False
        return True

   # check if date is met for sync
    def check_date_condition(self):
        start_date = self.start_date_get()
        end_date = self.end_date_get()
        prompt = 'Unable to sync: '
        if start_date == '' or end_date == '':
            self.sync_status_set(prompt + 'dates null')
            DataSyncer._logger.error(prompt + 'dates null')
            return False
        elif not self.check_date_format(start_date) or not self.check_date_format(end_date):
            self.sync_status_set(prompt + 'format should be YYYY-MM-DD')
            DataSyncer._logger.error(prompt + 'format should be YYYY-MM-DD')
            return False
        elif start_date > end_date:
            self.sync_status_set(prompt + 'start date later than end date')
            DataSyncer._logger.error(prompt + 'start date later than end date')
            return False
        else:
            self.add_file_list(start_date, end_date)
            if len(self.file_list) == 0:
                self.sync_status_set(prompt + 'no bag between these dates')
                DataSyncer._logger.error(prompt + 'no bag between these dates')
                return False
            else:
                return True

    # check both conditions
    def check_sync_condition(self, sync_type):
        if self.check_dst_condition(sync_type) and self.check_date_condition():
            self.set_status(SYNC_READY)
        else:
            self.set_status(SYNC_NOT_READY)
        
    # start syncing
    def start_sync(self, sync_type):
        # check destination
        self.check_sync_condition(sync_type)
        if self.get_status() == SYNC_NOT_READY:
            return
        
        self.set_status(SYNCING)
        # generate dist path
        if sync_type == 'USB':
            self.sync_dst_bag = self.sync_dst_dataset = os.path.join('/media', USER, self.usb_model, 'import')
        else:
            self.sync_dst_bag = os.path.join(BAG_MOUNT_POINT, 'data_collection')
            self.sync_dst_dataset = DATASET_MOUNT_POINT
        try:
            folders = os.listdir(self.sync_dst_bag)
        except OSError:
            self.sync_status_set('No such path: {}'.format(self.sync_dst_bag))
            DataSyncer._logger.error('Unable to open file: {}'.format(self.sync_dst_bag))
            return

        # sanity check
        self.sync_status_set('Sanity check...please wait')
        self.sanity_check()
        DataSyncer._logger.info('Sanity check finished')
        self.progressbar_update()

        # start to sync bag one by one
        for key, f_list in self.file_list.iteritems():
            if key not in folders and 'bag' in f_list.values():
                try:
                    os.mkdir(os.path.join(self.sync_dst_bag, key))
                except OSError:
                    self.set_status(SYNC_NOT_READY)
                    DataSyncer._logger.error('Unable to create {} under {}'.format(key, self.sync_dst_bag))
                    return
            for f in f_list.keys():
                if self.get_status() == SYNCING: 
                    self.sync_status_set('Syncing: ' + f)
                    cmd = ['rsync', '--progress', '-r', '--append']
                    cmd.append(os.path.join(SYNC_SRC, key, f))
                    sync_dst = os.path.join(self.sync_dst_bag, key) if f_list[f] == 'bag' else self.sync_dst_dataset
                    cmd.append(sync_dst)
                    self.sync_proc = subprocess.Popen(cmd)
                    self.sync_proc.communicate()
                    if self.sync_proc.returncode not in [0, 20]:
                        self.sync_status_set('Syncing progress error code: {}'.format(self.sync_proc.returncode))
                        DataSyncer._logger.error('rsync progress error code: {}'.format(self.sync_proc.returncode))

        if self.get_status() == EXIT:
            DataSyncer._logger.info('exiting...')
            return

        # reset status 
        if self.get_status() == SYNCING:
            self.set_status(SYNC_NOT_READY)
            if self.sync_proc.returncode == 0:
                self.sync_status_set(sync_type + ' sync completed')
                DataSyncer._logger.info(sync_type + ' sync completed')

        # post deletion
        self.post_delete()
        # restart update
        self.search_usb_update()
        self.search_net_update()
        # forget progressbar and its related speed/time estimator
        self.forget_progressbar()
        DataSyncer._logger.info('syncing thread finished')

    # stop syncing
    def stop_sync(self):
        if self.sync_proc != None and self.sync_proc.poll() == None:
            DataSyncer._logger.info('start stopping')
            self.sync_proc.terminate()
            if self.get_status() != EXIT:
                self.set_status(SYNC_NOT_READY)
            self.sync_proc.communicate()
            DataSyncer._logger.info('returncode is: {}'.format(self.sync_proc.returncode))
            if self.sync_proc.returncode in [0, 20]:
                self.sync_status_set('stop success')
            DataSyncer._logger.info('stop syncing thread finished')

    # sanity check before syncing to avoid - matching the use of rsync --append
    def sanity_check(self):
        for key, bag_folder in self.file_list.iteritems():
            for f in bag_folder.keys():
                try:
                    # assumption: all files in destination must be included by those in source
                    sync_dst = os.path.join(self.sync_dst_bag, key, f) if bag_folder[f] == 'bag' else os.path.join(self.sync_dst_dataset, f)
                    items = os.listdir(sync_dst)
                    for item in items:
                        src_path = os.path.join(SYNC_SRC, key, f, item)
                        dst_path = os.path.join(sync_dst, item)
                        if os.path.isfile(dst_path):
                            s_size = self.get_file_size(src_path)
                            d_size = self.get_file_size(dst_path)
                        else:
                            s_size = self.get_dir_size(src_path)
                            d_size = self.get_dir_size(dst_path)
                        if s_size != d_size:
                            try:
                                os.remove(dst_path)
                            except OSError:
                                shutil.rmtree(dst_path)
                            finally:
                                DataSyncer._logger.warn('removed {}'.format(dst_path))
                except OSError:
                    DataSyncer._logger.error('Unable to do OS operation in Sanity check')
             
    # post-delete the .active bag 
    # TO-DO: include post check
    def post_delete(self):
        for key, bag_folder in self.file_list.iteritems():
            for f in bag_folder.keys():
                try:
                    if bag_folder[f] == 'bag':
                        path = os.path.join(self.sync_dst_bag, key, f)
                        items = os.listdir(path)
                        for item in items:
                            if item.endswith('.active'):
                                path = os.path.join(path, item)
                                os.remove(path)
                except OSError:
                    DataSyncer._logger.error('Unable to do OS operation in post delete')

    # wait threads finish
    def wait_thread(self):
        while True:
            if (self.sync_thread != None and self.sync_thread.isAlive()) or (self.stop_thread != None and self.stop_thread.isAlive()):
                time.sleep(0.5)
                continue
            else:
                break

    # close window exit
    def exit(self):
        self.set_status(EXIT)
        self.stop_sync()
        time.sleep(0.5)
        self.root.destroy()
        sys.exit(0)

    # get folder size in KB in general
    def get_size(self, path):
        return int(subprocess.check_output(['du', '-s', path]).split()[0])

    # calculate file's logical size
    def get_file_size(self, path):
        return int(subprocess.check_output(['ls', '-l', path]).split()[4])

    # calculate folde'r logical size
    def get_dir_size(self, path):
        size = 0
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            size += self.get_file_size(item_path) if os.path.isfile(item_path) else self.get_dir_size(item_path)
        return int(size)

def main():
    try:
        ds = DataSyncer()
    except KeyboardInterrupt:
        print('Program interrupted')
        ds.exit() 

if __name__ == "__main__":
    main()
