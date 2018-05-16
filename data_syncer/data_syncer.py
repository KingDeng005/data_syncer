#!/usr/bin/env python
# created by Fuheng Deng on 05/10/2018
import os
import sys
import threading
import subprocess
import datetime
from Tkinter import *
from ttk import Progressbar, Style
import threading
import shutil

SYNC_SRC = os.path.join(os.path.expanduser("~"), 'octopus_manager', 'bags')
DEV_PRE = 'AZ-Infra'
NETWORK_IP = '10.162.1.4'
MOUNT_POINT = '/mnt/truenas/scratch'

# timer frequency
UPDATE_FREQ = 300
USB_FREQ    = 500
NET_FREQ    = 2000 
PROG_FREQ   = 2000

# state
SYNC_NOT_READY = 0 
SYNC_READY = 1 
SYNCING = 2 

class data_syncer:
    
    def __init__(self):
        self.root = Tk()
        self.bag_list = {} 
        self.file_size = 0
        self.bag_num = 0
        self.bag_num_thres = 5
        self.usb_model = None
        self.user = os.environ.get('USER')
        self._lock = threading.Lock() 
        self.sync_proc = None
        self.status = SYNC_NOT_READY
        self.sync_dst = ''
        self.usb_status = ''
        self.net_status = ''
        self.sync_status = ''
        self.create_layout()
        self.gui_update()
        self.search_usb_update()
        self.search_net_update()
 
        # GUI interface
        self.frame = Frame(self.root)
        self.root.title('TuSimple Data Syncer')
        self.root.geometry('300x250')
        self.root.protocol("WM_DELETE_WINDOW", self.exit)
        self.style = Style(self.root)
        self.style.layout('text.Horizontal.TProgressbar',
                     [('Horizontal.Progessbar.trough',
                         {'children': [('Horizontal.Progressbar.pbar',
                                        {'side':'left', 'sticky':'ns'})],
                          'sticky': 'nswe'}),
                         ('Horizontal.Progressbar.label', {'side':'right', 'sticky':''})])
        self.root.mainloop()
        
    def create_layout(self):
        # usb label 
        usb_lbl = Label(text='usb status:', height=2)
        usb_lbl.grid(column=0, row=0)

        # usb status label
        self.usb_status_lbl = Label(text=self.usb_status, height=2)
        self.usb_status_lbl.grid(column=1, row=0)

        # network label 
        net_lbl = Label(text='network status:', height=2)
        net_lbl.grid(column=0, row=1)

        # network status label
        self.net_status_lbl = Label(text=self.net_status, height=2)
        self.net_status_lbl.grid(column=1, row=1)

        # start date label
        start_lbl = Label(text='start date:', height=2)
        start_lbl.grid(column=0, row=2)
        
        # start date text
        self.start_txt = Entry(width=12) 
        self.start_txt.grid(column=1, row=2)
        
        # end date label
        end_lbl = Label(text='end date:', height=2)
        end_lbl.grid(column=0, row=3)
        
        # end date text
        self.end_txt = Entry(width=12) 
        self.end_txt.grid(column=1, row=3)

        # start button
        self.usb_button = Button(text='USB sync', height=1,  command= lambda: self.start_button_click('USB'))
        self.usb_button.grid(column=0, row=4) 

        # stop button
        self.stop_button = Button(text='stop sync', height=1, command= lambda: self.stop_button_click())
        self.stop_button.grid(column=1, row=4) 

        # start button
        self.net_button = Button(text='Net sync', height=1, command= lambda: self.start_button_click('Net'))
        self.net_button.grid(column=0, row=5) 
        
        # start button
        self.exit_button = Button(text='exit', height=1, command=self.exit)
        self.exit_button.grid(column=1, row=5) 

        # sync status label
        self.sync_status_lbl = Label(text=self.sync_status, width=30)
        self.sync_status_lbl.grid(column=0, row=6, columnspan=2, rowspan=2)

        # progress bar
        self.progressbar = Progressbar(orient='horizontal', length=100, mode='determinate', style='text.Horizontal.TProgressbar')
        
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

    def search_usb_update(self):
        self.root.after(USB_FREQ, self.search_usb)

    def search_net_update(self):
        self.root.after(NET_FREQ, self.search_net)
 
    def gui_update(self):
        self.root.after(UPDATE_FREQ, self.update)

    def progressbar_update(self):
        self.root.after(PROG_FREQ, self.progressbar_calculator)

    def progressbar_calculator(self):
        if self.get_status() == SYNCING and len(self.bag_list) != 0:
            self.progressbar.grid(column=1, row=12)
            finish_bag_num = 0
            for key, bag_folder in self.bag_list.iteritems():
                for f in bag_folder:
                    path = os.path.join(self.sync_dst, key, f)
                    if os.path.exists(path):
                        finish_bag_num += len([item for item in os.listdir(path) if item.endswith('.bag')])
            val = int(finish_bag_num * 1. / self.bag_num * 100.)
            maximum = 100 
            self.prog_status_config(val, maximum, '{}/{}'.format(val, maximum))
            self.progressbar_update()

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
            res = os.system("ping -c 1 " + NETWORK_IP + '> /dev/null 2>&1')
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
            print('Unable to check the network availability')

    # count how many bags one folder has 
    def count_bag(self, folder):
        try:
            items = os.listdir(folder)
        except OSError:
            print('Unable to open file: {}'.format(folder))
            return False
        bag_num = 0
        for item in items:
            if item.endswith('.bag'):
                bag_num += 1
        return bag_num

    # add to bag list 
    def add_bag_list(self, start_date, end_date):
        # empty the bag
        self.bag_list = {}
        # adding into bag list
        try:
            dates = os.listdir(SYNC_SRC)
            for date in dates:
                if date < start_date or date > end_date:
                    continue
                self.bag_list[date] = []
                path = os.path.join(SYNC_SRC, date)
                self.file_size += os.path.getsize(path)
                bag_folders = os.listdir(path) 
                for f in bag_folders:
                    f_path = os.path.join(SYNC_SRC, date, f)
                    bag_num = self.count_bag(f_path)
                    if bag_num >= self.bag_num_thres:
                        self.bag_num += bag_num
                        self.bag_list[date].append(f)
                if len(self.bag_list[date]) == 0:
                    del(self.bag_list[date])
        except OSError as e:
            print('Unable to open files when adding to bag list')

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
            self.sync_dst = os.path.join('/media', self.user, self.usb_model, 'import')
        else:
            self.sync_dst = os.path.join(MOUNT_POINT, 'data_collection')
        try:
            folders = os.listdir(self.sync_dst)
        except OSError:
            print('Unable to open file: {}'.format(self.sync_dst))
            return

        # sanity check
        self.sanity_check()

        # start to sync bag one by one
        self.set_status(SYNCING)
        self.progressbar_update()
        for key, f_list in self.bag_list.iteritems():
            if key not in folders:
                try:
                    os.mkdir(os.path.join(self.sync_dst, key))
                except OSError:
                    self.set_status(SYNC_READY)
                    print('Unable to create {} under {}'.format(key, self.sync_dst))
                    return
            for f in f_list:
                if self.get_status() == SYNCING: 
                    self.sync_status_set('Syncing: ' + f)
                    cmd = ['rsync', '--progress', '-r', '--append']
                    cmd.append(os.path.join(SYNC_SRC, key, f))
                    cmd.append(os.path.join(self.sync_dst, key))
                    self.sync_proc = subprocess.Popen(cmd)
                    self.sync_proc.communicate()
                    if self.sync_proc.returncode not in [0, 20]:
                        print 'rsync progress error code: {}'.format(self.sync_proc.returncode)
                        self.sync_status_set('Syncing progress error code: {}'.format(self.sync_proc.returncode))

        # post deletion
        self.post_delete()
        self.progressbar.grid_forget()

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
            self.progressbar.grid_forget()
            self.sync_proc.communicate()
            if self.sync_proc.returncode in [0, 20]:
                self.sync_status_set('stop success')
            self.search_usb_update()
            self.search_net_update()

    # sanity check before syncing to avoid - matching the use of rsync --append
    def sanity_check(self):
        for key, bag_folder in self.bag_list.iteritems():
            for f in bag_folder:
                src_path = os.path.join(SYNC_SRC, key, f)
                dst_path = os.path.join(self.sync_dst, key, f)
                try:
                    # assumption: all files in destination must be included by those in source
                    items = os.listdir(dst_path)
                    for item in items:
                        s_size = os.path.getsize(os.path.join(src_path, item))
                        d_size = os.path.getsize(os.path.join(dst_path, item))
                        if s_size != d_size:
                            path = os.path.join(dst_path, item)  
                            if os.path.exists(path):
                                try:
                                    os.remove(path)
                                except OSError:
                                    shutil.rmtree(path)
                                finally:
                                    print 'removing {}'.format(path)
                            else:
                                print 'removing {} failed'.format(path)
                except OSError:
                    print 'Unable to do OS operation in Sanity check'
             
    # post-delete the .active bag 
    # TO-DO: include post check
    def post_delete(self):
        for key, bag_folder in self.bag_list.iteritems():
            for f in bag_folder:
                try:
                    path = os.path.join(self.sync_dst, key, f)
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

    # close window exit
    def exit(self):
        self.stop_sync()
        self.root.destroy()
        sys.exit(0)

def main():
    try:
        ds = data_syncer()
    except KeyboardInterrupt:
        print('Program interrupted')
        ds.exit() 

if __name__ == "__main__":
    main()
