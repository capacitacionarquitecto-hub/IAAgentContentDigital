# video_builder.py — generador de video para redes sociales (100% gratis)

Stack usado (todo open source, sin APIs de pago): **moviepy** (usa **ffmpeg**
por debajo) + **Pillow** para renderizar los subtítulos. No depende de
ImageMagick ni de ningún servicio externo.

## Instalación

```bash
pip install moviepy pillow
```

(ffmpeg viene incluido automáticamente vía el paquete `imageio-ffmpeg`
que instala moviepy).

## 1. Nombra tus imágenes con la duración

El script lee el **último número** del nombre del archivo (antes de la
extensión) como segundos de exposición. Antepone un índice para
controlar el orden:

```
imagenes/
  01_2.0.jpg      -> se muestra 2.0s, va primera
  02_3.5.jpg      -> se muestra 3.5s, va segunda
  03_1.5.jpg      -> se muestra 1.5s, va tercera
```

## 2. Uso desde Python

```python
from video_builder import build_video, build_for_multiple_platforms

# Un solo video
build_video(
    image_folder="imagenes",
    audio_path="audio.mp3",
    output_path="salida/video.mp4",
    srt_path="subtitulos.srt",   # opcional
    resolution=(1080, 1920),      # 9:16 vertical
    fit_mode="scale",             # ver abajo
    fontsize=48,
)

# Varias plataformas de una sola vez (tamaños distintos)
build_for_multiple_platforms(
    image_folder="imagenes",
    audio_path="audio.mp3",
    output_dir="salida",
    platforms=["tiktok", "youtube", "square", "instagram_post"],
    srt_path="subtitulos.srt",
    fontsize=48,   # se re-escala automáticamente según el ancho de cada formato
)
```

## 3. Uso desde la terminal

```bash
python video_builder.py \
  --images imagenes \
  --audio audio.mp3 \
  --srt subtitulos.srt \
  --out salida \
  --platforms tiktok youtube square \
  --fontsize 48
```

## Cómo se calcula la duración total

1. Se analiza el audio con `AudioFileClip(...).duration` para saber
   cuánto debe durar el video.
2. Se suman las duraciones de todas las imágenes (según sus nombres).
3. Como casi nunca coinciden exactamente, se ajustan con `fit_mode`:
   - **`scale`** (por defecto): reescala proporcionalmente todas las
     duraciones para que la suma dé exactamente igual al audio.
     Mantiene las proporciones relativas que definiste.
   - **`trim`**: recorta el video al final si sobran imágenes, o
     estira la última si faltan.
   - **`loop`**: si el audio dura más que la secuencia de imágenes,
     repite la secuencia completa hasta llenar el tiempo.

## Tamaños/plataformas disponibles (`RESOLUTION_PRESETS`)

| clave              | resolución  | uso                        |
|--------------------|-------------|-----------------------------|
| tiktok/reels/shorts/stories | 1080x1920 | vertical 9:16       |
| youtube            | 1920x1080   | horizontal 16:9              |
| square             | 1080x1080   | feed cuadrado 1:1            |
| instagram_post     | 1080x1350   | feed vertical 4:5             |

Cada imagen se ajusta en modo "cover" (llena el encuadre y recorta el
sobrante) para que no queden franjas negras en ningún formato.

## Subtítulos

- Formato estándar `.srt`.
- El tamaño de fuente se controla con `fontsize` (en píxeles, sobre
  base 1080px de ancho). Al generar varias plataformas, el tamaño se
  re-escala automáticamente en proporción al ancho de cada una.
- Se dibujan centrados cerca del borde inferior, con contorno negro
  para que se lean sobre cualquier fondo.
- Puedes pasar tu propia fuente `.ttf` con `font_path="ruta.ttf"` para
  usar tu tipografía de marca.

## Notas para integrarlo en tu agente

- Todas las funciones (`parse_duration_from_filename`,
  `get_audio_duration`, `fit_durations_to_audio`, `parse_srt`, etc.)
  están separadas para que puedas usarlas sueltas si tu agente ya
  genera las imágenes/audio/subtítulos con otra herramienta (p. ej.
  TTS local o un modelo de subtítulos) y solo necesitas el ensamblado
  final.
- El script fue probado de punta a punta (imágenes + audio + .srt +
  dos resoluciones) y confirmado: duración final ajustada al audio,
  subtítulos con tildes correctas y sin franjas negras.
