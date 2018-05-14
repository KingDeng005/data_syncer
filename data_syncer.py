#!/usr/bin/env python
# created by Fuheng Deng on 05/10/2018
import os
import sys
import threading
import subprocess
import datetime
from Tkinter import *
from ttk import Progressbar 
import threading

OM_BAGS_PATH = os.path.join(os.path.expanduser("~"), 'octopus_manager', 'bags')
DEV_PRE = 'Yuan'
NETWORK_IP = '10.162.1.4'
MOUNT_POINT = '/mnt/truenas/scratch'

# timer frequency
UPDATE_FREQ = 300
USB_FREQ    = 500
NET_FREQ    = 2000 

# state
SYNC_NOT_READY = 0 
SYNC_READY = 1 
SYNCING = 2 

class data_syncer:
    
    def __init__(self):
        self.bag_list = {} 
        self.bag_num_thres = 5
        self.usb_model = None
        self.user = os.environ.get('USER')
        self._lock = threading.Lock() 
        self.sync_proc = None
        self.status = SYNC_NOT_READY

        # GUI interface
        self.root = Tk()
        self.frame = Frame(self.root)
        self.root.title('TuSimple Data Syncer')
        self.root.geometry('500x300')
        self.usb_status = ''
        self.net_status = ''
        self.sync_status = ''
        self.create_layout()
        self.gui_update()
        self.search_usb_update()
        self.search_net_update()
        self.root.mainloop()
        
    def create_layout(self):
        # usb label 
        usb_lbl = Label(text='usb status:')
        usb_lbl.grid(column=1, row=0)

        # usb status label
        self.usb_status_lbl = Label(text=self.usb_status)
        self.usb_status_lbl.grid(column=2, row=1)

        # network label 
        net_lbl = Label(text='network status:')
        net_lbl.grid(column=1, row=2)

        # network status label
        self.net_status_lbl = Label(text=self.net_status)
        self.net_status_lbl.grid(column=2, row=3)

        # start date label
        start_lbl = Label(text='start date:')
        start_lbl.grid(column=1, row=5)
        
        # start date text
        self.start_txt = Entry(width=12) 
        self.start_txt.grid(column=2, row=6)
        
        # end date label
        end_lbl = Label(text='end date:')
        end_lbl.grid(column=1, row=7)
        
        # end date text
        self.end_txt = Entry(width=12) 
        self.end_txt.grid(column=2, row=8)

        # start button
        self.usb_button = Button(text='USB sync', command= lambda: self.start_button_click('USB'))
        self.usb_button.grid(column=1, row=10) 

        # stop button
        self.stop_button = Button(text='stop sync', command= lambda: self.stop_button_click())
        self.stop_button.grid(column=2, row=10) 

        # start button
        self.net_button = Button(text='Net sync', command= lambda: self.start_button_click('Net'))
        self.net_button.grid(column=1, row=11) 

        # sync status label
        self.sync_status_lbl = Label(text=self.sync_status)
        self.sync_status_lbl.grid(column=2, row=11)

        # progress bar
        self.prog_bar = Progressbar(orient=HORIZONTAL, mode='indeterminate')
        
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

    def search_usb_update(self):
        self.root.after(USB_FREQ, self.search_usb)

    def search_net_update(self):
        self.root.after(NET_FREQ, self.search_net)
 
    def gui_update(self):
        self.root.after(UPDATE_FREQ, self.update)

    def start_button_click(self, sync_type):
        if self.get_status() == SYNCING:
            self.sync_status_set('Unable to sync: syncing in progress')  
            return
        t = threading.Thread(target=self.start_sync, args=(sync_type,))
        t.start()

    def stop_button_click(self):
        if self.get_status() != SYNCING:
            self.sync_status_set('Unable to stop: No syncing in progress')
            return
        t = threading.Thread(target=self.stop_sync)
        t.start()

    def update(self):
        self.usb_status_config(self.usb_status)
        self.net_status_config(self.net_status)
        self.sync_status_config(self.sync_status)
        self.gui_update()

    # check if usb is availble
    def search_usb(self):
        dev_path = os.path.join('/media', self.user)
        dev_name = None
        try:
            devs = os.listdir(dev_path)
            for dev in devs:
                if DEV_PRE in dev:
                    dev_name = dev
            if dev_name:
                self.usb_status = 'USB detected: {}'.format(dev)
            else:
                self.usb_status = 'No USB found'
            self.usb_model = dev_name
            if self.get_status() != SYNCING:
                self.search_usb_update()
        except OSError:
            self.usb_status = 'No USB found'
            self.usb_model = None
            
    # search if network is available
    def search_net(self):
        try:
            res = os.system("ping -c 1 " + NETWORK_IP + ' > /dev/null 2>&1')
            if res == 0:
                if os.path.ismount(MOUNT_POINT):
                    self.net_status = 'Network is ready for sync'
                else:
                    self.net_status = 'Mount point unfound'
            else:
                self.net_status = 'Network is unreachable'
            if self.get_status() != SYNCING:
                self.search_net_update()
        except OSError:
            print 'Unable to check the network availability'

    # check if a bag is valid
    def check_valid_bag(self, folder):
        try:
            items = os.listdir(folder)
        except OSError:
            print 'Unable to open file: {}'.format(folder)
            return False
        bag_num = 0
        for item in items:
            if item.endswith('.bag'):
                bag_num += 1
        if bag_num >= self.bag_num_thres:
            return True
        else:
            return False

    # add to bag list 
    def add_bag_list(self, start_date, end_date):
        # empty the bag
        self.bag_list = {}
        # adding into bag list
        try:
            dates = os.listdir(OM_BAGS_PATH)
            for date in dates:
                if date < start_date or date > end_date:
                    continue
                self.bag_list[date] = []
                bag_folders = os.listdir(os.path.join(OM_BAGS_PATH, date))
                for f in bag_folders:
                    f_path = os.path.join(OM_BAGS_PATH, date, f)
                    if self.check_valid_bag(f_path):
                        self.bag_list[date].append(f)
                if len(self.bag_list[date]) == 0:
                    del(self.bag_list[date])
        except OSError as e:
            print 'Unable to open files when adding to bag list'

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
            return False
        return True

   # check if date is met for sync
    def check_date_condition(self):
        start_date = self.start_date_get()
        end_date = self.end_date_get()
        prompt = 'Unable to sync: '
        if start_date == '' or end_date == '':
            self.sync_status_set(prompt + 'dates null')
            return False
        elif not self.check_date_format(start_date) or not self.check_date_format(end_date):
            self.sync_status_set(prompt + 'format should be YYYY-MM-DD')
            return False
        elif start_date > end_date:
            self.sync_status_set(prompt + 'Start date later than end date')
            return False
        else:
            self.add_bag_list(start_date, end_date)
            if len(self.bag_list) == 0:
                self.sync_status_set(prompt + 'No bag between these dates')
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
        
        # generate dist path
        if sync_type == 'USB':
            sync_dst = os.path.join('/media', self.user, self.usb_model, 'import')
        else:
            sync_dst = os.path.join(MOUNT_POINT, 'data_collection')
        try:
            folders = os.listdir(sync_dst)
        except OSError:
            print 'Unable to open file: {}'.format(sync_dst)
            return

        # start to sync bag one by one
        self.set_status(SYNCING)
        for key, f_list in self.bag_list.iteritems():
            if key not in folders:
                try:
                    os.mkdir(os.path.join(sync_dst, key))
                except OSError:
                    self.set_status(SYNC_READY)
                    print 'Unable to create {} under {}'.format(key, sync_dst)
                    return
            for f in f_list:
                if self.get_status() == SYNCING: 
                    self.sync_status_set('Syncing: ' + f)
                    cmd = ['rsync', '--progress', '-r']
                    cmd.append(os.path.join(OM_BAGS_PATH, key, f))
                    cmd.append(os.path.join(sync_dst, key))
                    self.sync_proc = subprocess.Popen(cmd)
                    self.sync_proc.communicate()
                    if self.sync_proc.returncode not in [0, 20]:
                        print 'rsync progress error code: {}'.format(self.sync_proc.returncode)
                        self.sync_status_set('Syncing progress error code: {}'.format(self.sync_proc.returncode))

        # post deletion
        self.post_delete(sync_dst)

        # reset status 
        if self.get_status() == SYNCING:
            self.set_status(SYNC_NOT_READY)
            self.sync_status_set(sync_type + ' sync completed')
            self.search_usb_update()
            self.search_net_update()

    # stop syncing
    def stop_sync(self):
        if self.sync_proc != None and self.sync_proc.poll() == None:
            self.sync_proc.terminate()
            self.set_status(SYNC_NOT_READY)
            self.sync_proc.communicate()
            if self.sync_proc.returncode in [0, 20]:
                self.sync_status_set('stop success')
            self.search_usb_update()
            self.search_net_update()
             
    # post-delete the .active bag 
    # TO-DO: include post check
    def post_delete(self, sync_dst):
        for key, bag_folder in self.bag_list.iteritems():
            for f in bag_folder:
                try:
                    path = os.path.join(sync_dst, key, f)
                    items = os.listdir(path)
                except OSError:
                    pass
                for item in items:
                    if item.endswith('.active'):
                        try:
                            path = os.path.join(path, item)
                            os.remove(path)
                        except OSError:
                            pass
        

if __name__ == "__main__":
    _ = data_syncer()
