
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
from tenacity import retry, stop_after_attempt, retry_if_exception

# Google helpers
import lab.speech.assistant_helpers as assistant_helpers
import lab.speech.audio_helpers as audio_helpers

# imports for google assistant
import grpc
import google.auth.transport.grpc
import google.auth.transport.requests
import google.oauth2.credentials

from google.assistant.embedded.v1alpha1 import embedded_assistant_pb2
from google.rpc import code_pb2


# Initialization
END_OF_UTTERANCE = embedded_assistant_pb2.ConverseResponse.END_OF_UTTERANCE
DIALOG_FOLLOW_ON = embedded_assistant_pb2.ConverseResult.DIALOG_FOLLOW_ON
CLOSE_MICROPHONE = embedded_assistant_pb2.ConverseResult.CLOSE_MICROPHONE

api_endpoint = 'embeddedassistant.googleapis.com'
credentials = '/home/pi/.config/google-oauthlib-tool/credentials.json'
grpc_deadline = 60 * 3 + 5


class FermiAssistant(object):
    """Fermi Assistant class

    Args:
      deadline_sec: gRPC deadline in seconds for Google Assistant API call.
    """

    def __init__(self, lab, deadline_sec=grpc_deadline):

        self.conversation_state = None

        # Create Google Assistant API gRPC client.
        self.deadline = deadline_sec
        self.logger = logging.getLogger("fermi")
        self.quiet = False

        # Define the labwork
        self.lab = lab

        # Load OAuth 2.0 credentials.
        try:
            with open(credentials, 'r') as f:
                credentials = google.oauth2.credentials.Credentials(token=None,
                                                                    **json.load(f))
                http_request = google.auth.transport.requests.Request()
                credentials.refresh(http_request)
        except Exception as e:
            self.logger.error('Error loading credentials: %s', e)
            self.logger.error('Run google-oauthlib-tool to initialize '
                          'new OAuth 2.0 credentials.')

        # Create an authorized gRPC channel.
        grpc_channel = google.auth.transport.grpc.secure_authorized_channel(
            credentials, http_request, api_endpoint)
        self.logger.info('Connecting to %s', api_endpoint)

        self.assistant = embedded_assistant_pb2.EmbeddedAssistantStub(grpc_channel)



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
                playstandard, self.quiet = self.lab.work(resp.result.spoken_request_text, self.quiet, self.conversation_stream)
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
