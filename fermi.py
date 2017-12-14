# Fermi: a voice controlled lab computer controller
#
# 2017
# Biswaroop Mukherjee


# Imports

# imports for snowboy
import snowboydecoder
import sys
import signal

import json
import logging
import os
import re
import click
from gtts import gTTS

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

interrupted = False
start_stop = True

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
def speaktext(mytext):
    """ Use by typing speaktext('textstring') """
    if not quiet:
        myobj = gTTS(text=mytext, lang='en-us', slow=False)
        myobj.save("text.mp3")
        # Play the converted file
        os.system("mpg321 text.mp3 -q")



# Functions for the keyboard
def errorhandler(err, exitonerror=True):
    """Display an error message and exit gracefully on errors from the serial"""
    logger.error("ERROR: " + err.message)
    if exitonerror:
        ser.close()
        sys.exit(-3)

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
def labwork(text):
    ''' Very hacky NLP on the text blob '''
    playstandard = False
    logger = logging.getLogger("fermi")
    text = text.lower()
    words = re.split(' ', text)
    if 'listen' in words: words = words + ['lithium']
    if 'soda' in words: words = words + ['sodium']
    if 'trap' in words or ('pumping' not in words and 'imaging' not in words and ('sodium' in words or 'lithium' in words)):
        if 'lithium' in words:
            logger.info('CTRL-L')
            speaktext('Turning on lithium mott')
            keysend('L', 'Ctrl')
        elif 'sodium' in words:
            speaktext('Turning on sodium mott')
            logger.info('CTRL-N')
            keysend('N', 'Ctrl')
        else:
            speaktext('Please specify the atom.')
             # need to make it more conversational: Sodium or lithium? Context needed
            logger.info('unknown atom')
    elif 'pumping' in words:
        if 'lithium' in words:
            speaktext('Turning on lithium pumping')
            logger.info('CTRL-P')
            keysend('P', 'Ctrl')
        elif 'sodium' in words:
            speaktext('Turning on sodium pumping')
            logger.info('CTRL-Q')
            keysend('Q', 'Ctrl')
        else:
            speaktext('Please specify the atom')
            logger.info('unknown atom')
    elif 'imaging' in words:
        speaktext('Turning on imaging')
        logger.info('CTRL-I')
        keysend('I', 'Ctrl')
    elif 'abort' in words:
        speaktext('Aborting')
        logger.info('esc')
        keysend('escape')
    elif 'run' in words or 'running' in words and 'trap' not in words:
        if 'list' in words:
            speaktext('Running list')
            logger.info('F12')
            keysend('F12')
        elif 'background' in words:
            speaktext('Running in background')
            logger.info('CTRL-F9')
            keysend('F9')
        else:
            speaktext('Running sequence')
            logger.info('F9')
            keysend('F9')
    elif 'stop' in words or 'control' in words or 'nothing' in words:
        speaktext('Okay. Doing nothing.')
        logger.info('CTRL-Z')
        keysend('Z', 'Ctrl')
    elif 'lights' in words or 'room' in words:
        try:
            if 'off' in words:
                speaktext('Turning off room lights.')
                switch.turn_off()
            else:
                speaktext('Turning on room lights.')
                switch.turn_on()
        except:
            speaktext("I'm sorry. I can't connect to the light switch right now.")
            logger.error('Cant talk to the switchmate')
    elif 'quiet' in words or 'shut' in words:
        quiet = True
        logger.info('turning off text to speech')
    elif 'stupid' in words:
        logger.info('theyre being mean')
        speaktext("I'm doing my best. Please try not to be mean to me.")
    elif 'speak' in words or 'speaking' in words:
        quiet = False
        speaktext("Thank you. I've been dying to talk.")
        logger.info('turning off text to speech')
    elif 'name' in words:
        speaktext('why')
        logger.info('why')
    elif 'why' in words:
        speaktext('Because you told me so.')
        logger.info('Classic matlab')
    elif 'igor' in words:
        speaktext('Igor? I prefer python.')
    elif 'morning' in words:
        speaktext('Good morning!')
    elif 'papers' in words or 'paper' in words or 'archive' in words:
        logger.info('checking the arxiv')
        speaktext("Hold on while I check the archive.')
        reader = Reader(detailed=True)
        try:
            reader.download_info()
        except:
            speaktext("Sorry. I couldn't connect to the archive")
            logger.error('Cant connect or download the interest list')
        try:
            text_to_say = reader.read_arxiv()
            speaktext(text_to_say)
        except:
            speaktext("I'm sorry. I can't do that right now.")
            logger.error('Cant read the arxiv')
    else:
        # Run standard google response
        # speaktext("Sorry I didn't understand that.")
        playstandard = True
    return playstandard



class FermiAssistant(object):
    """Fermi Assistant class

    Args:
      conversation_stream(ConversationStream): audio stream
        for recording query and playing back assistant answer.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
    """

    def __init__(self, conversation_stream, channel, deadline_sec):
        self.conversation_stream = conversation_stream

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
                playstandard = labwork(resp.result.spoken_request_text)
                # playstandard = True
                if playstandard:
                    self.logger.info('Playing assistant response.')

            if len(resp.audio_out.audio_data) > 0 and playstandard:
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

def testcallback():
    logger = logging.getLogger("fermi")
    logger.info('Hi! Speak friend.')


# Click options for fermi.py
@click.command()
@click.option('--api-endpoint', default=ASSISTANT_API_ENDPOINT,
              metavar='<api endpoint>', show_default=True,
              help='Address of Google Assistant API service.')
@click.option('--credentials',
              metavar='<credentials>', show_default=True,
              default=os.path.join(click.get_app_dir('google-oauthlib-tool'),
                                   'credentials.json'),
              help='Path to read OAuth2 credentials.')
@click.option('--verbose', '-v', is_flag=True, default=False,
              help='Verbose logger.')
@click.option('--input-audio-file', '-i',
              metavar='<input file>',
              help='Path to input audio file. '
              'If missing, uses audio capture')
@click.option('--output-audio-file', '-o',
              metavar='<output file>',
              help='Path to output audio file. '
              'If missing, uses audio playback')
@click.option('--audio-sample-rate',
              default=audio_helpers.DEFAULT_AUDIO_SAMPLE_RATE,
              metavar='<audio sample rate>', show_default=True,
              help='Audio sample rate in hertz.')
@click.option('--audio-sample-width',
              default=audio_helpers.DEFAULT_AUDIO_SAMPLE_WIDTH,
              metavar='<audio sample width>', show_default=True,
              help='Audio sample width in bytes.')
@click.option('--audio-iter-size',
              default=audio_helpers.DEFAULT_AUDIO_ITER_SIZE,
              metavar='<audio iter size>', show_default=True,
              help='Size of each read during audio stream iteration in bytes.')
@click.option('--audio-block-size',
              default=audio_helpers.DEFAULT_AUDIO_DEVICE_BLOCK_SIZE,
              metavar='<audio block size>', show_default=True,
              help=('Block size in bytes for each audio device '
                    'read and write operation..'))
@click.option('--audio-flush-size',
              default=audio_helpers.DEFAULT_AUDIO_DEVICE_FLUSH_SIZE,
              metavar='<audio flush size>', show_default=True,
              help=('Size of silence data in bytes written '
                    'during flush operation'))
@click.option('--grpc-deadline', default=DEFAULT_GRPC_DEADLINE,
              metavar='<grpc deadline>', show_default=True,
              help='gRPC deadline in seconds')
@click.option('--model', default='resources/Fermi 3.pmdl',
        metavar='<snowboy model>', show_default=True,
        help='Snowboy model for hotword')


# Main function.

def main(api_endpoint, credentials, verbose,
         audio_sample_rate, audio_sample_width,
         audio_iter_size, audio_block_size, audio_flush_size,
         grpc_deadline, model, *args, **kwargs):

    """Google assistant main function
    """
    #
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
    detector = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
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
        return

    # Create an authorized gRPC channel.
    grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
        credentials, http_request, api_endpoint)
    logger.info('Connecting to %s', api_endpoint)

    # Configure audio source and sink.
    audio_device = None

    audio_source = audio_device = (
        audio_device or audio_helpers.SoundDeviceStream(
            sample_rate=audio_sample_rate,
            sample_width=audio_sample_width,
            block_size=audio_block_size,
            flush_size=audio_flush_size
        )
    )

    audio_sink = audio_device = (
        audio_device or audio_helpers.SoundDeviceStream(
            sample_rate=audio_sample_rate,
            sample_width=audio_sample_width,
            block_size=audio_block_size,
            flush_size=audio_flush_size
        )
    )
    # Create conversation stream with the given audio source and sink.
    conversation_stream = audio_helpers.ConversationStream(
        source=audio_source,
        sink=audio_sink,
        iter_size=audio_iter_size,
        sample_width=audio_sample_width,
    )

    with FermiAssistant(conversation_stream, grpc_channel, grpc_deadline) as assistant:
        # main loop
        detector.start(detected_callback=assistant.converse,
                    interrupt_check=interrupt_callback,
                    sleep_time=0.03)

        detector.start(detected_callback=testcallback,
                    interrupt_check=interrupt_callback,
                    sleep_time=0.03)

    conversation_stream.close()

    detector.terminate()
    #
    # detect = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
    # detect.start(detected_callback=[lambda: main()],
    #                   interrupt_check=interrupt_callback,
    #                   sleep_time=0.05)

if __name__ == "__main__":
    main()

# detector.terminate()
