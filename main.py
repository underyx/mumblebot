# -*- coding: utf-8

import mumbleBot
import time, sys
from config import *

mumblebot = None

if __name__ == '__main__':
	print("Starting Mumble bot...")
	mumblebot = mumbleBot.mumbleBot(server, password, port, botname, channel, tokens, target)
	#thread.start_new_thread(self._pingLoop, ())
	
	mumblebot.runBot()
	
	options = {
		0 : mumblebot.stopBot,
		1 : mumblebot.popBot,
		2 : mumblebot.depopBot,
	}
	while mumblebot.running:
		try:
			action = int(input(">"))
			options[action]()
		except (SyntaxError, ValueError, NameError, KeyError):
			print("Error")
		
	