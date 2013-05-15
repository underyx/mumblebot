# This Python file uses the following encoding: utf-8
'''
Created on Feb 6, 2012

@author: johannes
'''

import socket
import ssl
import platform
import Mumble_pb2
import struct
import time
import thread
import subprocess
import sys
import re
import time
import os
import requests
import codecs
import unicodedata
from config import *


"""
fbconsole.AUTH_SCOPE = ['offline_access']
fbconsole.authenticate()
"""


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

    host = None
    port = None
    password = None
    tokens = None
    sock = None
    session = None
    channel = None
    _pingTotal = 1
    running = False
    _textCallbacks = []
    masterid = None

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
        Mumble_pb2.ContextActionAdd: 16,
        Mumble_pb2.ContextAction: 17,
        Mumble_pb2.UserList: 18,
        Mumble_pb2.VoiceTarget: 19,
        Mumble_pb2.PermissionQuery: 20,
        Mumble_pb2.CodecVersion: 21
    }

    _messageLookupNumber = {}

    def __init__(self, host, password, port, nickname, channel, tokens, mastername):
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
        self.host = host
        self.password = password
        self.port = port
        self.nickname = nickname
        self.channel = channel
        self.tokens = tokens
        self.mastername = mastername

        for i in self._messageLookupMessage.keys():
            self._messageLookupNumber[self._messageLookupMessage[i]] = i

    def _pingLoop(self):
        while(self.running):
            self._sendPing()
            time.sleep(1)

    def _mainLoop(self):
        while(self.running):
            self._readPacket()

    def _parseMessage(self, msgType, stringMessage):
        msgClass = self._messageLookupNumber[msgType]
        message = msgClass()
        message.ParseFromString(stringMessage)
        return message

    def addChatCallback(self, trigger, function):
        """
        Adds a function and a trigger for that function. Will execute the
        given function if the "Trigger" String occurs in channel tex".

        @param trigger: Text trigger, currently NO regexp support
        @type trigger: String
        @param function: Function to be called, Strings it returns are written back to the channel.
        @type function: Python Function
        """
        self._textCallbacks.append((trigger, function))

    def _readTotally(self, size):
        message = ""
        while len(message) < size:
            received = self.sock.recv(size - len(message))
            message += received
            if len(received) == 0:
                #print("Nothing received!")
                return None
        return message

    def _sendTotally(self, message):
        while len(message) > 0:
            sent = self.sock.send(message)
            if sent < 0:
                return False
            message = message[sent:]
        return True

    def _packageMessageForSending(self, msgType, stringMessage):
        length = len(stringMessage)
        return struct.pack(">HI", msgType, length) + stringMessage

    def connectToServer(self):
        """
        Really connects to the mumble server
        """
        if self.sock is None:
            #
            # Guttenberg'd from eve-bot
            #
            self.sock = socket.socket(type=socket.SOCK_STREAM)
            self.sock = ssl.wrap_socket(self.sock, ssl_version=ssl.PROTOCOL_TLSv1)
            self.sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)

            self.sock.connect((self.host, self.port))

            pbMess = Mumble_pb2.Version()
            pbMess.release = "1.2.0"
            pbMess.version = 66048
            pbMess.os = platform.system()
            pbMess.os_version = "mumblebot lol"

            initialConnect = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

            pbMess = Mumble_pb2.Authenticate()
            pbMess.password = self.password
            pbMess.username = self.nickname
            [pbMess.tokens.append(token) for token in self.tokens]
            if self.password is not None:
                pbMess.password = self.password

            initialConnect += self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

            if not self._sendTotally(initialConnect):
                print("couldn't send, wtf?")
                return
            else:
                self.running = True
                thread.start_new_thread(self._pingLoop, ())
                thread.start_new_thread(self._mainLoop, ())

    def sendTextMessage(self, Text):
        """
        Send text message to channel

        @param Text: Text that should be sent to channel
        @type Text: String
        """
        pbMess = Mumble_pb2.TextMessage()
        # print(self.session)
        pbMess.session.append(self.session)
        pbMess.channel_id.append(self.channel)
        # pbMess.tree_id.append(())
        pbMess.message = Text

        packet = self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())

        if not self._sendTotally(packet):
            print("couldnt't send text message, wtf?")

    def _readPacket(self):
        channels = {}
        meta = self._readTotally(6)
        if meta:
            msgType, length = struct.unpack(">HI", meta)
            stringMessage = self._readTotally(length)
            #print ("Message of type "+str(msgType)+" received!")
            #print (stringMessage)

            if not self.session and msgType == 5:
                message = self._parseMessage(msgType, stringMessage)
                self.session = message.session
                self._joinChannel()

            if(msgType == 7):
                message = self._parseMessage(msgType, stringMessage)
                channels[message.name] = message.channel_id
                print("Channel " + codecs.encode(codecs.decode(message.name, 'utf-32', 'replace'), 'utf-8') + ": " + str(message.channel_id))
                if followmode:
                    if(message.name == self.channel):
                        self.channel = message.channel_id

            if(msgType == 9):
                message = self._parseMessage(msgType, stringMessage)
                if followmode:
                    if message.name == self.mastername:
                        self.masterid = message.session
                        self.channel = message.channel_id
                    if message.actor == self.masterid and message.channel_id != self.channel and message.channel_id:
                        self.channel = message.channel_id
                        self._joinChannel()

            if(msgType == 11):
                message = self._parseMessage(msgType, stringMessage)
                msg = message.message.lower()
                self.sendTextMessage('(parrot):'+msg)

    def _sendPing(self):
        pbMess = Mumble_pb2.Ping()
        pbMess.timestamp = (self._pingTotal * 5000000)
        pbMess.good = 0
        pbMess.late = 0
        pbMess.lost = 0
        pbMess.resync = 0
        pbMess.udp_packets = 0
        pbMess.tcp_packets = self._pingTotal
        pbMess.udp_ping_avg = 0
        pbMess.udp_ping_var = 0.0
        pbMess.tcp_ping_avg = 50
        pbMess.tcp_ping_var = 50
        self._pingTotal += 1
        packet = struct.pack(">HI", 3, pbMess.ByteSize()) + pbMess.SerializeToString()

        self.sock.send(packet)

    def _joinChannel(self):
        pbMess = Mumble_pb2.UserState()
        pbMess.session = self.session

        pbMess.channel_id = self.channel

        if not self._sendTotally(self._packageMessageForSending(self._messageLookupMessage[type(pbMess)], pbMess.SerializeToString())):
            print ("Error sending join packet")
