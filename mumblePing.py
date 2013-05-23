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

	def __doPing(self):
		try:
			addrinfo = socket.getaddrinfo(self.host, self.port, 0, 0, socket.SOL_UDP)
		except socket.gaierror, e:
			print("ping getaddrinfo error")
			return

		for (family, socktype, proto, canonname, sockaddr) in addrinfo:
			s = socket.socket(family, socktype)
			s.settimeout(1)

			buf = pack(">iQ", 0, datetime.datetime.now().microsecond)
			try:
				s.sendto(buf, sockaddr)
			except socket.gaierror, e:
				print("ping sendto error")
				return

			try:
				data, addr = s.recvfrom(1024)
			except socket.timeout:
				print("Timeout on ping")
				return
			except socket.gaierror:
				print("get ip failed")
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
		self.__doPing()
		return self.users
