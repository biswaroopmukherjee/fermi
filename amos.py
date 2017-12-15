from google.assistant.embedded.v1alpha1 import embedded_assistant_pb2
from google.rpc import code_pb2
from pync import Notifier

import subprocess
import logging
import os
import sys
import json
import snowboydecoder
import sys
import signal
import time



interrupted = False
start_stop = True

def signal_handler(signal, frame):
    global interrupted
    interrupted = True


def interrupt_callback():
    global interrupted
    return interrupted

def assistant2():
    global detect
    detect.terminate()
    time.sleep(1)
    global amos
    amos = False

    logging.basicConfig(level=logging.INFO)
    api_endpoint = 'embeddedassistant.googleapis.com'
    # Load credentials.
    try:
        creds = auth_helpers.load_credentials("credentials.json", scopes=[common_settings.ASSISTANT_OAUTH_SCOPE])
    except Exception as e:
        logging.error('Error loading credentials: %s', e)
        logging.error('Run auth_helpers to initialize new OAuth2 credentials.')
        return

    grpc_channel = auth_helpers.create_grpc_channel(api_endpoint, creds)
    logging.info('Connecting to %s', api_endpoint)


    assistant = embedded_assistant_pb2.EmbeddedAssistantStub(grpc_channel)

    audio_source = audio_helpers.SoundDeviceStream(
        sample_rate=16000,
        sample_width=2,
        block_size=6400,
        flush_size=25600
    )

    audio_sink = audio_helpers.SoundDeviceStream(
        sample_rate=16000,
        sample_width=2,
        block_size=6400,
        flush_size=25600
    )

    conversation_stream = audio_helpers.ConversationStream(
        source=audio_source,
        sink=audio_sink,
        sample_width=2,
        iter_size=3200
    )

    conversation_state_bytes = None

    wait_for_user_trigger = False
    keep_running = True

    while keep_running:
        def gen_converse_requests():
            converse_state = None
            if conversation_state_bytes:
                    converse_state = embedded_assistant_pb2.ConverseState(
                    conversation_state=conversation_state_bytes,
                )
            config = embedded_assistant_pb2.ConverseConfig(
                audio_in_config=embedded_assistant_pb2.AudioInConfig(
                    encoding='LINEAR16',
                    sample_rate_hertz=16000
                ),
                audio_out_config=embedded_assistant_pb2.AudioOutConfig(
                    encoding='LINEAR16',
                    sample_rate_hertz=16000,
                    volume_percentage=75
                ),
                converse_state=converse_state
            )
            yield embedded_assistant_pb2.ConverseRequest(config=config)
            for data in conversation_stream:
                yield embedded_assistant_pb2.ConverseRequest(audio_in=data)

        def iter_converse_requests():
            for c in gen_converse_requests():
                assistant_helpers.log_converse_request_without_audio(c)
                yield c
            conversation_stream.start_playback()

        
      #   os.system('google_speech "Yes Cevat"')
        conversation_stream.start_recording()
        for resp in assistant.Converse(iter_converse_requests(), 185):
            assistant_helpers.log_converse_response_without_audio(resp)
            if resp.error.code != code_pb2.OK:
                Notifier.notify('server error: %s' % resp.error.message)
                break
            if resp.event_type == embedded_assistant_pb2.ConverseResponse.END_OF_UTTERANCE:
                Notifier.notify('End of audio request detected')
                conversation_stream.stop_recording()
            if resp.result.spoken_request_text:
                Notifier.notify(resp.result.spoken_request_text)
                apiairequest(resp.result.spoken_request_text)
                if amos: #let the custom assistant handle it
                    break #break here so it doesn't play the voice response if amos is handling it 
            if len(resp.audio_out.audio_data) > 0:
                conversation_stream.write(resp.audio_out.audio_data)

            if resp.result.conversation_state:
                conversation_state_bytes = resp.result.conversation_state

            if resp.result.volume_percentage != 0:
                Notifier.notify('Volume','Volume','Volume should be set to %s%%' % resp.result.volume_percentage)

            if resp.result.microphone_mode == embedded_assistant_pb2.ConverseResult.DIALOG_FOLLOW_ON:
                wait_for_user_trigger = False
                Notifier.notify('Expecting follow-on query from user.')

            elif resp.result.microphone_mode == embedded_assistant_pb2.ConverseResult.CLOSE_MICROPHONE:
                wait_for_user_trigger = True
                keep_running = False

        Notifier.notify('Finished playing assistant response.')
        conversation_stream.stop_playback()
        keep_running = False

    conversation_stream.close()
    detect = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
    detect.start(detected_callback=[lambda: assistant2()],
                      interrupt_check=interrupt_callback,
                      sleep_time=0.05) 

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Error: need to specify model name")
        print("Usage: python demo.py your.model")
        sys.exit(-1)

    model = sys.argv[1]

# capture SIGINT signal, e.g., Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    detect = snowboydecoder.HotwordDetector(model, sensitivity=0.4)
    print('Listening... Press Ctrl+C to exit')

# main loop
    detect.start(detected_callback=assistant2,
                    interrupt_check=interrupt_callback, sleep_time=0.05) 
