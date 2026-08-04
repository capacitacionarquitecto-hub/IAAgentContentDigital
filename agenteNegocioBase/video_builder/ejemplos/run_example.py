"""
run_example.py
===============
Ejemplo mínimo de uso de video_builder.py con los archivos de esta
carpeta:

    imagenes/               -> 4 imágenes, el nombre define su duración
    audio_ejemplo.mp3       -> 10 segundos, define la duración del video
    subtitulos_ejemplo.srt  -> subtítulos a quemar

Este archivo debe estar en la misma carpeta que video_builder.py
(o ajusta el import agregando esa ruta a sys.path).

Ejecuta con:
    python run_example.py
"""

from video_builder import build_video, build_for_multiple_platforms

# --- Opción 1: un solo video, formato vertical (TikTok/Reels/Shorts) ---
build_video(
    image_folder="imagenes",
    audio_path="audio_ejemplo.mp3",
    output_path="salida/video_vertical.mp4",
    srt_path="subtitulos_ejemplo.srt",
    resolution=(1080, 1920),
    fit_mode="scale",   # reescala las duraciones para que sumen 10s exactos
    fontsize=48,
)

# --- Opción 2: varias plataformas de una sola vez ---
build_for_multiple_platforms(
    image_folder="imagenes",
    audio_path="audio_ejemplo.mp3",
    output_dir="salida",
    platforms=["tiktok", "youtube", "square"],
    srt_path="subtitulos_ejemplo.srt",
    fontsize=48,
)

print("\nListo. Revisa la carpeta 'salida/' para ver los videos generados.")
