
##################################################
#
# TTS: a simple text-to-speech wrapper for gTTS
#
# 2017
# Biswaroop Mukherjee
#
##################################################

import wave
import contextlib
import logging
from gtts import gTTS


# Text to speech class
class TTS(object):
    """ A Text to speech object that works on the Pi3"""

    def __init__(self, conversation_stream):
        self.conversation_stream = conversation_stream

    def speaktext(self, mytext):
        """ Use by typing speaktext('textstring') """
        if not quiet:
            logger = logging.getLogger("fermi")
            myobj = gTTS(text=mytext, lang='en-us', slow=False)
            myobj.save("text.mp3")
            # Needs resampling because the Pi can't output 24kHz
            logger.info("resampling")
            os.system("sox text.mp3 -r 16000 text_r.wav")
            logger.info("resampling successful")
            # Play the converted file
            with contextlib.closing(wave.open("text_r.wav", "r")) as f:
                frames = f.getnframes()
                logger.info(str(frames)+" frames to speak")
                data = f.readframes(frames)
                self.conversation_stream.write(data)
