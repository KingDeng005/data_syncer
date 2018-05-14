from Tkinter import Button, Tk, Frame, HORIZONTAL

from ttk import Progressbar
import time
import threading

class MonApp(Frame):
    def __init__(self, master=None):
        Frame.__init__(self, master)
        self.btn = Button(text='Traitement', command=self.traitement)
        self.btn.grid(row=1,column=1)
        self.progress = Progressbar(orient=HORIZONTAL,length=100,  mode='indeterminate')


    def traitement(self):
        def real_traitement():
            self.progress.grid(row=1,column=0)
            self.progress.start()
            time.sleep(5)
            self.progress.stop()
            self.progress.grid_forget()

            self.btn['state']='normal'

        self.btn['state']='disabled'
        threading.Thread(target=real_traitement).start()

if __name__ == '__main__':
    root = Tk()
    gui = MonApp(master=root)
    gui.mainloop()
