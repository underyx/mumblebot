# -*- coding: utf-8

import mumbleBot
import time, sys
from config import *

mumblebot = None

def print_numUsers():
	print("Number of users: " + str(mumblebot.getNumUsers()))
def print_waitTime():
	print("waitTime: " + str(mumblebot.waitTime))


if __name__ == '__main__':
	print("Starting Mumble bot...")
	mumblebot = mumbleBot.mumbleBot(server, password, port, botname, channel, tokens, target)

	mumblebot.runBot()

	options = {
		0 : mumblebot.stopBot,
		1 : mumblebot.popBot,
		2 : mumblebot.depopBot,
		3 : print_numUsers,
		4 : print_waitTime
	}
	while mumblebot.running:
		try:
			action = int(input(""))
		except (SyntaxError, ValueError, NameError, KeyError):
			print("Error")
		except KeyboardInterrupt:
			mumblebot.stopBot();
		else:
			if options.has_key(action):
				options[action]()

	try:
		sys.stdout.close()
	except:
		pass
	try:
		sys.stderr.close()
	except:
		pass