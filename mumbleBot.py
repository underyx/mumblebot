# -*- coding: utf-8

import mumbleConnection, mumblePing
import thread
import time
import re

class mumbleBot():
	serverQuery = None
	running = True
	stopping = False
	numBot = 0

	server = None
	password = None
	port = 0
	botname = None
	channel = None
	tokens = None
	
	target = 3
	
	_bots = []

	def __init__(self, server, password, port, botname, channel, tokens):
		self.server = server
		self.port = port
		self.botname = botname
		self.channel = channel
		self.tokens = tokens
		self.password = password
		self.numBot = 0
		self.running = True
		self.serverQuery = mumblePing.mumblePing(server, port)
		
	def runBot(self):
		thread.start_new_thread(self._pingLoop, ())
		
	def stopBot(self):
		self.stopping = True
		self.depopMultipleBot(self.numBot)
		self.running = False
		
	def onBotDie(self):
		self.numBot -= 1

	def _pingLoop(self):
		while(self.running and not self.stopping):
			self.serverQuery._doPing()
			if(self.serverQuery.getNumUsers() < self.target):
				self.popBot()
				#reqbot = self.target - self.serverQuery.getNumUsers()
				#self.popMultipleBot(reqbot)
			else:
				if(self.serverQuery.getNumUsers() > self.target):
					self.depopBot()
					#reqbot = self.serverQuery.getNumUsers() - self.target
					#self.depopMultipleBot(reqbot)				
				
			time.sleep(20)

	def popMultipleBot(self, num):
		for x in range(0, num):
			self.popBot()
			time.sleep(2)
		
	def popBot(self):
		bot = mumbleConnection.mumbleConnection(self.numBot, self.server, self.password, self.port, self.botname+str(self.numBot+1), self.channel, self.tokens)
		self.numBot += 1
		self._bots.append(bot)
		bot.addBotDieHandler(self.onBotDie)
		bot.connectToServer()
	
	def depopMultipleBot(self, num):
		numBotCopy = self.numBot
		for x in range(numBotCopy-num, numBotCopy):
			self.depopBotbyId(x)
		
	def depopBotbyId(self, id):
		if(id >= 0 and id < self.numBot):
			self._bots[id].disconnect()
			
	def depopBot(self):
		self.depopBotbyId(self.numBot-1)
		