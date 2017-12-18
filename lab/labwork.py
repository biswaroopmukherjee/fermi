
##################################################
#
# Labwork: a lab device manager and NLP handler
#
# 2017
# Biswaroop Mukherjee
#
##################################################

import logging
from lab.devices.arxiv_reader import Reader
from lab.devices.BLE_keyboard import Keyboard
from lab.devices.switchmate import Switch
from lab.devices.tts import TTS

class Lab(object):
    """ The Lab. This should contain all lab devices, and perform first layer NLP
    - keyboards
    - switches
    - text to speech for scripted responses
    """
    def __init__(self, name):
        self.keyboard = Keyboard()
        self.switch = Switch()
        self.logger = logging.getLogger("fermi")

    # NLP preprocessor for lab related stuff. If this fails, fall back on google
    def work(self, text, quiet, conversation_stream):
        ''' Very hacky NLP on the text blob '''
        playstandard = False
        quietout = quiet
        text = text.lower()
        words = re.split(' ', text)
        speaker = TTS(conversation_stream)
        if 'listen' in words: words = words + ['lithium']
        if 'soda' in words: words = words + ['sodium']
        if 'trap' in words or ('pumping' not in words and 'imaging' not in words and ('sodium' in words or 'lithium' in words)):
            if 'lithium' in words:
                self.logger.info('CTRL-L')
                if not quiet: speaker.speaktext('Turning on lithium mott')
                self.keyboard.keysend('L', 'Ctrl')
            elif 'sodium' in words:
                if not quiet: speaker.speaktext('Turning on sodium mott')
                self.logger.info('CTRL-N')
                self.keyboard.keysend('N', 'Ctrl')
            else:
                if not quiet: speaker.speaktext('Please specify the atom.')
                 # need to make it more conversational: Sodium or lithium? Context needed
                self.logger.info('unknown atom')
        elif 'pumping' in words:
            if 'lithium' in words:
                if not quiet: speaker.speaktext('Turning on lithium pumping')
                self.logger.info('CTRL-P')
                self.keyboard.keysend('P', 'Ctrl')
            elif 'sodium' in words:
                if not quiet: speaker.speaktext('Turning on sodium pumping')
                self.logger.info('CTRL-Q')
                self.keyboard.keysend('Q', 'Ctrl')
            else:
                if not quiet: speaker.speaktext('Please specify the atom')
                self.logger.info('unknown atom')
        elif 'imaging' in words:
            if not quiet: speaker.speaktext('Turning on imaging')
            self.logger.info('CTRL-I')
            self.keyboard.keysend('I', 'Ctrl')
        elif 'abort' in words or 'escape' in words:
            if not quiet: speaker.speaktext('Aborting')
            self.logger.info('esc')
            self.keyboard.keysend('escape')
        elif 'run' in words or 'running' in words or 'sequence' in words and 'trap' not in words:
            if 'list' in words or 'twelve' in words:
                if not quiet: speaker.speaktext('Running list')
                self.logger.info('F12')
                self.keyboard.keysend('F12')
            elif 'background' in words:
                if not quiet: speaker.speaktext('Running in background')
                self.logger.info('CTRL-F9')
                self.keyboard.keysend('F9')
            else:
                if not quiet: speaker.speaktext('Running sequence')
                self.logger.info('F9')
                self.keyboard.keysend('F9')
        elif 'stop' in words or 'control' in words or 'nothing' in words:
            if not quiet: speaker.speaktext('Okay. Doing nothing.')
            self.logger.info('CTRL-Z')
            self.keyboard.keysend('Z', 'Ctrl')
        elif 'lights' in words or 'room' in words:
            try:
                if 'off' in words:
                    if not quiet: speaker.speaktext('Turning off room lights.')
                    self.switch.turn_off()
                else:
                    if not quiet: speaker.speaktext('Turning on room lights.')
                    self.switch.turn_on()
            except:
                self.logger.debug('well I need to fix this error')
        elif 'quiet' in words or 'shut' in words:
            quietout = True
            self.logger.info('turning off text to speech')
        elif 'stupid' in words:
            self.logger.info('theyre being mean')
            if not quiet: speaker.speaktext("I'm doing my best. Please try not to be mean to me.")
        elif 'speak' in words or 'speaking' in words:
            quietout = False
            if quiet: speaker.speaktext("Thank you. I've been dying to talk.")
            else: speaker.speaktext("Thank you, but I can already talk.")
            self.logger.info('turning on text to speech')
        elif 'name' in words:
            if not quiet: speaker.speaktext('why')
            self.logger.info('why')
        elif 'why' in words:
            if not quiet: speaker.speaktext('Because you told me so.')
            self.logger.info('Classic matlab')
        elif 'igor' in words:
            if not quiet: speaker.speaktext('Igor? I prefer python.')
        elif 'morning' in words:
            if not quiet: speaker.speaktext('Good morning!')
        elif 'papers' in words or 'paper' in words or 'archive' in words:
            self.logger.info('checking the arxiv')
            if not quiet: speaker.speaktext("Hold on while I check the archive.")
            reader = Reader(detailed=True)
            try:
                self.reader.download_info()
            except:
                if not quiet: speaker.speaktext("Sorry. I couldn't connect to the archive")
                self.logger.error('Cant connect or download the interest list')
            try:
                text_to_say = self.reader.read_arxiv()
                if not quiet: speaker.speaktext(text_to_say)
                self.logger.info(text_to_say)
            except:
                if not quiet: speaker.speaktext("I'm sorry. I can't do that right now.")
                self.logger.error('Cant read the arxiv')
        elif 'pod' in words or 'bay' in words or 'door' in words:
            if not quiet: speaker.speaktext("I'm sorry Dave. I'm afraid I can't do that")
            self.logger.info('Hal')
        else:
            # Run standard google response
            # speaker.speaktext("Sorry I didn't understand that.")
            playstandard = True
        return playstandard, quietout
