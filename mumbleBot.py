# -*- coding: utf-8

import mumbleConnection, mumblePing
import thread
import time
import re

class mumbleBot():
	serverQuery = None
	running = True
	stopping = False
	next_bot_id = 0
	numBot = 0

	server = None
	password = None
	port = 0
	botname = None
	channel = None
	tokens = None

	target = 3

	waitTime = 30

	_bots = {}

	def __init__(self, server, password, port, botname, channel, tokens, target):
		self.server = server
		self.port = port
		self.botname = botname
		self.channel = channel
		self.tokens = tokens
		self.password = password
		self.target = target
		self.numBot = 0
		self.running = True
		self.serverQuery = mumblePing.mumblePing(server, port)

		for bot_id in range(0, self.target):
			self._bots[bot_id] = None

	def runBot(self):
		thread.start_new_thread(self._pingLoop, ())

	def stopBot(self):
		self.stopping = True
		for bot_id in range(0, self.target):
			if (self._bots[bot_id] is not None):
				if self._bots[bot_id].isRunning():
					self._bots[bot_id].disconnect()
		self.running = False

	def recountBots(self):
		count = 0
		self.next_bot_id = -1
		for bot_id in range(0, self.target):
			if (self._bots[bot_id] is not None):
				if self._bots[bot_id].isRunning():
					count += 1
				else:
					if(self.next_bot_id == -1):
						self.next_bot_id = bot_id
			else:
				if(self.next_bot_id == -1):
					self.next_bot_id = bot_id
		self.numBot = count

	def getNumUsers(self):
		for bot_id in range(0, self.target):
			if (self._bots[bot_id] is not None):
				if self._bots[bot_id].isRunning():
					return self._bots[bot_id].getNumUsers()
		self.serverQuery._doPing()
		return self.serverQuery.getNumUsers()

	def onBotDie(self, bot_id):
		if not self.stopping:
			self.recountBots()
			
	def onBotConnect(self, bot_id):
		self.waitTime = 30

	def onConnectionRefused(self, bot_id):
		print("Extending waitTime to 320 seconds")
		self.waitTime = 320

	def _pingLoop(self):
		while(self.running and not self.stopping):
			self.recountBots()

			if(self.getNumUsers() < self.target):
				self.popBot()
			else:
				if(self.getNumUsers() > self.target):
					self.depopBot()

			time.sleep(self.waitTime)

	def popBot(self):
		if self.next_bot_id == -1:
			print("Cannot create new bot, no space left")
			return
		bot = mumbleConnection.mumbleConnection(self.numBot, self.server, self.password, self.port, self.botname+str(self.numBot+1), self.channel, self.tokens)
		bot.addBotDieHandler(self.onBotDie)
		bot.addBotConnectHandler(self.onBotConnect)
		bot.addConnectionRefusedHandler(self.onConnectionRefused)
		bot.connectToServer()
		
		self._bots[self.next_bot_id] = bot
		self.recountBots()

	def depopBotbyId(self, id):
		if(id >= 0 and id < self.numBot):
			self._bots[id].disconnect()
		self.recountBots()

	def depopBot(self):
		self.depopBotbyId(self.numBot-1)