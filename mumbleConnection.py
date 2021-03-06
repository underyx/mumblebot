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
import time
import os
import re
import telnetlib
import BeautifulSoup as bs
import urllib2
import requests
import codecs
import unicodedata
import gdata.youtube
import gdata.youtube.service
import praw
import fbconsole
import PIL
from PIL import Image
import base64
import cStringIO
import HTMLParser
from config import *

yt_service = gdata.youtube.service.YouTubeService()
r = praw.Reddit(user_agent='mumblebot by /u/underyx')
r.login(reddituser, redditpass)

"""
fbconsole.AUTH_SCOPE = ['offline_access']
fbconsole.authenticate()
"""


def strip_accents(s):  # Credit to oefe on stackoverflow.com
    if not s:
        return False
    return ''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))


def getYoutubeData(videoid):
    entry = yt_service.GetYouTubeVideoEntry(video_id=videoid)
    title = entry.media.title.text
    m, s = divmod(int(entry.media.duration.seconds), 60)
    return strip_accents(unicode(title)), unicode("%d:%02d" % (m, s))


def getRedditTitle(link):
    try:
        print link
        print r.info(url=link)
        print list(r.info(url=link))
        result = next(r.info(url=link))
    except StopIteration:
        return None
    cid = result.content_id[3:]
    title = str(r.get_submission(submission_id=cid)).split(" :: ", 1)[1]
    shortlink = "http://redd.it/" + cid
    return title, shortlink


def getFBTitle(photoid):
    try:
        print "/%s" % photoid
        data = fbconsole.get("/%s" % photoid)
    except urllib2.HTTPError as e:
        print e.read()
        return None
    try:
        return data["name"], data["from"]["name"], data["link"]
    except Exception:
        return "Unnamed picture", data["from"]["name"], data["link"]
        print "FB error #2"


def parseQueueLink(link):
    ytid = re.search("v=([\w-]{11})", link)
    if ytid:
        result = getYoutubeData(ytid.group(1)) or ("Song name not found", "?:??")
        print result
        return result


def telnetVLC(command):
    try:
        tn = telnetlib.Telnet("localhost", 4212)
        tn.read_until("Password: ")
        tn.write("admin\n")
        tn.read_until(">")
        tn.write(command + "\n")
        return tn.read_until(">")
    except Exception:
        pass


def playinVLC(input):
    info = subprocess.STARTUPINFO()
    info.dwFlags = 1
    info.wShowWindow = 0
    subprocess.Popen(["C:\Program Files (x86)\VideoLAN\VLC\\vlc.exe", "--intf", "telnet", "--vout", "dummy", "--playlist-enqueue", input], startupinfo=info)
    telnetVLC("play")
    telnetVLC("volume 60")
    telnetVLC("next")


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
                outmsg = ""
                if msg[:5] == "play ":
                    msg_data = msg[5:].split(",")  # Split in case CSV
                    for item in msg_data:
                        if "http" in item:
                            link = re.search(r"<a href=\"((?:http|https)://\S+)\"", item).group()
                            yt = re.search(r"v=([\w-]{11})", link)
                            try:
                                if yt:
                                    try:
                                        youtubedata = getYoutubeData(yt.group(1))
                                        outmsg += "<br /><b> %s [%s]</b>" % youtubedata
                                        playinVLC("http://www.youtube.com/watch?v=" + yt.group(1))
                                    except Exception:
                                        outmsg += "<br />You ain't foolin' this dog, mister."
                                elif re.search("(mp3|wav|ogg)", item):
                                    playinVLC(re.search('href="(.+)"', item).group(1))
                                self.sendTextMessage(outmsg)
                            except Exception:
                                self.sendTextMessage(outmsg)
                        else:
                            try:
                                params = {"vq": item, "racy": "include", "orderby": "relevance", "alt": "json", "fields": "entry(media:group(media:player))"}
                                ytid = requests.get("http://gdata.youtube.com/feeds/api/videos", params=params).json()["feed"]["entry"][0]["media$group"]["media$player"][0]["url"][31:42]
                                youtubedata = getYoutubeData(ytid)
                                self.sendTextMessage("<br /><b> <a href='http://www.youtube.com/watch?v=%s'>%s</a> [%s]</b>" % (ytid, youtubedata[0], youtubedata[1]))
                                playinVLC("http://www.youtube.com/watch?v=" + ytid)
                            except Exception:
                                self.sendTextMessage("<br /><b>No results found or some other random error I dunno.</b>")

                elif msg == "stop":
                    os.system("taskkill /F /IM vlc.exe")

                elif msg == "next":
                    telnetVLC("next")

                elif msg == "prev":
                    telnetVLC("prev")

                elif msg == "info":
                    playlist = re.findall("^\|   \d+ - (?:(.+?) ?\((\d\d:\d\d:\d\d)\)?(?: \[played \d* times?])?|(https?://.+))\r",  telnetVLC("playlist"), re.MULTILINE)
                    i = 0
                    playlistmsg = "<br />"
                    for title, length, link in playlist:
                        i += 1
                        if title:
                            length = unicode("%d:%02d" % divmod(int(length[0:2]) * 3600 + int(length[3:5]) * 60 + int(length[6:8]), 60))
                        elif link:
                            title, length = parseQueueLink(link)
                        playlistmsg += "#%s <b>%s - [%s]</b><br />" % (i, title, length)
                    self.sendTextMessage(playlistmsg)

                elif msg.startswith("my "):
                    self.sendTextMessage("It looks good.")

                elif msg.startswith("seek"):
                    telnetVLC("seek %s%%" % re.search("\d+", msg).group())

                elif msg.startswith("vol"):
                    if not re.search("\d", msg):
                        outmsg = "<b>Current Volume:</b> " + str(int(float(telnetVLC("volume")[:-3]) / 2.56))
                        self.sendTextMessage(outmsg)
                    elif int(round(float(re.search("\d+", msg).group()))) > 100 and message.name != self.mastername:
                        self.sendTextMessage("<b>NOPE</b>")
                    else:
                        telnetVLC("volume %s" % int(round(float(re.search("\d+", msg).group())*2.56)))

                else:
                    links = re.findall(r"<a href=\"((?:http|https)://\S+)\"", msg)
                    for link in links:
                        print link
                        link = HTMLParser.HTMLParser().unescape(link)
                        try:
                            file = cStringIO.StringIO(urllib2.urlopen(link).read())
                            img = Image.open(file)
                            basewidth = 350

                            if basewidth < img.size[0]:
                                wpercent = (basewidth / float(img.size[0]))
                                hsize = int((float(img.size[1]) * float(wpercent)))
                                img = img.resize((basewidth, hsize), PIL.Image.ANTIALIAS)
                            img.save('tmp.jpg', 'JPEG')
                            outimage = 'tmp.jpg'
                            self.sendTextMessage("<br /><img src=\"data:image/jpeg;base64, %s\"/>" % base64.encodestring(open(outimage, "rb").read()))
                            os.remove(outimage)
                        except Exception:
                            pass

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
