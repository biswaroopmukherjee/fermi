import speech_recognition as sr
import snowboydecoder
import sys
import signal

def callback(recognizer, audio):                          # this is called from the background thread
    try:
        print("You said " + recognizer.recognize_google(audio))  # received audio data, now need to recognize it
    except LookupError:
        print("Oops! Didn't catch that")

r = sr.Recognizer()
r.listen_in_background(sr.Microphone(), callback)

import time
while True: time.sleep(0.1)                         # we're still listening even though the main thread is blocked
#
#
# interrupted = False
#
#
# def signal_handler(signal, frame):
#     global interrupted
#     interrupted = True
#
#
# def interrupt_callback():
#     global interrupted
#     return interrupted
#
# if len(sys.argv) == 1:
#     print("Error: need to specify model name")
#     print("Usage: python demo.py your.model")
#     sys.exit(-1)
#
# def blah():
#     # snowboydecoder.play_audio_file()
#     # Record Audio
#     print('say something')
#     r = sr.Recognizer()
#     with sr.Microphone() as source:
#         print("Say something!")
#         audio = r.listen(source)
#
#     # Speech recognition using Google Speech Recognition
#     try:
#         # for testing purposes, we're just using the default API key
#         # to use another API key, use `r.recognize_google(audio, key="GOOGLE_SPEECH_RECOGNITION_API_KEY")`
#         # instead of `r.recognize_google(audio)`
#         print("You said: " + r.recognize_google(audio))
#     except sr.UnknownValueError:
#         print("Google Speech Recognition could not understand audio")
#     except sr.RequestError as e:
#         print("Could not request results from Google Speech Recognition service; {0}".format(e))
#
#
#
#
# model = sys.argv[1]
#
# # capture SIGINT signal, e.g., Ctrl+C
# signal.signal(signal.SIGINT, signal_handler)
#
# detector = snowboydecoder.HotwordDetector(model, sensitivity=0.5)
# print('Listening... Press Ctrl+C to exit')
#
# # main loop
# detector.start(detected_callback=blah,
#                interrupt_check=interrupt_callback,
#                sleep_time=0.03)
#
# detector.terminate()
