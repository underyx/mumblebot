# -*- coding: utf-8

import socket
import ssl
import platform
import Mumble_pb2
from struct import pack, unpack
import time
import thread
import subprocess
import sys
import re
import time
import os
import requests
import unicodedata
from config import *


def strip_accents(s):  # Credit to oefe on stackoverflow.com
	if not s:
		return False
	return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))

class mumbleConnection():
	'''
	This class represents a persistent connection to a mumble Server
	via TCP. Id doesn't support UDP and taking in account the fact that
	UDP is optional it most likely never will.
	'''

	id = 0;

	host = None
	port = None
	password = None
	tokens = None
	sock = None
	nickname = None
	session = 0
	targetChannel = None
	channel_id = 0
	user_id = 0
	_pingTotal = 1
	running = False
	masterid = None
	numUsers = 0

	_onBotDieHandler = []
	_onBotConnectHandler = []
	_onConnectionRefusedHandler = []

	_messageLookupMessage = {
        Mumble_pb2.Version: 0,
        Mumble_pb2.UDPTunnel: 1,
        Mumble_pb2.Authenticate: 2,
        Mumble_pb2.Ping: 3,
        Mumble_pb2.Reject: 4,
        Mumble_pb2.ServerSync: 5,
        Mumble_pb2.ChannelRemove: 6,
        Mumble_pb2.ChannelState: 7,
        Mumble_pb2.UserRemove: 8,
        Mumble_pb2.UserState: 9,
        Mumble_pb2.BanList: 10,
        Mumble_pb2.TextMessage: 11,
        Mumble_pb2.PermissionDenied: 12,
        Mumble_pb2.ACL: 13,
        Mumble_pb2.QueryUsers: 14,
        Mumble_pb2.CryptSetup: 15,
        Mumble_pb2.ContextActionModify: 16,
        Mumble_pb2.ContextAction: 17,
        Mumble_pb2.UserList: 18,
        Mumble_pb2.VoiceTarget: 19,
        Mumble_pb2.PermissionQuery: 20,
        Mumble_pb2.CodecVersion: 21,
		Mumble_pb2.UserStats: 22,
		Mumble_pb2.RequestBlob: 23,
		Mumble_pb2.ServerConfig: 24,
		Mumble_pb2.SuggestConfig: 25
	}
    

	_messageLookupNumber = {}
	
	_knownUsers = []
	_channels = {}

	def __init__(self, id, host, password, port, nickname, channel, tokens):
		"""
		Creates a mumble Connection but doesn't open it yet.

		@param host: Mumble server to connect to, as hostname or IP address
		@type host: String
		@param password: Server password, if the server doesn't have one, leave it empty or put in whatever you like to.
		@type password: String
		@param port: Port on which the mumble server listens.
		@type port: String
		@param channel: Channel name the bot should join.
		@type channel: String
		"""
		self.id = id;
		self.host = host
		self.password = password
		self.port = port
		self.nickname = nickname
		self.targetChannel = channel
		self.tokens = tokens
		self.numUsers = 0
		self._onBotConnectHandler = []
		self._onBotDieHandler = []
		self._onConnectionRefusedHandler = []
		self._knownUsers = []
		self._channels = {}

		for i in self._messageLookupMessage.keys():
			self._messageLookupNumber[self._messageLookupMessage[i]] = i

		print("Bot#"+str(id)+ " Created")

	def _pingLoop(self):
		while(self.running):
			self._sendPing()
			time.sleep(20)

	def _mainLoop(self):
		while(self.running):
			self._readPacket()

	def _parseMessage(self, msgType, stringMessage):
		msgClass = self._messageLookupNumber[msgType]
		message = msgClass()
		message.ParseFromString(stringMessage)
		return message

	def _readTotally(self, size):
		if not self.running:
			return
		try:
			message = ""
			while len(message) < size:
				received = self.sock.recv(size - len(message))
				message += received
				if len(received) == 0:
					#print("Nothing received!")
					return None
			return message
		except socket.timeout:
			print("Bot#"+str(self.id)+" Timeout")
			self.disconnect()
			return ""
		except socket.error as e:
			print("Bot#"+str(self.id)+" Error" + str(e))
			self.disconnect()
			return ""

	def _sendTotally(self, message):
		try:
			while len(message) > 0:
				sent = self.sock.send(message)
				if sent < 0:
					return False
				message = message[sent:]
			return True
		except socket.timeout:
			print("Bot#"+str(self.id)+" Timeout")
			self.disconnect()
			return False
		except socket.error as e:
			print("Bot#"+str(self.id)+" Error" + str(e))
			self.disconnect()
			return False

	def _packageMessageForSending(self, msgType, stringMessage):
		length = len(stringMessage)
		return pack(">HI", msgType, length) + stringMessage

	def _close(self):
		if not self.sock is None:
			self.running = False
			try:
				self.sock.shutdown(socket.SHUT_RDWR)
				self.sock.close()
			except socket.error:
				pass
			self.sock = None
			print("Bot#"+str(self.id)+" Disconnected")
			self._handleBotDie()

	def _handleBotDie(self):
		for i in self._onBotDieHandler:
			i(self.id)

	def _handleBotConnect(self):
		for i in self._onBotConnectHandler:
			i(self.id)

	def _handleConnectionRefused(self):
		for i in self._onConnectionRefusedHandler:
			i(self.id)

	def addBotDieHandler(self, func):
		self._onBotDieHandler.append(func)
		
	def addBotConnectHandler(self, func):
		self._onBotConnectHandler.append(func)

	def addConnectionRefusedHandler(self, func):
		self._onConnectionRefusedHandler.append(func)

	def getNumUsers(self):
		return len(self._knownUsers)

	def connectToServer(self):
		"""
		Really connects to the mumble server
		"""
		if self.sock is None:
			try:
				self.sock = socket.socket(type=socket.SOCK_STREAM)
				self.sock = ssl.wrap_socket(self.sock, ssl_version=ssl.PROTOCOL_TLSv1)
				self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)

				self.sock.connect((self.host, self.port))
			except ssl.SSLError as e:
				print("Bot#"+str(self.id)+" SSLError: " + str(e))
				self.disconnect()
				self._handleConnectionRefused()
				return

			except socket.timeout as e:
				print("Bot#"+str(self.id)+" Timeout: " + str(e))
				self.disconnect()
				return

			except socket.error as e:
				print("Bot#"+str(self.id)+" Error: " + str(e))
				self.disconnect()
				return


			pbMess = Mumble_pb2.Version()
			pbMess.release = "1.2.1"
			pbMess.version = 66050
			pbMess.os = platform.system()
			pbMess.os_version = "Mumblebot"

			initialConnect = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

			pbMess = Mumble_pb2.Authenticate()
			pbMess.username = self.nickname
			if self.tokens is not None:
				[pbMess.tokens.append(token) for token in self.tokens]
			if self.password is not None:
				pbMess.password = self.password

			initialConnect += self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

			if not self._sendTotally(initialConnect):
				print("couldn't send, wtf?")
				self.disconnect()
				return
			else:
				self.running = True
				thread.start_new_thread(self._pingLoop, ())
				thread.start_new_thread(self._mainLoop, ())

	def disconnect(self):
		self._close()

	def isRunning(self):
		return self.running

	def getChannelIdByName(self, channel_name):
		for id in self._channels:
			if self._channels[id] == channel_name:
				return id
		return 0

	def sendTextMessage(self, Text):
		"""
		Send text message to channel

		@param Text: Text that should be sent to channel
		@type Text: String
		"""
		pbMess = Mumble_pb2.TextMessage()
		pbMess.session.append(self.session)
		pbMess.channel_id.append(self.channel_id)
		pbMess.message = Text

		packet = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

		if not self._sendTotally(packet):
			print("couldnt't send text message, wtf?")

	def switchToChannel(self, new_channel):
		if self.session == 0:
			return
			
		pbMess = Mumble_pb2.UserState()
		pbMess.session = int(self.session)
		pbMess.channel_id = int(new_channel)
		pbMess.self_mute = True;
		pbMess.self_deaf = True;

		packet = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

		if not self._sendTotally(packet):
			print("couldnt't send UserState")
		else:
			if self.channel_id != new_channel:
				self.channel_id = new_channel
				print("Bot#"+str(self.id)+" switched to channel#"+str(new_channel))

	def _readPacket(self):
		meta = self._readTotally(6)
		if meta:
			msgType, length = unpack(">HI", meta)
			stringMessage = self._readTotally(length)

			""""
			if(msgType != 3 and msgType != 1):
				print ("Bot#"+str(self.id)+" Message of type "+str(self._messageLookupNumber[msgType])+" (" + str(msgType) + ") received!")
			"""

			if(msgType == 5): # ServerSync
				packet = self._parseMessage(msgType, stringMessage)
				self.session = packet.session
				print("Bot#"+str(self.id)+" session: " + str(packet.session))
				self.switchToChannel(self.getChannelIdByName(self.targetChannel))

			if(msgType == 4): # Reject
				packet = self._parseMessage(msgType, stringMessage)
				print("Bot#"+str(self.id)+" rejected (" + str(packet.type) + ") : " + packet.reason)
				self.disconnect();

			if(msgType == 6): # ChannelRemove
				packet = self._parseMessage(msgType, stringMessage)
				del self._channels[packet.channel_id]
					#print("Switching to channel_id " + str(packet.channel_id))

			if(msgType == 7): # ChannelState
				packet = self._parseMessage(msgType, stringMessage)
				self._channels[packet.channel_id] = packet.name
				if packet.name == self.targetChannel:
					self.switchToChannel(packet.channel_id)
					#print("Switching to channel_id " + str(packet.channel_id))

			if(msgType == 8): # UserRemove
				packet = self._parseMessage(msgType, stringMessage)
				
				if packet.session not in self._knownUsers:
					self._knownUsers.remove(packet.session)
					self.numUsers -= 1;
				#print("Bot#"+str(self.id)+" remove user total: " + str(self.numUsers))

			if(msgType == 9): # UserState
				packet = self._parseMessage(msgType, stringMessage)
				if packet.session not in self._knownUsers:
					self._knownUsers.append(packet.session)
					self.numUsers += 1;
				if packet.session == self.session:
					self.channel_id == packet.channel_id
					print("Bot#"+str(self.id)+" is in channel#" + str(packet.channel_id))
					self.switchToChannel(self.getChannelIdByName(self.targetChannel))

			#if(msgType == 11): # TextMessage
				#packet = self._parseMessage(msgType, stringMessage)
				#self.sendTextMessage('(parrot): '+packet.message)
				
			if(msgType == 12): # PermissionDenied
				packet = self._parseMessage(msgType, stringMessage)
				print("Bot#"+str(self.id)+" PermissionDenied (" + str(packet.type) + ") : " + packet.reason)
				self.disconnect()
				self._handleConnectionRefused()

	def _sendPing(self):
		pbMess = Mumble_pb2.Ping()
		"""pbMess.timestamp = (self._pingTotal * 5000000)
		pbMess.good = 0
		pbMess.late = 0
		pbMess.lost = 0
		pbMess.resync = 0
		pbMess.udp_packets = 0
		pbMess.tcp_packets = self._pingTotal
		pbMess.udp_ping_avg = 0
		pbMess.udp_ping_var = 0.0
		pbMess.tcp_ping_avg = 50
		pbMess.tcp_ping_var = 50"""
		self._pingTotal += 1
		packet = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())
		if not self._sendTotally(packet):
			print("Ping error");
