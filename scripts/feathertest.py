import io
import sys
import serial
from time import sleep

ser = None
serio = None
verbose = True #set this to True to see all of the incoming serial data



	
	
def errorhandler(err, exitonerror=True):
	"""Display an error message and exit gracefully on errors from the serial"""
	print("ERROR: " + err.message)
	if exitonerror:
		ser.close()
		sys.exit(-3)
	
	
	
def atcommand(command, delayms=0):
	"""Execurtes the supplied AT command and waits for a valid response"""
	serio.write(command + "\n")
	print(command+"\r\n")
	
	if (delayms != 0):
		sleep(delayms/1000)
		
	rx = None
	while rx != b"OK!\r\n" and rx != "FAILED!\r\n":
		rx = ser.readline()
		if verbose:
			print(str(rx))
	# Check the return value
	if rx == "FAILED!\r\n":
		raise ValueError("AT Parser reported an error on '" + command.rstrip() + "'")
		
		

## Helper functions for the keyboard class
def HIDkeyboard(character, modifier=None):
	"""Converts keys into HID keycodes

	Usage:
	HIDkeyboard('n', modifier='Shift')
	HIDkeyboard('l', modifier='Ctrl')
	HIDkeyboard('F')

	"""
	if modifier==None:
		return '00-00-' + HIDkeycode(character)
	elif modifier=='Ctrl':
		return '01-00-' + HIDkeycode(character)
	elif modifier=='Shift':
		return '02-00-' + HIDkeycode(character)
	elif modifier=='Alt':
		return '03-00-' + HIDkeycode(character)

def HIDkeycode(character):
	# Converts single characters into HID keycodes
	character = character.lower()
	return {
		'a' : '04',
		'b' : '05',
		'c' : '06',
		'd' : '07',
		'e' : '08',
		'f' : '09',
		'g' : '0A',
		'h' : '0B',
		'i' : '0C',
		'j' : '0D',
		'k' : '0E',
		'l' : '0F',
		'm' : '10',
		'n' : '11',
		'o' : '12',
		'p' : '13',
		'q' : '14',
		'r' : '15',
		's' : '16',
		't' : '17',
		'u' : '18',
		'v' : '19',
		'w' : '1A',
		'x' : '1B',
		'y' : '1C',
		'z' : '1D',
		'1' : '1E',
		'2' : '1F',
		'3' : '20',
		'4' : '21',
		'5' : '22',
		'6' : '23',
		'7' : '24',
		'8' : '25',
		'9' : '26',
		'0' : '27',
		'return' : '28',
		'escape' : '29',
		'backspace' : '2A',
		'tab' : '2B',
		'space' : '2C',
		'minus' : '2D',
		'equal' : '2E',
		'bracket_left' : '2F',
		'bracket_right' : '30',
		'backslash' : '31',
		'europe_1' : '32',
		'semicolon' : '33',
		'apostrophe' : '34',
		'grave' : '35',
		'comma' : '36',
		'period' : '37',
		'slash' : '38',
		'caps_lock' : '39',
		'f1' : '3A',
		'f2' : '3B',
		'f3' : '3C',
		'f4' : '3D',
		'f5' : '3E',
		'f6' : '3F',
		'f7' : '40',
		'f8' : '41',
		'f9' : '42',
		'f10' : '43',
		'f11' : '44',
		'f12' : '45',
		'print_screen' : '46'
	}.get(character, '00')
			
	

		
if __name__ == '__main__':
	# Set up serial connection
	ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, rtscts=True)
	serio = io.TextIOWrapper(io.BufferedRWPair(ser,ser,1), newline='\r\n', line_buffering=True)
	

							 
	# Add the keyboard
	try: 
		atcommand("AT+BleKeyboardCode="+HIDkeyboard('G', 'Shift'))
	except ValueError as err:
		errorhandler(err)
	except KeyboardInterrupt:
		# Close nicely on CTRL-C
		ser.close()
		sys.exit()

		