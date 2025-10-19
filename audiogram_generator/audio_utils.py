"""
Utilità per scaricare e processare audio
"""
import os
import ssl
import urllib.request
from pydub import AudioSegment


def download_audio(url, output_path):
    """Scarica un file audio da URL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, context=ssl_context) as response:
        with open(output_path, 'wb') as f:
            f.write(response.read())


def extract_audio_segment(audio_path, start_time, duration, output_path):
    """
    Estrae un segmento audio da un file

    Args:
        audio_path: Percorso del file audio completo
        start_time: Tempo di inizio in secondi
        duration: Durata del segmento in secondi
        output_path: Percorso del file di output
    """
    audio = AudioSegment.from_file(audio_path)

    start_ms = int(float(start_time) * 1000)
    end_ms = start_ms + int(float(duration) * 1000)

    segment = audio[start_ms:end_ms]
    segment.export(output_path, format="mp3")

    return output_path
