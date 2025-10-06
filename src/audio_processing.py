# --- 1. INSTALACIONES E IMPORTACIONES ---
import ffmpeg
import tempfile
import os
from faster_whisper import WhisperModel
import gradio as gr
import torch

# --- 2. UTILIDADES DE AUDIO ---

def convert_audio_to_wav(audio_path):
    """
    Convierte un archivo de audio a formato WAV a 16kHz, mono.
    Devuelve la ruta del archivo temporal convertido.
    """
    try:
        # Crea un archivo temporal con la extensión .wav
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        # Usa ffmpeg para la conversión
        (
            ffmpeg
            .input(audio_path)
            .output(temp_filename, acodec='pcm_s16le', ac=1, ar='16k')
            .run(overwrite_output=True, quiet=True)
        )
        return temp_filename
    except ffmpeg.Error as e:
        print(f"Error de ffmpeg: {e.stderr.decode()}")
        raise
    except Exception as e:
        print(f"Error inesperado en la conversión de audio: {e}")
        raise

# --- 3. CARGA DE MODELOS (LAZY LOADING) ---

transcription_model = None

def get_transcription_model():
    """
    Carga el modelo de transcripción de forma perezosa (solo cuando se necesita).
    Esto evita que la aplicación se cuelgue al inicio.
    """
    global transcription_model
    if transcription_model is None:
        print("Cargando modelo de transcripción por primera vez...")
        DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"
        transcription_model = WhisperModel("base", device=DEVICE, compute_type=COMPUTE_TYPE)
        print("Modelo de transcripción cargado.")
    return transcription_model


# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribe_audio(audio_path):
    """
    Transcribe un archivo de audio y devuelve el texto plano.
    """
    if audio_path is None:
        return "No se recibió audio. Por favor, graba algo.", None

    temp_wav_path = None
    try:
        # 1️⃣ Cargar el modelo (se inicializará solo la primera vez)
        model = get_transcription_model()

        # 2️⃣ Convertir a WAV estándar para compatibilidad y eficiencia
        print("Convirtiendo audio a formato WAV...")
        temp_wav_path = convert_audio_to_wav(audio_path)
        print(f"Audio convertido y guardado en: {temp_wav_path}")

        # 3️⃣ Transcripción directa desde el archivo
        print("Iniciando transcripción...")
        segments_generator, info = model.transcribe(
            temp_wav_path, language="es"
        )

        # Unir los segmentos en un solo texto
        segments = list(segments_generator)
        full_transcription = " ".join([s.text for s in segments]).strip()
        print("Transcripción completada.")

        if not full_transcription:
            return "No se pudo transcribir el audio (posiblemente silencio).", audio_path

        print("Proceso completado.")
        return full_transcription, audio_path

    except ffmpeg.Error as e:
        return f"Error de FFMPEG: {e.stderr.decode()}", None
    except Exception as e:
        import traceback
        return f"Ocurrió un error inesperado: {e}\\n{traceback.format_exc()}", None
    finally:
        # 3️⃣ Limpieza del archivo temporal
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)
            print(f"Archivo temporal eliminado: {temp_wav_path}")