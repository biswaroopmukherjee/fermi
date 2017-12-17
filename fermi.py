# Fermi: a voice controlled lab computer controller
#
# 2017
# Biswaroop Mukherjee


# Imports

# imports for snowboy
import snowboydecoder
import sys
import signal
import subprocess

import json
import logging
import os
import re
import click
from gtts import gTTS
import wave
import contextlib

# imports for google assistant
import grpc
import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials

from google.assistant.embedded.v1alpha1 import embedded_assistant_pb2
from google.rpc import code_pb2
from tenacity import retry, stop_after_attempt, retry_if_exception

import assistant_helpers
import audio_helpers

# imports for keyboard
import io
import sys
import serial
from time import sleep
from keyconverter import keyboard

# imports for switchmate
import switchmate

# imports for arxiv reader
from arxiv_reader import Reader


# Initialization
ASSISTANT_API_ENDPOINT = 'embeddedassistant.googleapis.com'
END_OF_UTTERANCE = embedded_assistant_pb2.ConverseResponse.END_OF_UTTERANCE
DIALOG_FOLLOW_ON = embedded_assistant_pb2.ConverseResult.DIALOG_FOLLOW_ON
CLOSE_MICROPHONE = embedded_assistant_pb2.ConverseResult.CLOSE_MICROPHONE
DEFAULT_GRPC_DEADLINE = 60 * 3 + 5


api_endpoint=ASSISTANT_API_ENDPOINT
credentials = '/home/pi/.config/google-oauthlib-tool/credentials.json'
verbose = True
grpc_deadline = DEFAULT_GRPC_DEADLINE
model = 'resources/Fermi 3.pmdl'


interrupted = False
start_stop = True

detector = None
assistant = None

ser = None
serio = None
switch = None

quiet = False


# Signal handlers for snowboy
def signal_handler(signal, frame):
    global interrupted
    interrupted = True

def interrupt_callback():
    global interrupted
    return interrupted


# Text to speech
class TTS(object):
    def __init__(self, conversation_stream):
        self.conversation_stream = conversation_stream
    def speaktext(self, mytext):
        """ Use by typing speaktext('textstring') """
        if not quiet:
            logger = logging.getLogger("fermi")
            myobj = gTTS(text=mytext, lang='en-us', slow=False)
            myobj.save("text.mp3")
            # Resample
            logger.info("resampling")
            os.system("sox text.mp3 -r 16000 text_r.wav")
            logger.info("resampling successful")
            # Play the converted file
            with contextlib.closing(wave.open("text_r.wav", "r")) as f:
                frames = f.getnframes()
                logger.info(str(frames)+" frames to speak")
                data = f.readframes(frames)
                self.conversation_stream.write(data)
            



# Functions for the keyboard
def errorhandler(err, exitonerror=True):
    """Display an error message and exit gracefully on errors from the serial"""
    logger.error("ERROR: " + err.message)
##    if exitonerror:
##        ser.close()
##        sys.exit(-3)

def atcommand(command, delayms=0):
    """Executes the supplied AT command and waits for a valid response"""
    serio.write(command + "\n")
    logger = logging.getLogger("fermi")
    logger.info(command+"\r\n")

    if (delayms != 0):
        sleep(delayms/1000)

    rx = None
    while rx != b"OK!\r\n" and rx != "FAILED!\r\n":
        rx = ser.readline()
        logger.debug(str(rx))
    # Check the return value
    if rx == "FAILED!\r\n":
        raise ValueError("AT Parser reported an error on '" + command.rstrip() + "'")

def keysend(letter, modifier=None):
    """ a simpler keyboard"""
    try:
        atcommand("AT+BleKeyboardCode="+keyboard(letter, modifier))
    except ValueError as err:
        errorhandler(err)
    except KeyboardInterrupt:
        ser.close()
        sys.exit()


# NLP preprocessor for lab related stuff. If this fails, fall back on google
def labwork(text, quiet, conversation_stream):
    ''' Very hacky NLP on the text blob '''
    playstandard = False
    quietout = quiet
    logger = logging.getLogger("fermi")
    text = text.lower()
    words = re.split(' ', text)
    speaker = TTS(conversation_stream)
    if 'listen' in words: words = words + ['lithium']
    if 'soda' in words: words = words + ['sodium']
    if 'trap' in words or ('pumping' not in words and 'imaging' not in words and ('sodium' in words or 'lithium' in words)):
        if 'lithium' in words:
            logger.info('CTRL-L')
            if not quiet: speaker.speaktext('Turning on lithium mott')
            keysend('L', 'Ctrl')
        elif 'sodium' in words:
            if not quiet: speaker.speaktext('Turning on sodium mott')
            logger.info('CTRL-N')
            keysend('N', 'Ctrl')
        else:
            if not quiet: speaker.speaktext('Please specify the atom.')
             # need to make it more conversational: Sodium or lithium? Context needed
            logger.info('unknown atom')
    elif 'pumping' in words:
        if 'lithium' in words:
            if not quiet: speaker.speaktext('Turning on lithium pumping')
            logger.info('CTRL-P')
            keysend('P', 'Ctrl')
        elif 'sodium' in words:
            if not quiet: speaker.speaktext('Turning on sodium pumping')
            logger.info('CTRL-Q')
            keysend('Q', 'Ctrl')
        else:
            if not quiet: speaker.speaktext('Please specify the atom')
            logger.info('unknown atom')
    elif 'imaging' in words:
        if not quiet: speaker.speaktext('Turning on imaging')
        logger.info('CTRL-I')
        keysend('I', 'Ctrl')
    elif 'abort' in words:
        if not quiet: speaker.speaktext('Aborting')
        logger.info('esc')
        keysend('escape')
    elif 'run' in words or 'running' in words and 'trap' not in words:
        if 'list' in words or 'twelve' in words:
            if not quiet: speaker.speaktext('Running list')
            logger.info('F12')
            keysend('F12')
        elif 'background' in words:
            if not quiet: speaker.speaktext('Running in background')
            logger.info('CTRL-F9')
            keysend('F9')
        else:
            if not quiet: speaker.speaktext('Running sequence')
            logger.info('F9')
            keysend('F9')
    elif 'stop' in words or 'control' in words or 'nothing' in words:
        if not quiet: speaker.speaktext('Okay. Doing nothing.')
        logger.info('CTRL-Z')
        keysend('Z', 'Ctrl')
    elif 'lights' in words or 'room' in words:
        try:
            if 'off' in words:
                if not quiet: speaker.speaktext('Turning off room lights.')
                switch.turn_off()
            else:
                if not quiet: speaker.speaktext('Turning on room lights.')
                switch.turn_on()
        except:
            logger.debug('well I need to fix this error')
    elif 'quiet' in words or 'shut' in words:
        quietout = True
        logger.info('turning off text to speech')
    elif 'stupid' in words:
        logger.info('theyre being mean')
        if not quiet: speaker.speaktext("I'm doing my best. Please try not to be mean to me.")
    elif 'speak' in words or 'speaking' in words:
        quietout = False
        if quiet: speaker.speaktext("Thank you. I've been dying to talk.")
        else: speaker.speaktext("Thank you, but I can already talk.")
        logger.info('turning on text to speech')
    elif 'name' in words:
        if not quiet: speaker.speaktext('why')
        logger.info('why')
    elif 'why' in words:
        if not quiet: speaker.speaktext('Because you told me so.')
        logger.info('Classic matlab')
    elif 'igor' in words:
        if not quiet: speaker.speaktext('Igor? I prefer python.')
    elif 'morning' in words:
        if not quiet: speaker.speaktext('Good morning!')
    elif 'papers' in words or 'paper' in words or 'archive' in words:
        logger.info('checking the arxiv')
        if not quiet: speaker.speaktext("Hold on while I check the archive.")
        reader = Reader(detailed=True)
        try:
            reader.download_info()
        except:
            if not quiet: speaker.speaktext("Sorry. I couldn't connect to the archive")
            logger.error('Cant connect or download the interest list')
        try:
            text_to_say = reader.read_arxiv()
            if not quiet: speaker.speaktext(text_to_say)
            logger.info(text_to_say)
        except:
            if not quiet: speaker.speaktext("I'm sorry. I can't do that right now.")
            logger.error('Cant read the arxiv')
    elif 'pod' in words or 'bay' in words or 'door' in words:
        if not quiet: speaker.speaktext("I'm sorry Dave. I'm afraid I can't do that")
        logger.info('Hal')
    else:
        # Run standard google response
        # speaker.speaktext("Sorry I didn't understand that.")
        playstandard = True
    return playstandard, quietout



class FermiAssistant(object):
    """Fermi Assistant class

    Args:
      conversation_stream(ConversationStream): audio stream
        for recording query and playing back assistant answer.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
    """

    def __init__(self, channel, deadline_sec):
        

        # Opaque blob provided in ConverseResponse that,
        # when provided in a follow-up ConverseRequest,
        # gives the Assistant a context marker within the current state
        # of the multi-Converse()-RPC "conversation".
        # This value, along with MicrophoneMode, supports a more natural
        # "conversation" with the Assistant.
        self.conversation_state = None

        # Create Google Assistant API gRPC client.
        self.assistant = embedded_assistant_pb2.EmbeddedAssistantStub(channel)
        self.deadline = deadline_sec
        self.logger = logging.getLogger("fermi")
        self.quiet = False

    def __enter__(self):
        return self

    def __exit__(self, etype, e, traceback):
        if e:
            return False
        self.conversation_stream.close()

    def is_grpc_error_unavailable(e):
        is_grpc_error = isinstance(e, grpc.RpcError)
        if is_grpc_error and (e.code() == grpc.StatusCode.UNAVAILABLE):
            self.logger.error('grpc unavailable error: %s', e)
            return True
        return False

    @retry(reraise=True, stop=stop_after_attempt(3),
           retry=retry_if_exception(is_grpc_error_unavailable))
    def converse(self):
        """Send a voice request to the Assistant and playback the response.

        Returns: True if conversation should continue.
        """
        continue_conversation = False

        # Configure audio source and sink.
        audio_device = None

        audio_source = audio_device = (
            audio_device or audio_helpers.SoundDeviceStream(
                sample_rate=16000,
                sample_width=2,
                block_size=6400,
                flush_size=25600
            )
        )

        audio_sink = audio_device = (
            audio_device or audio_helpers.SoundDeviceStream(
                sample_rate=16000,
                sample_width=2,
                block_size=6400,
                flush_size=25600
            )
        )
        # Create conversation stream with the given audio source and sink.
        conversation_stream = audio_helpers.ConversationStream(
            source=audio_source,
            sink=audio_sink,
            iter_size=3200,
            sample_width=2,
        )
        
        self.conversation_stream = conversation_stream

        self.conversation_stream.start_recording()
        self.logger.info('Recording audio request.')

        def iter_converse_requests():
            for c in self.gen_converse_requests():
                assistant_helpers.log_converse_request_without_audio(c)
                yield c
            self.conversation_stream.start_playback()

        # This generator yields ConverseResponse proto messages
        # received from the gRPC Google Assistant API.
        for resp in self.assistant.Converse(iter_converse_requests(),
                                            self.deadline):
            assistant_helpers.log_converse_response_without_audio(resp)

            if resp.error.code != code_pb2.OK:
                self.logger.error('server error: %s', resp.error.message)
                break
            if resp.event_type == END_OF_UTTERANCE:
                self.logger.info('End of audio request detected')
                self.conversation_stream.stop_recording()
            if resp.result.spoken_request_text:
                self.logger.info('Transcript of user request: "%s".',
                             resp.result.spoken_request_text)
                playstandard, self.quiet = labwork(resp.result.spoken_request_text, self.quiet, self.conversation_stream)
                # playstandard = True
                if playstandard:
                    self.logger.info('Playing assistant response.')

            if len(resp.audio_out.audio_data) > 0 and playstandard and not self.quiet:
                self.conversation_stream.write(resp.audio_out.audio_data)
            # if resp.result.spoken_response_text:
            #     self.logger.info(
            #         'Transcript of TTS response '
            #         '(only populated from IFTTT): "%s".',
            #         resp.result.spoken_response_text)
            if resp.result.conversation_state:
                self.conversation_state = resp.result.conversation_state
            if resp.result.volume_percentage != 0:
                self.conversation_stream.volume_percentage = (
                    resp.result.volume_percentage
                )
            if resp.result.microphone_mode == DIALOG_FOLLOW_ON:
                continue_conversation = True
                self.logger.info('Expecting follow-on query from user.')
            elif resp.result.microphone_mode == CLOSE_MICROPHONE:
                continue_conversation = False
        self.logger.info('Finished response.')
        self.conversation_stream.stop_playback()
        try:
            self.conversation_stream.close()
        except:
            self.logger.error("Cant close conversation stream")
        return continue_conversation

    def gen_converse_requests(self):
        """Yields: ConverseRequest messages to send to the API."""

        converse_state = None
        if self.conversation_state:
            self.logger.debug('Sending converse_state: %s',
                          self.conversation_state)
            converse_state = embedded_assistant_pb2.ConverseState(
                conversation_state=self.conversation_state,
            )
        config = embedded_assistant_pb2.ConverseConfig(
            audio_in_config=embedded_assistant_pb2.AudioInConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
            ),
            audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
                volume_percentage=self.conversation_stream.volume_percentage,
            ),
            converse_state=converse_state
        )
        # The first ConverseRequest must contain the ConverseConfig
        # and no audio data.
        yield embedded_assistant_pb2.ConverseRequest(config=config)
        for data in self.conversation_stream:
            # Subsequent requests need audio data, but not config.
            yield embedded_assistant_pb2.ConverseRequest(audio_in=data)

def testCallback():
    logger = logging.getLogger("fermi")
    logger.info('Hi! Speak friend.')

def fermiCallback():
    detector.terminate()
##    os.system('mplayer resources/dong.wav')
    assistant.converse()
    detector.start(detected_callback=callback_to_use, interrupt_check=interrupt_callback,sleep_time=0.03)


# Setup logger.
logging.basicConfig()
logger = logging.getLogger("fermi")
if verbose:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

signal.signal(signal.SIGINT, signal_handler)

# Setup the serial connection to the keyboard
ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, rtscts=True)
serio = io.TextIOWrapper(io.BufferedRWPair(ser,ser,1), newline='\r\n', line_buffering=True)

# Setup the switchmate
switch = switchmate.Switch()

# Start listening with snowboy
detector = snowboydecoder.HotwordDetector(model, sensitivity=0.6)
print('Listening... Press Ctrl+C to exit')

# Load OAuth 2.0 credentials.
try:
    with open(credentials, 'r') as f:
        credentials = google.oauth2.credentials.Credentials(token=None,
                                                            **json.load(f))
        http_request = google.auth.transport.requests.Request()
        credentials.refresh(http_request)
except Exception as e:
    logger.error('Error loading credentials: %s', e)
    logger.error('Run google-oauthlib-tool to initialize '
                  'new OAuth 2.0 credentials.')

# Create an authorized gRPC channel.
grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
    credentials, http_request, api_endpoint)
logger.info('Connecting to %s', api_endpoint)

# Make the assistant and callback
assistant = FermiAssistant(grpc_channel, grpc_deadline)
callback_to_use = fermiCallback

# main loop
detector.start(detected_callback=callback_to_use, interrupt_check=interrupt_callback,sleep_time=0.03)

detector.terminate()

