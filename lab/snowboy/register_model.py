import sys
import base64
import requests
import os
import subprocess
import click
import time


def get_wave(fname):
    with open(fname, 'rb') as infile:
        return str(base64.b64encode(infile.read()),'ascii', 'ignore')



@click.command()
@click.option('--name',
              metavar='<name>', show_default=True,
              default='biswaroop',
              help='Name for the new hotword user.')
@click.option('--gender',
              metavar='<gender>', show_default=True,
              default='M',
              help='Gender of person recording.')
@click.option('--age_group',
              metavar='<age_group>', show_default=True,
              default='20_29',
              help='Age group of person recording')
@click.option('--duration',
              metavar='<duration>', show_default=True,
              default='3',
              help='Duration for the hotword recording.')
@click.option('--norecord', is_flag=True, help='flag to just send files')
    



def main(name, duration, age_group, gender, norecord):
    
    hotword_name = "Fermi3"+name
    language = "en"
    microphone = "macbook microphone"
    
    fname = 'resources/snowboy_api_config.txt'
    f = open(fname,'r')
    endpoint = "https://snowboy.kitt.ai/api/v1/train/"
    token = f.read()
    
    if not norecord:
        print('New hotword model for ' + name +  ' with duration '+ str(duration) + ' seconds')
        input("Press Enter to start the first recording...")
        time.sleep(0.2)
        subprocess.call('rec -r 16000 -c 1 -b 16 -e signed-integer resources/Fermi3_'+name+'_1.wav trim 0 '+str(duration), shell=True)
        input("Press Enter to start the second recording...")
        time.sleep(0.2)
        subprocess.call('rec -r 16000 -c 1 -b 16 -e signed-integer resources/Fermi3_'+name+'_2.wav trim 0 '+str(duration), shell=True)
        input("Press Enter to start the third recording...")
        time.sleep(0.2)
        subprocess.call('rec -r 16000 -c 1 -b 16 -e signed-integer resources/Fermi3_'+name+'_3.wav trim 0 '+str(duration), shell=True)
    
    print('Sending to server...')
    
    wav1 = 'resources/Fermi3_'+name+'_1.wav'
    wav2 = 'resources/Fermi3_'+name+'_2.wav'
    wav3 = 'resources/Fermi3_'+name+'_3.wav'
    out  = 'saved_model_Fermi3_'+name+'.pmdl'
    
    data = { 
        "name": hotword_name,
        "language": language,
        "age_group": age_group,
        "gender": gender,
        "microphone": microphone,
        "token": token,
        "voice_samples": [
            {"wave": get_wave(wav1)},
            {"wave": get_wave(wav2)},
            {"wave": get_wave(wav3)}
        ]
    }

    response = requests.post(endpoint, json=data)
    if response.ok:
        with open(os.path.join('resources',out), "wb") as outfile:
            outfile.write(response.content)
        print("Saved model to '%s'." % out)
    else:
        print("Request failed.")
        print(response.text)




if __name__ == '__main__':
    main()