import io
import sys
import serial
from time import sleep
from keyconverter import keyboard

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
		
		
		
if __name__ == '__main__':
	# Set up serial connection
	ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, rtscts=True)
	serio = io.TextIOWrapper(io.BufferedRWPair(ser,ser,1), newline='\r\n', line_buffering=True)
	

							 
	# Add the keyboard
	try: 
		atcommand("AT+BleKeyboardCode="+keyboard('G', 'Shift'))
	except ValueError as err:
		errorhandler(err)
	except KeyboardInterrupt:
		# Close nicely on CTRL-C
		ser.close()
		sys.exit()

		
			
	
