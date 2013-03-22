# This Python file uses the following encoding: utf-8

'''
Created on Feb 6, 2012

@author: johannes
'''

import mumbleConnection
import thread
import time
import re
import win32api, win32process, win32con
from config import *

try:
    pid = win32api.GetCurrentProcessId()
    handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
    win32process.SetPriorityClass(handle, win32process.BELOW_NORMAL_PRIORITY_CLASS)
except:
    pass

asdf = None
tokens = [unicode(token, "utf-8") for token in tokens]
print tokens

def lol():
    return "test"

if __name__ == '__main__':
    #print("lol.")
    asdf = mumbleConnection.mumbleConnection(server, password, port, botname, channel, tokens, mastername)
    asdf.connectToServer()
    asdf.addChatCallback(re.compile("."), lol)
    # this infinity loop is there for structural purposes, do not remove it!
    while asdf.running:
        time.sleep(10)
