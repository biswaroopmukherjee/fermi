
###########################################################
#
# fermi_assistant: A wrapper for google cloud speech
#  Based on the standard google assistant api example
#
# 2017
# Biswaroop Mukherjee
#
###########################################################

# Other Imports
import json
import logging
import click
import os
from tenacity import retry, stop_after_attempt, retry_if_exception

# Google helpers
import lab.speech.assistant_helpers as assistant_helpers
import lab.speech.audio_helpers as audio_helpers
import lab.speech.browser_helpers as browser_helpers
import lab.speech.device_helpers as device_helpers

# imports for google assistant
import grpc
import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials

from google.assistant.embedded.v1alpha2 import (
    embedded_assistant_pb2,
    embedded_assistant_pb2_grpc
)


# Initialization
END_OF_UTTERANCE = embedded_assistant_pb2.AssistResponse.END_OF_UTTERANCE
DIALOG_FOLLOW_ON = embedded_assistant_pb2.DialogStateOut.DIALOG_FOLLOW_ON
CLOSE_MICROPHONE = embedded_assistant_pb2.DialogStateOut.CLOSE_MICROPHONE
PLAYING = embedded_assistant_pb2.ScreenOutConfig.PLAYING

api_endpoint = 'embeddedassistant.googleapis.com'
grpc_deadline = 60 * 3 + 5


class FermiAssistant(object):
    """Fermi Assistant class

    Args:
      device_model_id: identifier of the device model.
      device_id: identifier of the registered device instance.
      conversation_stream(ConversationStream): audio stream
        for recording query and playing back assistant answer.
      channel: authorized gRPC channel for connection to the
        Google Assistant API.
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
      device_handler: callback for device actions..
    """

    def __init__(self, lab, language_code='en-US', deadline_sec=grpc_deadline):

        self.conversation_state = None

        # Create Google Assistant API gRPC client.
        self.deadline = deadline_sec
        self.logger = logging.getLogger("fermi")
        self.quiet = True
        self.language_code = language_code

        # Define the labwork
        self.lab = lab


        # Load OAuth 2.0 credentials.
        credentials = os.path.join(click.get_app_dir('google-oauthlib-tool'),
                                   'credentials.json')
        try:
            with open(credentials, 'r') as f:
                credentials = google.oauth2.credentials.Credentials(token=None,
                                                                    **json.load(f))
                http_request = google.auth.transport.requests.Request()
                credentials.refresh(http_request)
        except Exception as e:
            logging.error('Error loading credentials: %s', e)
            logging.error('Run google-oauthlib-tool to initialize '
                          'new OAuth 2.0 credentials.')
            sys.exit(-1)
            
        # Opaque blob provided in AssistResponse that,
        # when provided in a follow-up AssistRequest,
        # gives the Assistant a context marker within the current state
        # of the multi-Assist()-RPC "conversation".
        # This value, along with MicrophoneMode, supports a more natural
        # "conversation" with the Assistant.
        self.conversation_state = None
        # Force reset of first conversation.
        self.is_new_conversation = True
    
        # Create an authorized gRPC channel.
        grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
            credentials, http_request, api_endpoint)
        self.logger.info('Connecting to %s', api_endpoint)
    
        self.assistant = embedded_assistant_pb2_grpc.EmbeddedAssistantStub(grpc_channel)



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
    def assist(self):
        """Send a voice request to the Assistant and playback the response.

        Returns: True if conversation should continue.
        """
        continue_conversation = False
        device_actions_futures = []

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
        
        # Get the device id and device model id
        device_config = os.path.join(
                  click.get_app_dir('googlesamples-assistant'),
                  'device_config.json')
        try:
            with open(device_config) as f:
                self.device = json.load(f)
                self.device_id = self.device['id']
                self.device_model_id = self.device['model_id']
                logging.info("Using device model %s and device id %s",
                             self.device_model_id,
                             self.device_id)
        except Exception as e:
            logging.warning('Device config not found: %s' % e)
            logging.warning('Please re run the google assistant configuration and register the device using the samples provided')

        self.device_handler = device_helpers.DeviceRequestHandler(self.device_id)



        self.conversation_stream.start_recording()
        self.logger.info('Recording audio request.')
        
        def iter_log_assist_requests():
            for c in self.gen_assist_requests():
                assistant_helpers.log_assist_request_without_audio(c)
                yield c
            logging.debug('Reached end of AssistRequest iteration.')

        # This generator yields AssistResponse proto messages
        # received from the gRPC Google Assistant API.
        for resp in self.assistant.Assist(iter_log_assist_requests(), self.deadline):
            assistant_helpers.log_assist_response_without_audio(resp)

            if resp.event_type == END_OF_UTTERANCE:
                self.logger.info('End of audio request detected')
                logging.info('Stopping recording.')
                self.conversation_stream.stop_recording()
            if resp.speech_results:
                self.logger.info('Transcript of user request: "%s".',
                             ' '.join(r.transcript
                                      for r in resp.speech_results))
                if resp.speech_results[0].stability==1.0:
                    spoken_text = resp.speech_results[0].transcript
                    playstandard, self.quiet = self.lab.work(spoken_text, self.quiet, self.conversation_stream)
                    #playstandard = True
                    if playstandard:
                        self.logger.info('Playing assistant response.')

                    if len(resp.audio_out.audio_data) > 0 and playstandard and not self.quiet:
                        if not self.conversation_stream.playing:
                            self.conversation_stream.stop_recording()
                            self.conversation_stream.start_playback()
                        self.conversation_stream.write(resp.audio_out.audio_data)
                    
                
            if resp.dialog_state_out.conversation_state:
                conversation_state = resp.dialog_state_out.conversation_state
                logging.debug('Updating conversation state.')
                self.conversation_state = conversation_state
            if resp.dialog_state_out.volume_percentage != 0:
                volume_percentage = resp.dialog_state_out.volume_percentage
                logging.info('Setting volume to %s%%', volume_percentage)
                self.conversation_stream.volume_percentage = volume_percentage
            if resp.dialog_state_out.microphone_mode == DIALOG_FOLLOW_ON:
                continue_conversation = True
                logging.info('Expecting follow-on query from user.')
            elif resp.dialog_state_out.microphone_mode == CLOSE_MICROPHONE:
                continue_conversation = False
            if resp.device_action.device_request_json:
                device_request = json.loads(
                    resp.device_action.device_request_json
                )
                fs = self.device_handler(device_request)
                if fs:
                    device_actions_futures.extend(fs)
                    
        self.logger.info('Finished response.')
        self.conversation_stream.stop_playback()
        try:
            self.conversation_stream.close()
        except:
            self.logger.error("Cant close conversation stream")
        return continue_conversation

    def gen_assist_requests(self):
        """Yields: AssistRequest messages to send to the API."""

        config = embedded_assistant_pb2.AssistConfig(
            audio_in_config=embedded_assistant_pb2.AudioInConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
            ),
            audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                encoding='LINEAR16',
                sample_rate_hertz=self.conversation_stream.sample_rate,
                volume_percentage=self.conversation_stream.volume_percentage,
            ),
            dialog_state_in=embedded_assistant_pb2.DialogStateIn(
                language_code=self.language_code,
                conversation_state=self.conversation_state,
                is_new_conversation=self.is_new_conversation,
            ),
            device_config=embedded_assistant_pb2.DeviceConfig(
                device_id=self.device_id,
                device_model_id=self.device_model_id,
            )
        )
        # Continue current conversation with later requests.
        self.is_new_conversation = False
        # The first AssistRequest must contain the AssistConfig
        # and no audio data.
        yield embedded_assistant_pb2.AssistRequest(config=config)
        for data in self.conversation_stream:
            # Subsequent requests need audio data, but not config.
            yield embedded_assistant_pb2.AssistRequest(audio_in=data)
