"""
Generatore di video audiogram
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip
from pydub import AudioSegment
import urllib.request
import ssl


# Formati video per social media
FORMATS = {
    # Verticale 9:16 - Instagram Reels/Stories, YouTube Shorts, TikTok, Twitter
    'vertical': (1080, 1920),
    # Quadrato 1:1 - Instagram Post, Twitter, Mastodon, LinkedIn
    'square': (1080, 1080),
    # Orizzontale 16:9 - YouTube, Twitter orizzontale
    'horizontal': (1920, 1080)
}

# Colori Pensieri in Codice
COLOR_ORANGE = (242, 101, 34)
COLOR_BEIGE = (235, 213, 197)
COLOR_WHITE = (255, 255, 255)
COLOR_BLACK = (50, 50, 50)


def download_image(url, output_path):
    """Scarica un'immagine da URL"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, context=ssl_context) as response:
        with open(output_path, 'wb') as f:
            f.write(response.read())


def get_waveform_data(audio_path, fps=24):
    """
    Estrae dati waveform dall'audio campionati per frame

    Args:
        audio_path: Percorso del file audio
        fps: Frame per secondo del video

    Returns:
        Array di ampiezze per ogni frame del video
    """
    audio = AudioSegment.from_file(audio_path)
    samples = np.array(audio.get_array_of_samples())

    # Normalizza
    if len(samples) > 0:
        samples = samples.astype(float)
        samples = samples / np.max(np.abs(samples))

    # Calcola quanti campioni audio per frame video
    sample_rate = audio.frame_rate
    duration_seconds = len(audio) / 1000.0
    total_frames = int(duration_seconds * fps)
    samples_per_frame = len(samples) // total_frames if total_frames > 0 else len(samples)

    # Estrai ampiezza media per ogni frame
    frame_amplitudes = []
    for i in range(total_frames):
        start = i * samples_per_frame
        end = min(start + samples_per_frame, len(samples))
        if start < len(samples):
            chunk = samples[start:end]
            frame_amplitudes.append(np.abs(chunk).mean())

    return np.array(frame_amplitudes)


def create_audiogram_frame(width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, colors=None):
    """
    Crea un singolo frame dell'audiogram

    Args:
        width, height: Dimensioni del frame
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        waveform_data: Dati della waveform
        current_time: Tempo corrente in secondi
        transcript_chunks: Lista di chunk di trascrizione con timing
        audio_duration: Durata totale dell'audio
        colors: Dizionario con i colori personalizzati (opzionale)
    """
    # Usa colori di default o personalizzati
    if colors is None:
        colors = {
            'primary': COLOR_ORANGE,
            'background': COLOR_BEIGE,
            'text': COLOR_WHITE,
            'transcript_bg': COLOR_BLACK
        }
    else:
        # Converti liste in tuple se necessario
        colors = {
            'primary': tuple(colors.get('primary', COLOR_ORANGE)),
            'background': tuple(colors.get('background', COLOR_BEIGE)),
            'text': tuple(colors.get('text', COLOR_WHITE)),
            'transcript_bg': tuple(colors.get('transcript_bg', COLOR_BLACK))
        }

    # Crea immagine di base
    img = Image.new('RGB', (width, height), colors['background'])
    draw = ImageDraw.Draw(img)

    # Header (15% altezza)
    header_height = int(height * 0.15)
    draw.rectangle([(0, 0), (width, header_height)], fill=colors['primary'])

    # Testo "ASCOLTA" nel header
    try:
        font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(header_height * 0.4))
    except:
        font_header = ImageFont.load_default()

    header_text = "ASCOLTA"
    bbox = draw.textbbox((0, 0), header_text, font=font_header)
    text_width = bbox[2] - bbox[0]
    text_x = (width - text_width) // 2
    text_y = (header_height - (bbox[3] - bbox[1])) // 2
    draw.text((text_x, text_y), header_text, fill=colors['text'], font=font_header)

    # Area centrale (60% altezza)
    central_top = header_height
    central_height = int(height * 0.60)
    central_bottom = central_top + central_height

    # Visualizzatore waveform tipo equalizer che "balla" con l'audio
    if waveform_data is not None and len(waveform_data) > 0:
        # Configurazione bars - usa tutta la larghezza dello schermo
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        # Calcola quante bars entrano nella larghezza
        num_bars = width // total_bar_width
        # Rendi pari per simmetria
        if num_bars % 2 != 0:
            num_bars -= 1

        # Ottieni l'ampiezza corrente dell'audio in questo momento
        frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
        frame_idx = min(frame_idx, len(waveform_data) - 1)
        current_amplitude = waveform_data[frame_idx]

        # Crea pattern simmetrico con variazione casuale ma controllata
        # Ogni bar ha una "sensibilità" diversa alle frequenze
        np.random.seed(42)  # Seed fisso per consistenza tra frame
        sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
        sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])  # Simmetria

        # Disegna le bars da sinistra a destra
        for i in range(num_bars):
            x = i * total_bar_width

            # Calcola altezza bar con pattern simmetrico dal centro
            center_idx = num_bars // 2
            distance_from_center = abs(i - center_idx)

            # Le bars centrali sono più reattive
            center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4

            # Ampiezza finale con sensibilità e boost
            bar_amplitude = current_amplitude * sensitivities[i] * center_boost

            # Altezza minima e massima
            min_height = int(central_height * 0.12)
            max_height = int(central_height * 0.80)
            bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
            bar_height = max(min_height, min(bar_height, max_height))

            # Centra verticalmente
            y_center = central_top + central_height // 2
            y_top = y_center - bar_height // 2
            y_bottom = y_center + bar_height // 2

            # Disegna la bar
            draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast al centro (sopra la waveform)
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width, central_height) * 0.6)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Posizione centrata
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (25% altezza)
    footer_top = central_bottom
    footer_height = height - footer_top
    draw.rectangle([(0, footer_top), (width, height)], fill=colors['primary'])

    # Titolo podcast nel footer
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.15))
        font_episode = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.10))
    except:
        font_title = ImageFont.load_default()
        font_episode = ImageFont.load_default()

    # Podcast title
    bbox = draw.textbbox((0, 0), podcast_title, font=font_title)
    title_width = bbox[2] - bbox[0]
    title_x = (width - title_width) // 2
    title_y = footer_top + int(footer_height * 0.10)
    draw.text((title_x, title_y), podcast_title, fill=colors['text'], font=font_title)

    # Episode title (wrapped)
    episode_y = title_y + int(footer_height * 0.20)
    max_chars = 40
    if len(episode_title) > max_chars:
        words = episode_title.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 <= max_chars:
                current_line += word + " "
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())

        for i, line in enumerate(lines[:3]):  # Max 3 lines
            bbox = draw.textbbox((0, 0), line, font=font_episode)
            line_width = bbox[2] - bbox[0]
            line_x = (width - line_width) // 2
            line_y = episode_y + i * int(footer_height * 0.12)
            draw.text((line_x, line_y), line, fill=colors['text'], font=font_episode)
    else:
        bbox = draw.textbbox((0, 0), episode_title, font=font_episode)
        ep_width = bbox[2] - bbox[0]
        ep_x = (width - ep_width) // 2
        draw.text((ep_x, episode_y), episode_title, fill=colors['text'], font=font_episode)

    # Trascrizione in tempo reale (sopra il footer, nell'area centrale bassa)
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.025))
            except:
                font_transcript = ImageFont.load_default()

            # Box per la trascrizione
            transcript_y = central_bottom - int(central_height * 0.15)
            max_width = int(width * 0.85)

            # Word wrap
            words = current_text.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + word + " "
                bbox = draw.textbbox((0, 0), test_line, font=font_transcript)
                if bbox[2] - bbox[0] <= max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line.strip())
                    current_line = word + " "
            if current_line:
                lines.append(current_line.strip())

            # Disegna background semi-trasparente per leggibilità
            for i, line in enumerate(lines[:2]):  # Max 2 lines
                bbox = draw.textbbox((0, 0), line, font=font_transcript)
                line_width = bbox[2] - bbox[0]
                line_height = bbox[3] - bbox[1]
                line_x = (width - line_width) // 2
                line_y = transcript_y + i * (line_height + 5)

                # Background
                padding = 10
                bg_color = colors['transcript_bg'] + (180,) if len(colors['transcript_bg']) == 3 else colors['transcript_bg']
                draw.rectangle([
                    (line_x - padding, line_y - padding),
                    (line_x + line_width + padding, line_y + line_height + padding)
                ], fill=bg_color)

                draw.text((line_x, line_y), line, fill=colors['text'], font=font_transcript)

    return np.array(img)


def generate_audiogram(audio_path, output_path, format_name, podcast_logo_path,
                      podcast_title, episode_title, transcript_chunks, duration,
                      formats=None, colors=None):
    """
    Genera un video audiogram completo

    Args:
        audio_path: Percorso del file audio
        output_path: Percorso del file video di output
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
        podcast_logo_path: Percorso logo podcast
        podcast_title: Titolo del podcast
        episode_title: Titolo dell'episodio
        transcript_chunks: Lista di chunk di trascrizione con timing
        duration: Durata del video
        formats: Dizionario con i formati personalizzati (opzionale)
        colors: Dizionario con i colori personalizzati (opzionale)
    """
    # Usa formati personalizzati o di default
    if formats is None or format_name not in formats:
        width, height = FORMATS[format_name]
    else:
        format_config = formats[format_name]
        width = format_config.get('width', FORMATS[format_name][0])
        height = format_config.get('height', FORMATS[format_name][1])

    fps = 24  # Riduci da 30 a 24 fps per velocizzare

    print(f"  - Estrazione waveform...")
    # Estrai waveform una sola volta, campionata per frame
    waveform_data = get_waveform_data(audio_path, fps=fps)

    print(f"  - Pre-caricamento logo...")
    # Pre-carica e ridimensiona il logo una sola volta
    logo_img = None
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        central_height = int(height * 0.60)
        logo_size = int(min(width, central_height) * 0.4)
        logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

    print(f"  - Generazione frame video...")
    # Funzione per generare frame
    def make_frame(t):
        return create_audiogram_frame(
            width, height,
            podcast_logo_path,  # Passiamo il path per compatibilità
            podcast_title,
            episode_title,
            waveform_data,
            t,
            transcript_chunks,
            duration,
            colors
        )

    # Crea video clip
    video = VideoClip(make_frame, duration=duration)
    video.fps = fps

    print(f"  - Aggiunta audio...")
    # Aggiungi audio
    audio = AudioFileClip(audio_path)
    video = video.with_audio(audio)

    print(f"  - Rendering video...")
    # Esporta con threads per velocizzare
    video.write_videofile(
        output_path,
        codec='libx264',
        audio_codec='aac',
        fps=fps,
        threads=4,
        preset='medium'  # Bilancia velocità/qualità
    )
