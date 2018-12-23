import sys

from docopt import docopt
from bluepy.btle import (
    Scanner, Peripheral, AssignedNumbers,
    ADDR_TYPE_RANDOM, UUID, BTLEException
)
from binascii import hexlify
from tabulate import tabulate


def identity(x):
    return x


if sys.version_info >= (3,):
    # In Python 3 we are already dealing with bytes,
    # so just return the original value.
    get_byte = identity
else:
    get_byte = ord

# firmware == 2.99.15 (or higher?)
SWITCHMATE_SERVICE = 'a22bd383-ebdd-49ac-b2e7-40eb55f5d0ab'


ORIGINAL_STATE_HANDLE = 0x2e
BRIGHT_STATE_HANDLE = 0x30

ORIGINAL_MODEL_STRING_HANDLE = 0x14

SERVICES_AD_TYPE = 0x07
MANUFACTURER_DATA_AD_TYPE = 0xff


def get_switchmates(scan_entries, mac_address):
    switchmates = []
    for scan_entry in scan_entries:
        service_uuid = scan_entry.getValueText(SERVICES_AD_TYPE)
        is_switchmate = service_uuid == SWITCHMATE_SERVICE
        if not is_switchmate:
            continue
        if mac_address and scan_entry.addr == mac_address:
            return [scan_entry]
        if scan_entry not in switchmates:
            switchmates.append(scan_entry)
    switchmates.sort(key=lambda sw: sw.addr)
    return switchmates


def scan(
    start_msg, process_entry,
    timeout=None, mac_address=None, success_msg=None
):
    print(start_msg)
    sys.stdout.flush()

    scanner = Scanner()

    try:
        switchmates = get_switchmates(scanner.scan(timeout), mac_address)
    except BTLEException as ex:
        print(
            'ERROR: Could not complete scan.',
            'Try running switchmate with sudo.',
            ex.message
        )
        return
    except OSError as ex:
        print(
            'ERROR: Could not complete scan.',
            'Try compiling the bluepy helper.',
            ex
        )
        return

    if len(switchmates):
        if success_msg:
            print(success_msg)
        for switchmate in switchmates:
            process_entry(switchmate)
    else:
        print('No Switchmate devices found')


def debug_helper(device):
    output = [['uuid', 'common name', 'handle', 'properties', 'value']]
    for char in device.getCharacteristics():
        if char.supportsRead():
            val = char.read()
            binary = False
            for c in val:
                if get_byte(c) < 32 or get_byte(c) > 126:
                    binary = True
            if binary:
                val = hexlify(val)
        output.append([
            str(char.uuid),
            UUID(char.uuid).getCommonName(),
            '{0:x}'.format(char.getHandle()),
            char.propertiesToString(),
            str(val)
        ])
    print(tabulate(output, headers='firstrow'))


def is_original_device(device):
    # The handle for reading the model string on Bright devices is actually
    # different from Original devices, but using getCharacteristics to read
    # the model is much slower.
    #model = device.readCharacteristic(ORIGINAL_MODEL_STRING_HANDLE)
    #print(model)
    #return model == b'Original'
    return True


def get_state_handle(device):
    return ORIGINAL_STATE_HANDLE
    #if is_original_device(device):
    #    return ORIGINAL_STATE_HANDLE
    #else:
    #    return BRIGHT_STATE_HANDLE


def switch(device, val):
    state_handle = get_state_handle(device)
    #curr_val = device.readCharacteristic(state_handle)
    #if val is None:
    #    val = b'\x01' if curr_val == b'\x00' else b'\x00'
    val_num = get_byte(val[0])
    #val_text = ('off', 'on')[val_num]
    #if curr_val != val:
    #    device.writeCharacteristic(state_handle, val, True)
    #    print('Switched {}!'.format(val_text))
    #else:
    #    print('Already {}!'.format(val_text))
    device.writeCharacteristic(state_handle, val, True)

def print_entry_state(entry, state_handle=None):
    service_data = entry.getValueText(MANUFACTURER_DATA_AD_TYPE)
    print(service_data)
    val = int(service_data[1])
    if val>0: val=1
    print(entry.addr, ("off", "on")[val])


def print_battery_level(device):
    battery_level = AssignedNumbers.batteryLevel
    level = device.getCharacteristics(uuid=battery_level)[0].read()
    print('Battery level: {}%'.format(ord(level)))


def print_exception(ex):
    if 'disconnected' in ex.message.lower():
        print('ERROR: Device disconnected.')
    else:
        print('ERROR: ' + ex.message)


class Switch(object):
    """ A switch class for switchmate switches """
    
    def __init__(self, mac_address='c1:59:2c:b2:8d:33'):
        """ return a switch object with the right mac_address"""
        self.mac_address = mac_address
        try:
            self.device = Peripheral(mac_address, ADDR_TYPE_RANDOM)
            self.state_handle = get_state_handle(self.device)
            self.curr_val = self.device.readCharacteristic(self.state_handle)
        except BTLEException as ex:
            print('ERROR: ' + ex.message)
        except OSError as ex:
            print('ERROR: Failed to connect to device.')
        
    @property
    def status(self,):
        return 'off' if self.curr_val==b'\x00'  else 'on'
        
    def switch(self, state=None):
        """ Switch the switchmate on or off 
        Usage: switch('on')
        """
        if state=='on':
            val = b'\x01'
        elif state=='off':
            val = b'\x00'
        elif state==None:
            val = b'\x01' if self.curr_val == b'\x00' else b'\x00'
        try:
            self.device.writeCharacteristic(self.state_handle, val, True)
            self.curr_val=val
        except BTLEException as ex:
            print_exception(ex)
        
    # Functions for a cleaner interface
    def turn_on(self):
        self.switch('on')
    
    def turn_off(self):
        self.switch('off')
    
