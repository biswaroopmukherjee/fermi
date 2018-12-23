from gtts import gTTS
import os 

mytext = "Turning off room lights. The archive reads quantum entanglement. Turning on lithium."

myobj = gTTS(text=mytext, lang='en', slow=False)
myobj.save("text.mp3")
os.system("sox text.mp3 -r 32000 text_r.mp3")
os.system("cvlc --play-and-exit text_r.mp3")
