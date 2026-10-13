#!/usr/bin/env python3
"""Small optional Tk quick-capture window. CLI alternative: tools/manage-vault.py capture."""
import importlib.util
from pathlib import Path

def main():
    import tkinter as tk
    from tkinter import messagebox
    root=Path(__file__).resolve().parents[2]
    spec=importlib.util.spec_from_file_location('manage',root/'tools/manage-vault.py')
    manage=importlib.util.module_from_spec(spec);spec.loader.exec_module(manage)
    window=tk.Tk();window.title('Fieldbook capture');window.geometry('520x200')
    tk.Label(window,text='Capture a thought or next action in Inbox').pack(pady=8)
    entry=tk.Text(window,height=5);entry.pack(fill='both',expand=True,padx=12);entry.focus_set()
    def save(event=None):
        try:manage.capture(root,entry.get('1.0','end').strip())
        except (ValueError,OSError) as error:messagebox.showerror('Not saved',str(error));return
        window.destroy()
    tk.Button(window,text='Save to Inbox',command=save).pack(pady=8)
    window.bind('<Control-Return>',save);window.bind('<Escape>',lambda event:window.destroy())
    window.mainloop()

if __name__=='__main__':main()
