# -*- coding: utf-8

from struct import pack, unpack
import socket, sys, time, datetime

class mumblePing():
	host = None
	port = 0
	
	ping = 0
	users = 0
	max_users = 0
	version = None
	bandwidth = 0
	
	def __init__(self, host, port):
		self.host = host
		self.port = port

	def _doPing(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.settimeout(1)

		buf = pack(">iQ", 0, datetime.datetime.now().microsecond)
		s.sendto(buf, (self.host, self.port))

		try:
			data, addr = s.recvfrom(1024)
		except socket.timeout:
			print("Timeout on ping")
			return
		
		r = unpack(">bbbbQiii", data)

		self.version = r[1:4]
		# r[0,1,2,3] = version
		# r[4] = ts
		# r[5] = users
		# r[6] = max users
		# r[7] = bandwidth

		self.ping = (datetime.datetime.now().microsecond - r[4]) / 1000.0
		if self.ping < 0: self.ping = self.ping + 1000
		
		self.users = r[5]
		self.max_users = r[6]
		
		self.bandwidth = r[7]/1000

	def getNumUsers(self):
		return self.users
