# -*- coding: utf-8

from bots import botTypes
import mumblePing
import thread
import time
import re
import random

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



	waitTime = 15


	__botsType = {
		0 : botTypes.presenceBot,
		1 : botTypes.chatUtilityBot
		}
	__bots = {}

	__chatUtilityBots = {}
	__chatUtilityBotsCount = 0


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


		self.__bots[0] = {}
		self.__bots[1] = {}

		
		#self.__popChatUtilityBot("Chat_Utility_Bot", "Salon #1")
		#for bot_id in range(0, self.target):
		#	self._bots[bot_id] = None

	def runBot(self):
		thread.start_new_thread(self.__presenceBotsLoop, ())

	def stopBot(self):
		self.stopping = True
		
		for bot_id in self.__bots[0].keys():
			self.__depopBotByName(bot_id, 0)
			
		for bot_id in self.__bots[1].keys():
			self.__depopBotByName(bot_id, 1)
			
		self.running = False

	def getNumUsers(self):
		if self.stopping:
			return 0
		for bot in self.__bots[0].values():
			if bot is not None:
				if bot.isRunning():
					return bot.getNumUsers()
		return self.serverQuery.getNumUsers()

	def __getNextBotNumber(self):
		if self.stopping:
			return "-1"
		for i in range(1, 10):
			if not self.__bots[0].has_key(self.botname+str(i)):
				return str(i)
		return '-1'
			
	def __removeOldBots(self):
		if self.stopping:
			return
		self.__removeOldBotsByType(0)
				
	def __removeOldBotsByType(self, type):
		if self.stopping:
			return
		for (name, bot) in self.__bots[type].items():
			if (bot is not None):
				if not bot.isRunning():
					del self.__bots[type][name]
			else:
				del self.__bots[type][name]

	def ___onPresenceBotDie(self, bot_name):
		if not self.stopping:
			del self.__bots[0][bot_name]
			self.__removeOldBots()
			
	def ___onPresenceBotConnect(self, bot_name):
		self.waitTime = 15

	def __onPresenceConnectionRefused(self, bot_name):
		print("Extending waitTime to 320 seconds")
		self.waitTime = 320

	def __presenceBotsLoop(self):
		while(self.running and not self.stopping):
			self.__removeOldBots()

			if(self.getNumUsers() < self.target):
				self.__popBot(0)
			else:
				if(self.getNumUsers() > self.target):
					self.__depopBot(0)

			time.sleep(self.waitTime)

	def __popBotWithParameters(self, type, name, password, channel):
		bot = self.__botsType[type](self.server, password, self.port, name, channel, self.tokens)
		if type == 0:
			bot.addBotDieHandler(self.___onPresenceBotDie)
			bot.addBotConnectHandler(self.___onPresenceBotConnect)
			bot.addConnectionRefusedHandler(self.__onPresenceConnectionRefused)
		bot.connectToServer()
		
		self.__bots[type][name] = bot
		self.__removeOldBots()

	def __popBot(self, type):
		bot_name = self.__getNextBotNumber();
		if bot_name == "-1":
			return
		bot_name = self.botname+bot_name
		self.__popBotWithParameters(type, bot_name, self.password, self.channel)

	def __depopBotByName(self, name, type):
		if not self.__bots[type].has_key(name):
			return
		if self.__bots[type][name] is None:
			return
		if self.__bots[type][name].isRunning():
			self.__bots[type][name].disconnect()

	def __depopBot(self, type):
		if len(self.__bots[type]) <= 0:
			return
		keys = self.__bots[type].keys()
		
		self.__depopBotByName(keys[len(keys)-1], type)

	def __popChatUtilityBot(self, name, channel):
		bot = botTypes.chatUtilityBot(self.server, "", self.port, name+str(self.__presenceBotsCount+1), channel, self.tokens)
		bot.connectToServer()
