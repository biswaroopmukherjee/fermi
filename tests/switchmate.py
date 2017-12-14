import struct
import sys
import ctypes
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, ADDR_TYPE_RANDOM
from binascii import hexlify, unhexlify


SWITCHMATE_SERVICE = '23d1bcea5f782315deef121223150000'
NOTIFY_VALUE = struct.pack('<BB', 0x01, 0x00)

AUTH_NOTIFY_HANDLE = 0x0017
AUTH_HANDLE = 0x0016
AUTH_INIT_VALUE = struct.pack('<BBBBBB', 0x00, 0x00, 0x00, 0x00, 0x01, 0x00)

STATE_HANDLE = 0x000e
STATE_NOTIFY_HANDLE = 0x000f


def c_mul(a, b):
	'''
	Multiplication function with overflow
	'''
	return ctypes.c_int64((a * b) &0xffffffffffffffff).value

def sign(data, key):
	'''
	Variant of the Fowler-Noll-Vo (FNV) hash function
	'''
	blob = data + key
	x = blob[0] << 7
	for c in blob:
		x1 = c_mul(1000003, x)
		x = x1 ^ c ^ len(blob)

	# once we have the hash, we append the data
	shifted_hash = (x & 0xffffffff) << 16
	shifted_data_0 = data[0] << 48
	shifted_data_1 = data[1] << 56
	packed = struct.pack('<Q', shifted_hash | shifted_data_0 | shifted_data_1)[2:]
	return packed

class NotificationDelegate(DefaultDelegate):
	def __init__(self, device):
		DefaultDelegate.__init__(self)
		self.device = device

	def handleNotification(self, handle, data):
		print('')
		succeeded = True
		if handle == AUTH_HANDLE:
			print('Auth key is {}'.format(hexlify(data[3:]).upper()))
		else:
			if data[-1] == 0:
				print('Switched!')
			else:
				print('Switching failed!')
				succeeded = False
		self.device.disconnect()
		sys.exit(0 if succeeded else 1)

class Switch(object):
	""" A switch class for switchmate switches """
	
	def __init__(self, mac_address='c1:59:2c:b2:8d:33', auth_key=b'C84FE8BB'):
		""" return a switch object with the right mac_address and auth"""
		self.mac_address = mac_address
		self.auth_key = auth_key

	def switch(self, state):
		""" Switch the switchmate on or off 
		Usage: switch('on')
		"""
		device = Peripheral(self.mac_address, ADDR_TYPE_RANDOM)
		notifications = NotificationDelegate(device)
		device.setDelegate(notifications)
		
		auth_key = unhexlify(self.auth_key)
		device.writeCharacteristic(STATE_NOTIFY_HANDLE, NOTIFY_VALUE, True)
		if state == 'on':
			val = b'\x01'
		else:
			val = b'\x00'
		device.writeCharacteristic(STATE_HANDLE, sign(b'\x01' + val, auth_key))
		print('Waiting for response', end='')
		while True:
			device.waitForNotifications(0.1)
			print('.', end='')
			sys.stdout.flush()
		
	# Functions for a cleaner interface
	def turn_on(self):
		self.switch('on')
	
	def turn_off(self):
		self.switch('off')
	
