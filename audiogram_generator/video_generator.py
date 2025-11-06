"""
Generatore di video audiogram
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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


def _subtitle_default_style(colors):
    """Ritorna lo stile predefinito per i sottotitoli (trascrizione)."""
    # Colori con alpha per sfondo
    bg = tuple(colors.get('transcript_bg', COLOR_BLACK))
    bg_with_alpha = bg + (190,) if len(bg) == 3 else bg
    return {
        'text_color': tuple(colors.get('text', COLOR_WHITE)),
        'bg_color': bg_with_alpha,      # RGBA
        'padding': 18,                  # px
        'radius': 18,                   # px angoli arrotondati
        'line_spacing': 1.28,           # moltiplicatore altezza riga
        'shadow': True,                 # ombra soft al box
        'shadow_offset': (0, 4),        # dx, dy
        'shadow_blur': 10,              # raggio blur
        'max_lines': 5,                 # righe massime visualizzate
        'width_ratio': 0.88             # % della larghezza massima
    }


def _draw_rounded_box_with_shadow(base_img, box, fill, radius=16, shadow=True, shadow_offset=(0, 3), shadow_blur=8):
    """Disegna un rettangolo arrotondato semi-trasparente con ombra su un overlay RGBA e lo compone su base_img.
    box: (x1, y1, x2, y2)
    Ritorna l'immagine risultante (stessa istanza o nuova se necessario).
    """
    # Assicurati che la base sia RGBA per alpha_composite
    if base_img.mode != 'RGBA':
        base_img = base_img.convert('RGBA')

    overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)

    if shadow:
        sx = box[0] + shadow_offset[0]
        sy = box[1] + shadow_offset[1]
        ex = box[2] + shadow_offset[0]
        ey = box[3] + shadow_offset[1]
        shadow_overlay = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(shadow_overlay)
        sdraw.rounded_rectangle([(sx, sy), (ex, ey)], radius=radius, fill=(0, 0, 0, 140))
        shadow_overlay = shadow_overlay.filter(ImageFilter.GaussianBlur(shadow_blur))
        base_img = Image.alpha_composite(base_img, shadow_overlay)

    odraw.rounded_rectangle([box[:2], box[2:]], radius=radius, fill=fill)
    base_img = Image.alpha_composite(base_img, overlay)
    return base_img


def _render_subtitle_lines(img, draw, text, font, start_y, max_width, style):
    """Esegue il word wrap e disegna le righe di sottotitoli più gradevoli.
    Ritorna (img, total_height_disegnata).
    """
    # Word wrap manuale
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = (current + w + " ").strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test + " " if not test.endswith(" ") else test
        else:
            if current.strip():
                lines.append(current.strip())
            current = w + " "
    if current.strip():
        lines.append(current.strip())

    lines = lines[: style.get('max_lines', 5)]

    total_height = 0
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        lh = bbox[3] - bbox[1]
        line_x = (img.width - lw) // 2
        line_y = start_y + int(total_height)

        padding = style['padding']
        box = (line_x - padding, line_y - padding, line_x + lw + padding, line_y + lh + padding)
        img = _draw_rounded_box_with_shadow(
            img,
            box,
            style['bg_color'],
            radius=style['radius'],
            shadow=style['shadow'],
            shadow_offset=style['shadow_offset'],
            shadow_blur=style['shadow_blur']
        )

        # Dopo compositing, ricrea draw su eventuale immagine RGBA
        draw = ImageDraw.Draw(img)
        draw.text((line_x, line_y), line, fill=style['text_color'], font=font)

        line_advance = int(lh * style['line_spacing'])
        total_height += line_advance

    return img, int(total_height)


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


def create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, colors, cta_text, show_progress_bar=False):
    """
    Layout specifico per formato verticale 9:16 (1080x1920)
    Ottimizzato per Instagram Reels, Stories, YouTube Shorts, TikTok
    """
    # Progress bar (2% altezza) - opzionale
    progress_height = 0
    if show_progress_bar:
        progress_height = int(height * 0.02)
        progress_percent = current_time / audio_duration if audio_duration > 0 else 0
        progress_width = int(width * progress_percent)

        # Background della progress bar (arancione scuro)
        draw.rectangle([(0, 0), (width, progress_height)], fill=colors['primary'])
        # Riempimento progress (beige che avanza)
        if progress_width > 0:
            draw.rectangle([(0, 0), (progress_width, progress_height)], fill=colors['background'])

    # Header (17% altezza) - aumentato per ospitare 3 righe di titolo
    header_top = progress_height
    header_height = int(height * 0.17)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Titolo episodio nel header (con word wrap su 3 righe)
    try:
        font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(header_height * 0.17))
    except:
        font_header = ImageFont.load_default()

    # Word wrap del titolo su max 3 righe
    max_header_width = int(width * 0.90)
    words = episode_title.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " " if current_line else word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font_header)
        test_width = bbox[2] - bbox[0]

        if test_width <= max_header_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
                current_line = word + " "
            else:
                # Parola singola troppo lunga, la tronchiamo
                current_line = word[:30] + "... "
                lines.append(current_line.strip())
                current_line = ""

    if current_line:
        lines.append(current_line.strip())

    # Limita a 3 righe, troncando la terza se necessario
    lines = lines[:3]
    if len(lines) == 3:
        bbox = draw.textbbox((0, 0), lines[2], font=font_header)
        while (bbox[2] - bbox[0]) > max_header_width and len(lines[2]) > 3:
            lines[2] = lines[2][:-4] + "..."
            bbox = draw.textbbox((0, 0), lines[2], font=font_header)

    # Disegna le righe centrate, posizionate più in basso
    bbox_sample = draw.textbbox((0, 0), "Test", font=font_header)
    line_height = bbox_sample[3] - bbox_sample[1]
    total_height = len(lines) * line_height * 1.2
    start_y = header_top + int(header_height * 0.65) - int(total_height // 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_header)
        line_width = bbox[2] - bbox[0]
        line_x = (width - line_width) // 2
        line_y = start_y + i * int(line_height * 1.2)
        draw.text((line_x, line_y), line, fill=colors['text'], font=font_header)

    # Area centrale (54% altezza) - ridotta per compensare l'header più grande
    central_top = header_top + header_height
    central_height = int(height * 0.54)
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

        # Proteggi contro num_bars troppo piccolo (serve almeno 2 per la simmetria)
        if num_bars >= 2:
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
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0

                # Ampiezza finale con sensibilità e boost
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                # Altezza minima e massima
                min_height = int(central_height * 0.12)
                max_height = int(central_height * 0.80)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # Centra verticalmente - spostato più in alto (al 40% invece del 50%)
                y_center = central_top + int(central_height * 0.40)
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                # Disegna la bar
                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast al centro (sopra la waveform) - spostato più in alto
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width, central_height) * 0.6)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # Posizione spostata più in alto (al 35% invece del 50%)
        logo_x = (width - logo_size) // 2
        logo_y = central_top + int(central_height * 0.35) - logo_size // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (27% altezza) - aumentato per ospitare podcast title + CTA
    footer_top = central_bottom
    footer_height = int(height * 0.27)
    footer_bottom = footer_top + footer_height
    draw.rectangle([(0, footer_top), (width, footer_bottom)], fill=colors['primary'])

    # Titolo podcast nel footer
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.12))
    except:
        font_title = ImageFont.load_default()

    # Podcast title centrato verticalmente nella parte superiore del footer
    bbox = draw.textbbox((0, 0), podcast_title, font=font_title)
    title_width = bbox[2] - bbox[0]
    title_height = bbox[3] - bbox[1]
    title_x = (width - title_width) // 2
    title_y = footer_top + int(footer_height * 0.15)
    draw.text((title_x, title_y), podcast_title, fill=colors['text'], font=font_title)

    # Call-to-action sotto il titolo del podcast
    if cta_text:  # Mostra solo se specificato
        try:
            font_cta = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.09))
        except:
            font_cta = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
        cta_width = bbox[2] - bbox[0]
        cta_x = (width - cta_width) // 2
        cta_y = title_y + title_height + int(footer_height * 0.15)
        draw.text((cta_x, cta_y), cta_text, fill=colors['text'], font=font_cta)

    # Trascrizione in tempo reale (sopra il footer, nell'area centrale bassa)
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.028))
            except:
                font_transcript = ImageFont.load_default()

            # Posizionamento più in alto, sotto il logo
            transcript_y = central_top + int(central_height * 0.67)

            # Stile sottotitoli e larghezza massima
            style = _subtitle_default_style(colors)
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            # Aggiorna draw nel caso l'immagine sia stata convertita in RGBA
            draw = ImageDraw.Draw(img)

    return img


def create_square_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                         waveform_data, current_time, transcript_chunks, audio_duration, colors, cta_text, show_progress_bar=False):
    """
    Layout specifico per formato quadrato 1:1 (1080x1080)
    Ottimizzato per Instagram Post, Twitter, Mastodon, LinkedIn
    Logo e waveform centrati verticalmente
    """
    # Progress bar (2% altezza) - opzionale
    progress_height = 0
    if show_progress_bar:
        progress_height = int(height * 0.02)
        progress_percent = current_time / audio_duration if audio_duration > 0 else 0
        progress_width = int(width * progress_percent)

        # Background della progress bar (arancione)
        draw.rectangle([(0, 0), (width, progress_height)], fill=colors['primary'])
        # Riempimento progress (beige che avanza)
        if progress_width > 0:
            draw.rectangle([(0, 0), (progress_width, progress_height)], fill=colors['background'])

    # Header (12% altezza) - più piccolo per square
    header_top = progress_height
    header_height = int(height * 0.12)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Titolo episodio nel header (2 righe max per square)
    try:
        font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(header_height * 0.22))
    except:
        font_header = ImageFont.load_default()

    # Word wrap del titolo su max 2 righe
    max_header_width = int(width * 0.90)
    words = episode_title.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " " if current_line else word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font_header)
        test_width = bbox[2] - bbox[0]

        if test_width <= max_header_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
                current_line = word + " "
            else:
                current_line = word[:30] + "... "
                lines.append(current_line.strip())
                current_line = ""

    if current_line:
        lines.append(current_line.strip())

    # Limita a 2 righe per square
    lines = lines[:2]
    if len(lines) == 2:
        bbox = draw.textbbox((0, 0), lines[1], font=font_header)
        while (bbox[2] - bbox[0]) > max_header_width and len(lines[1]) > 3:
            lines[1] = lines[1][:-4] + "..."
            bbox = draw.textbbox((0, 0), lines[1], font=font_header)

    # Disegna le righe centrate
    bbox_sample = draw.textbbox((0, 0), "Test", font=font_header)
    line_height = bbox_sample[3] - bbox_sample[1]
    total_height = len(lines) * line_height * 1.2
    start_y = header_top + int(header_height * 0.50) - int(total_height // 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_header)
        line_width = bbox[2] - bbox[0]
        line_x = (width - line_width) // 2
        line_y = start_y + i * int(line_height * 1.2)
        draw.text((line_x, line_y), line, fill=colors['text'], font=font_header)

    # Area centrale (66% altezza) - più grande per square
    central_top = header_top + header_height
    central_height = int(height * 0.66)
    central_bottom = central_top + central_height

    # Visualizzatore waveform CENTRATO VERTICALMENTE
    if waveform_data is not None and len(waveform_data) > 0:
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        num_bars = width // total_bar_width
        if num_bars % 2 != 0:
            num_bars -= 1

        if num_bars >= 2:
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            np.random.seed(42)
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])

            for i in range(num_bars):
                x = i * total_bar_width

                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                min_height = int(central_height * 0.12)
                max_height = int(central_height * 0.70)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # CENTRATO VERTICALMENTE al 50%
                y_center = central_top + central_height // 2
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo podcast CENTRATO VERTICALMENTE
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width, central_height) * 0.5)
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # CENTRATO VERTICALMENTE al 50%
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (20% altezza)
    footer_top = central_bottom
    footer_height = int(height * 0.20)
    footer_bottom = footer_top + footer_height
    draw.rectangle([(0, footer_top), (width, footer_bottom)], fill=colors['primary'])

    # Titolo podcast nel footer - font ingrandito
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.18))
    except:
        font_title = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), podcast_title, font=font_title)
    title_width = bbox[2] - bbox[0]
    title_height = bbox[3] - bbox[1]
    title_x = (width - title_width) // 2
    title_y = footer_top + int(footer_height * 0.20)
    draw.text((title_x, title_y), podcast_title, fill=colors['text'], font=font_title)

    # Call-to-action sotto il titolo - font ingrandito
    if cta_text:
        try:
            font_cta = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.13))
        except:
            font_cta = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
        cta_width = bbox[2] - bbox[0]
        cta_x = (width - cta_width) // 2
        cta_y = title_y + title_height + int(footer_height * 0.15)
        draw.text((cta_x, cta_y), cta_text, fill=colors['text'], font=font_cta)

    # Trascrizione in basso nell'area centrale
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.030))
            except:
                font_transcript = ImageFont.load_default()

            transcript_y = central_bottom - int(central_height * 0.15)
            style = _subtitle_default_style(colors)
            style['max_lines'] = min(style.get('max_lines', 5), 3)  # per square al massimo 3 righe
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            draw = ImageDraw.Draw(img)

    return img


def create_horizontal_layout(img, draw, width, height, podcast_logo_path, podcast_title, episode_title,
                             waveform_data, current_time, transcript_chunks, audio_duration, colors, cta_text, show_progress_bar=False):
    """
    Layout specifico per formato orizzontale 16:9 (1920x1080)
    Ottimizzato per YouTube
    Logo e waveform centrati verticalmente
    """
    # Progress bar (2% altezza) - opzionale
    progress_height = 0
    if show_progress_bar:
        progress_height = int(height * 0.02)
        progress_percent = current_time / audio_duration if audio_duration > 0 else 0
        progress_width = int(width * progress_percent)

        draw.rectangle([(0, 0), (width, progress_height)], fill=colors['primary'])
        if progress_width > 0:
            draw.rectangle([(0, 0), (progress_width, progress_height)], fill=colors['background'])

    # Header (15% altezza)
    header_top = progress_height
    header_height = int(height * 0.15)
    draw.rectangle([(0, header_top), (width, header_top + header_height)], fill=colors['primary'])

    # Titolo episodio nel header (2 righe max)
    try:
        font_header = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(header_height * 0.25))
    except:
        font_header = ImageFont.load_default()

    max_header_width = int(width * 0.90)
    words = episode_title.split()
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + word + " " if current_line else word + " "
        bbox = draw.textbbox((0, 0), test_line, font=font_header)
        test_width = bbox[2] - bbox[0]

        if test_width <= max_header_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line.strip())
                current_line = word + " "
            else:
                current_line = word[:30] + "... "
                lines.append(current_line.strip())
                current_line = ""

    if current_line:
        lines.append(current_line.strip())

    lines = lines[:2]
    if len(lines) == 2:
        bbox = draw.textbbox((0, 0), lines[1], font=font_header)
        while (bbox[2] - bbox[0]) > max_header_width and len(lines[1]) > 3:
            lines[1] = lines[1][:-4] + "..."
            bbox = draw.textbbox((0, 0), lines[1], font=font_header)

    bbox_sample = draw.textbbox((0, 0), "Test", font=font_header)
    line_height = bbox_sample[3] - bbox_sample[1]
    total_height = len(lines) * line_height * 1.2
    start_y = header_top + int(header_height * 0.50) - int(total_height // 2)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_header)
        line_width = bbox[2] - bbox[0]
        line_x = (width - line_width) // 2
        line_y = start_y + i * int(line_height * 1.2)
        draw.text((line_x, line_y), line, fill=colors['text'], font=font_header)

    # Area centrale (68% altezza)
    central_top = header_top + header_height
    central_height = int(height * 0.68)
    central_bottom = central_top + central_height

    # Waveform CENTRATA VERTICALMENTE
    if waveform_data is not None and len(waveform_data) > 0:
        bar_spacing = 3
        bar_width = 12
        total_bar_width = bar_width + bar_spacing

        num_bars = width // total_bar_width
        if num_bars % 2 != 0:
            num_bars -= 1

        if num_bars >= 2:
            frame_idx = int((current_time / audio_duration) * len(waveform_data)) if audio_duration > 0 else 0
            frame_idx = min(frame_idx, len(waveform_data) - 1)
            current_amplitude = waveform_data[frame_idx]

            np.random.seed(42)
            sensitivities = np.random.uniform(0.6, 1.4, num_bars // 2)
            sensitivities = np.concatenate([sensitivities, sensitivities[::-1]])

            for i in range(num_bars):
                x = i * total_bar_width

                center_idx = num_bars // 2
                distance_from_center = abs(i - center_idx)
                center_boost = 1.0 + (1.0 - distance_from_center / center_idx) * 0.4 if center_idx > 0 else 1.0
                bar_amplitude = current_amplitude * sensitivities[i] * center_boost

                min_height = int(central_height * 0.15)
                max_height = int(central_height * 0.70)
                bar_height = int(min_height + (bar_amplitude * (max_height - min_height)))
                bar_height = max(min_height, min(bar_height, max_height))

                # CENTRATA VERTICALMENTE al 50%
                y_center = central_top + central_height // 2
                y_top = y_center - bar_height // 2
                y_bottom = y_center + bar_height // 2

                draw.rectangle([(x, y_top), (x + bar_width, y_bottom)], fill=colors['primary'])

    # Logo CENTRATO VERTICALMENTE
    if os.path.exists(podcast_logo_path):
        logo = Image.open(podcast_logo_path)
        logo_size = int(min(width * 0.3, central_height * 0.6))
        logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)

        # CENTRATO VERTICALMENTE al 50%
        logo_x = (width - logo_size) // 2
        logo_y = central_top + (central_height - logo_size) // 2
        img.paste(logo, (logo_x, logo_y), logo if logo.mode == 'RGBA' else None)

    # Footer (15% altezza)
    footer_top = central_bottom
    footer_height = height - footer_top
    draw.rectangle([(0, footer_top), (width, height)], fill=colors['primary'])

    # Titolo podcast
    try:
        font_title = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.20))
    except:
        font_title = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), podcast_title, font=font_title)
    title_width = bbox[2] - bbox[0]
    title_height = bbox[3] - bbox[1]
    title_x = (width - title_width) // 2
    title_y = footer_top + int(footer_height * 0.25)
    draw.text((title_x, title_y), podcast_title, fill=colors['text'], font=font_title)

    # Call-to-action
    if cta_text:
        try:
            font_cta = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(footer_height * 0.14))
        except:
            font_cta = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), cta_text, font=font_cta)
        cta_width = bbox[2] - bbox[0]
        cta_x = (width - cta_width) // 2
        cta_y = title_y + title_height + int(footer_height * 0.15)
        draw.text((cta_x, cta_y), cta_text, fill=colors['text'], font=font_cta)

    # Trascrizione in basso nell'area centrale
    if transcript_chunks:
        current_text = ""
        for chunk in transcript_chunks:
            if chunk['start'] <= current_time < chunk['end']:
                current_text = chunk['text']
                break

        if current_text:
            try:
                font_transcript = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=int(height * 0.030))
            except:
                font_transcript = ImageFont.load_default()

            transcript_y = central_bottom - int(central_height * 0.18)
            style = _subtitle_default_style(colors)
            style['max_lines'] = min(style.get('max_lines', 5), 2)  # per horizontal max 2 righe
            max_width = int(width * style['width_ratio'])

            img, _ = _render_subtitle_lines(
                img,
                draw,
                current_text,
                font_transcript,
                transcript_y,
                max_width,
                style
            )
            draw = ImageDraw.Draw(img)

    return img


def create_audiogram_frame(width, height, podcast_logo_path, podcast_title, episode_title,
                           waveform_data, current_time, transcript_chunks, audio_duration, colors=None, cta_text=None, format_name='vertical', show_progress_bar=False):
    """
    Crea un singolo frame dell'audiogram delegando al layout specifico per formato

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
        cta_text: Testo della call-to-action (opzionale)
        format_name: Nome del formato ('vertical', 'square', 'horizontal')
        show_progress_bar: Mostra la progress bar in cima (opzionale, default False)
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

    # Delega al layout specifico per il formato
    if format_name == 'vertical':
        img = create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                     episode_title, waveform_data, current_time, transcript_chunks,
                                     audio_duration, colors, cta_text, show_progress_bar)
    elif format_name == 'square':
        img = create_square_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                   episode_title, waveform_data, current_time, transcript_chunks,
                                   audio_duration, colors, cta_text, show_progress_bar)
    elif format_name == 'horizontal':
        img = create_horizontal_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                       episode_title, waveform_data, current_time, transcript_chunks,
                                       audio_duration, colors, cta_text, show_progress_bar)
    else:
        # Default: usa vertical
        img = create_vertical_layout(img, draw, width, height, podcast_logo_path, podcast_title,
                                     episode_title, waveform_data, current_time, transcript_chunks,
                                     audio_duration, colors, cta_text, show_progress_bar)

    # Assicurati che l'array sia in RGB per MoviePy
    if img.mode != 'RGB':
        img = img.convert('RGB')
    return np.array(img)


def generate_audiogram(audio_path, output_path, format_name, podcast_logo_path,
                      podcast_title, episode_title, transcript_chunks, duration,
                      formats=None, colors=None, cta_text=None, show_progress_bar=False):
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
        cta_text: Testo della call-to-action (opzionale)
        show_progress_bar: Mostra la progress bar in cima (opzionale, default False)
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
            colors,
            cta_text,
            format_name,  # Passa il formato per usare il layout corretto
            show_progress_bar  # Passa il flag progress bar
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
