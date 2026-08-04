"""
video_builder.py
=================
Genera videos para redes sociales a partir de:
  - Una carpeta de imágenes, donde el NOMBRE del archivo codifica la
    duración (en segundos) que esa imagen debe permanecer en pantalla.
  - Un archivo de audio (mp3/wav/m4a...) cuya duración total define
    la duración final del video.
  - (Opcional) Un archivo de subtítulos .srt que se "quema" (burn-in)
    sobre el video, con tamaño de fuente configurable.
  - (Opcional) Varios tamaños/relaciones de aspecto de salida, para
    poder generar de una sola vez las versiones para TikTok/Reels/
    Shorts (9:16), YouTube (16:9), feed cuadrado (1:1), etc.

Stack 100% gratuito y open source:
  - moviepy (usa ffmpeg por debajo) -> corte/composición de video
  - Pillow -> renderizado de texto para subtítulos (sin depender de
    ImageMagick, que suele dar problemas de instalación)
  - ffmpeg -> ya viene incluido vía el paquete imageio-ffmpeg que
    instala moviepy

Instalación:
    pip install moviepy pillow

------------------------------------------------------------------
CONVENCIÓN DE NOMBRES DE IMAGEN
------------------------------------------------------------------
El script busca el último número (entero o decimal) que aparece en
el nombre del archivo, antes de la extensión, y lo interpreta como
segundos de exposición. Ejemplos válidos:

    01_2.0.jpg      -> 2.0 segundos, orden 1
    02_3.5.jpg      -> 3.5 segundos, orden 2
    escena_04_5s.png -> 5 segundos (la 's' final se ignora)
    3.jpg           -> 3 segundos

El orden de aparición en el video es el orden alfabético de los
nombres de archivo, por eso se recomienda anteponer un índice
(01_, 02_, 03_...).

------------------------------------------------------------------
AJUSTE A LA DURACIÓN DEL AUDIO
------------------------------------------------------------------
Como la suma de duraciones de las imágenes casi nunca coincide
exactamente con la duración del audio, hay 3 estrategias
(parámetro `fit_mode`):

    "scale" (por defecto): se reescala proporcionalmente la duración
        de TODAS las imágenes para que la suma total sea exactamente
        igual a la duración del audio. Mantiene las proporciones
        relativas que definiste en los nombres de archivo.

    "trim": si las imágenes duran más que el audio, se recorta el
        video al final. Si duran menos, se extiende la última imagen.

    "loop": si las imágenes duran menos que el audio, se repite la
        secuencia completa de imágenes desde el inicio hasta llenar
        la duración del audio (útil para loops/gifs largos).
"""

import os
import re
import glob
import textwrap
from dataclasses import dataclass

from moviepy import (
    ImageClip,
    AudioFileClip,
    CompositeVideoClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont


# ------------------------------------------------------------------
# Presets de tamaño de salida para distintas redes sociales
# ------------------------------------------------------------------
RESOLUTION_PRESETS = {
    "tiktok": (1080, 1920),
    "reels": (1080, 1920),
    "shorts": (1080, 1920),
    "stories": (1080, 1920),
    "youtube": (1920, 1080),
    "square": (1080, 1080),
    "instagram_post": (1080, 1350),  # 4:5, el formato "alto" del feed
}

# Rutas de fuente típicas en Linux / Windows / Mac, en orden de intento
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _resolve_font(font_path, fontsize):
    candidates = [font_path] if font_path else []
    candidates += _FONT_CANDIDATES
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                return ImageFont.truetype(path, fontsize)
            except OSError:
                continue
    # último recurso: fuente por defecto de PIL (no escala bien, pero no falla)
    return ImageFont.load_default()


# ------------------------------------------------------------------
# 1) Parseo de duración desde el nombre de archivo
# ------------------------------------------------------------------
_DURATION_RE = re.compile(r"(\d+(?:\.\d+)?)\s*s?$")


def parse_duration_from_filename(filepath):
    """Extrae la duración (float, segundos) del nombre de archivo.

    Toma el último número que aparece en el nombre (sin extensión).
    Devuelve None si no se encuentra ningún número.
    """
    base = os.path.splitext(os.path.basename(filepath))[0]
    match = _DURATION_RE.search(base)
    if not match:
        return None
    return float(match.group(1))


def load_image_sequence(image_folder, extensions=(".jpg", ".jpeg", ".png", ".webp")):
    """Lee la carpeta de imágenes y devuelve una lista de tuplas
    (ruta, duracion_segundos) ordenadas por nombre de archivo.
    """
    files = sorted(
        f for f in glob.glob(os.path.join(image_folder, "*"))
        if f.lower().endswith(extensions)
    )
    if not files:
        raise ValueError(f"No se encontraron imágenes en: {image_folder}")

    sequence = []
    for f in files:
        duration = parse_duration_from_filename(f)
        if duration is None or duration <= 0:
            raise ValueError(
                f"No pude interpretar una duración válida en el nombre: '{f}'. "
                "Usa un formato como '01_2.5.jpg' (índice_duración.ext)."
            )
        sequence.append((f, duration))
    return sequence


# ------------------------------------------------------------------
# 2) Duración del audio
# ------------------------------------------------------------------
def get_audio_duration(audio_path):
    with AudioFileClip(audio_path) as clip:
        return clip.duration


# ------------------------------------------------------------------
# 3) Ajustar duraciones de imágenes a la duración del audio
# ------------------------------------------------------------------
def fit_durations_to_audio(sequence, target_duration, fit_mode="scale"):
    total = sum(d for _, d in sequence)

    if fit_mode == "scale":
        factor = target_duration / total
        return [(path, d * factor) for path, d in sequence]

    if fit_mode == "trim":
        adjusted = []
        remaining = target_duration
        for path, d in sequence:
            if remaining <= 0:
                break
            use = min(d, remaining)
            adjusted.append((path, use))
            remaining -= use
        # si el audio dura más que todas las imágenes, estira la última
        if remaining > 0 and adjusted:
            last_path, last_d = adjusted[-1]
            adjusted[-1] = (last_path, last_d + remaining)
        return adjusted

    if fit_mode == "loop":
        adjusted = []
        remaining = target_duration
        i = 0
        while remaining > 0:
            path, d = sequence[i % len(sequence)]
            use = min(d, remaining)
            adjusted.append((path, use))
            remaining -= use
            i += 1
        return adjusted

    raise ValueError(f"fit_mode desconocido: {fit_mode}")


# ------------------------------------------------------------------
# 4) Subtítulos: parseo de .srt + renderizado con Pillow
# ------------------------------------------------------------------
@dataclass
class SubtitleEntry:
    start: float
    end: float
    text: str


def _srt_time_to_seconds(t):
    h, m, rest = t.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt(srt_path):
    with open(srt_path, encoding="utf-8-sig") as f:
        content = f.read()

    blocks = re.split(r"\n\s*\n", content.strip())
    entries = []
    time_re = re.compile(
        r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})"
    )
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        time_match = None
        text_lines = []
        for line in lines:
            m = time_re.search(line)
            if m:
                time_match = m
            elif not line.strip().isdigit():
                text_lines.append(line.strip())
        if time_match:
            entries.append(
                SubtitleEntry(
                    start=_srt_time_to_seconds(time_match.group(1)),
                    end=_srt_time_to_seconds(time_match.group(2)),
                    text=" ".join(text_lines),
                )
            )
    return entries


def _render_subtitle_png(text, video_size, fontsize, font_path=None,
                          color=(255, 255, 255, 255),
                          stroke_color=(0, 0, 0, 255), stroke_width=3,
                          margin_bottom_ratio=0.08, max_width_ratio=0.9):
    """Devuelve la ruta a un PNG transparente del tamaño del video con
    el texto centrado cerca de la parte inferior (estilo subtítulo)."""
    w, h = video_size
    font = _resolve_font(font_path, fontsize)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    max_width_px = int(w * max_width_ratio)

    # envolver texto para que no se salga del ancho disponible
    avg_char_w = max(font.getlength("x"), 1)
    wrap_chars = max(int(max_width_px / avg_char_w), 10)
    wrapped = textwrap.fill(text, width=wrap_chars)
    lines = wrapped.split("\n")

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total_text_h = sum(line_heights) + (len(lines) - 1) * 6
    y = h - int(h * margin_bottom_ratio) - total_text_h

    for line, lh in zip(lines, line_heights):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (w - line_w) / 2
        draw.text(
            (x, y), line, font=font, fill=color,
            stroke_width=stroke_width, stroke_fill=stroke_color,
        )
        y += lh + 6

    return img


def build_subtitle_clips(entries, video_size, fontsize, font_path=None, **style):
    clips = []
    for entry in entries:
        img = _render_subtitle_png(
            entry.text, video_size, fontsize, font_path=font_path, **style
        )
        import numpy as np
        clip = (
            ImageClip(np.array(img))
            .with_start(entry.start)
            .with_duration(entry.end - entry.start)
        )
        clips.append(clip)
    return clips


# ------------------------------------------------------------------
# 5) Ajustar cada imagen al tamaño de salida (modo "cover": llena el
#    encuadre y recorta el sobrante, sin franjas negras)
# ------------------------------------------------------------------
def _cover_resize(clip, target_size):
    target_w, target_h = target_size
    src_w, src_h = clip.size
    scale = max(target_w / src_w, target_h / src_h)
    resized = clip.resized(scale)
    # recorte centrado
    x_center = resized.w / 2
    y_center = resized.h / 2
    return resized.cropped(
        x_center=x_center, y_center=y_center,
        width=target_w, height=target_h,
    )


# ------------------------------------------------------------------
# 6) Función principal
# ------------------------------------------------------------------
def build_video(
    image_folder,
    audio_path,
    output_path,
    srt_path=None,
    resolution=(1080, 1920),
    fit_mode="scale",
    fontsize=48,
    font_path=None,
    subtitle_color=(255, 255, 255, 255),
    fps=30,
    verbose=True,
):
    """Arma el video final.

    Parámetros clave:
      image_folder: carpeta con imágenes nombradas '<orden>_<duracion>.ext'
      audio_path:   archivo de audio que define la duración total
      output_path:  ruta del .mp4 de salida
      srt_path:     archivo .srt opcional para quemar subtítulos
      resolution:   (ancho, alto) de salida, o usa RESOLUTION_PRESETS
      fit_mode:     'scale' | 'trim' | 'loop' (ver docstring del módulo)
      fontsize:     tamaño de fuente de los subtítulos, en píxeles
    """
    sequence = load_image_sequence(image_folder)
    audio_duration = get_audio_duration(audio_path)
    adjusted = fit_durations_to_audio(sequence, audio_duration, fit_mode)

    if verbose:
        print(f"Duración del audio: {audio_duration:.2f}s")
        print(f"Imágenes: {len(adjusted)} | modo de ajuste: {fit_mode}")

    image_clips = []
    for path, duration in adjusted:
        clip = ImageClip(path).with_duration(duration)
        clip = _cover_resize(clip, resolution)
        image_clips.append(clip)

    video = concatenate_videoclips(image_clips, method="compose")
    video = video.with_duration(audio_duration)  # ajuste fino por redondeo

    audio_clip = AudioFileClip(audio_path)
    video = video.with_audio(audio_clip)

    if srt_path:
        entries = parse_srt(srt_path)
        sub_clips = build_subtitle_clips(
            entries, resolution, fontsize, font_path=font_path,
            color=subtitle_color,
        )
        video = CompositeVideoClip([video, *sub_clips], size=resolution)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    video.write_videofile(
        output_path, fps=fps, codec="libx264", audio_codec="aac",
        logger="bar" if verbose else None,
    )

    video.close()
    audio_clip.close()
    return output_path


def build_for_multiple_platforms(
    image_folder, audio_path, output_dir, platforms, srt_path=None,
    fit_mode="scale", fontsize=48, font_path=None, fps=30,
):
    """Genera una versión del video por cada plataforma en `platforms`
    (claves de RESOLUTION_PRESETS, p.ej. ['tiktok', 'youtube', 'square']).
    El tamaño de fuente de los subtítulos se escala automáticamente
    según el ancho de cada resolución para que se vea proporcional.
    """
    outputs = {}
    for platform in platforms:
        resolution = RESOLUTION_PRESETS[platform]
        # escala el fontsize en proporción al ancho, tomando 1080 como base
        scaled_fontsize = int(fontsize * (resolution[0] / 1080))
        out_path = os.path.join(output_dir, f"{platform}.mp4")
        build_video(
            image_folder=image_folder,
            audio_path=audio_path,
            output_path=out_path,
            srt_path=srt_path,
            resolution=resolution,
            fit_mode=fit_mode,
            fontsize=scaled_fontsize,
            font_path=font_path,
            fps=fps,
        )
        outputs[platform] = out_path
    return outputs


# ------------------------------------------------------------------
# Uso por línea de comandos
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--images", required=True, help="Carpeta de imágenes")
    parser.add_argument("--audio", required=True, help="Archivo de audio")
    parser.add_argument("--srt", default=None, help="Archivo .srt (opcional)")
    parser.add_argument("--out", default="output", help="Carpeta de salida")
    parser.add_argument(
        "--platforms", nargs="+", default=["tiktok"],
        choices=list(RESOLUTION_PRESETS.keys()),
        help="Una o más plataformas a generar",
    )
    parser.add_argument("--fit-mode", default="scale", choices=["scale", "trim", "loop"])
    parser.add_argument("--fontsize", type=int, default=48)
    args = parser.parse_args()

    results = build_for_multiple_platforms(
        image_folder=args.images,
        audio_path=args.audio,
        output_dir=args.out,
        platforms=args.platforms,
        srt_path=args.srt,
        fit_mode=args.fit_mode,
        fontsize=args.fontsize,
    )
    for platform, path in results.items():
        print(f"[{platform}] -> {path}")
