
##################################################
#
# Fermi: a voice controlled lab computer controller
#
# 2017
# Biswaroop Mukherjee
#
##################################################

# Imports
import signal
import logging

from lab.labwork import Lab
from lab.fermi_assistant import FermiAssistant
import lab.snowboy.snowboydecoder as snowboydecoder


# Initialization
verbose = True
model = 'lab/snowboy/resources/Fermi 3.pmdl'

interrupted = False
detector = None
assistant = None
lab = None


# Signal handlers for snowboy
def signal_handler(signal, frame):
    global interrupted
    interrupted = True

def interrupt_callback():
    global interrupted
    return interrupted


# Setup logger.
logging.basicConfig()
logger = logging.getLogger("fermi")
if verbose:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

signal.signal(signal.SIGINT, signal_handler)

# Setup the lab and the assistant
lab = Lab(name='fermi 3')
assistant = FermiAssistant(lab)
assistant.assist()

