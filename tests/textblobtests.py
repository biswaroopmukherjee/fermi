from textblob import TextBlob
# from gtts import gTTS
# tts = gTTS(text='Hello I will say this text', lang='en', slow=False)
# tts.save("hello.mp3")


text = 'Turn on lithium MOT'

blob = TextBlob(text)
# blob.tags           # [('The', 'DT'), ('titular', 'JJ'),
#                     #  ('threat', 'NN'), ('of', 'IN'), ...]
#
# blob.noun_phrases   # WordList(['titular threat', 'blob',
#                     #            'ultimate movie monster',
#                     #            'amoeba-like mass', ...])

print(blob.tags)
