import whisperx
import torch
import os
import gradio as gr
from datetime import timedelta

# --- 1. CONFIGURACIÓN ---

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

def get_hf_token():
    """
    Obtiene el token de Hugging Face desde las variables de entorno.
    """
    token = os.environ.get('HF_TOKEN')
    if not token:
        # Esta advertencia es útil para la depuración en la consola
        print("Advertencia: La variable de entorno 'HF_TOKEN' no se ha configurado. La diarización puede fallar.")
    return token

HF_TOKEN = get_hf_token()


# Cache para los modelos
model_cache = {}

def get_model(model_name):
    """Carga y cachea los modelos de WhisperX."""
    if model_name not in model_cache:
        print(f"Cargando modelo de transcripción: {model_name}...")
        try:
            model = whisperx.load_model(model_name, DEVICE, compute_type=COMPUTE_TYPE)
            model_cache[model_name] = model
            print(f"Modelo '{model_name}' cargado.")
        except Exception as e:
            print(f"Error al cargar el modelo '{model_name}': {e}")
            return None
    return model_cache[model_name]

# --- 2. FUNCIONES AUXILIARES ---

def format_timestamp(seconds):
    """Convierte segundos a un formato de tiempo HH:MM:SS.ms."""
    td = timedelta(seconds=seconds)
    # Formato para asegurar dos dígitos en horas, minutos y segundos
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

def format_transcription_with_speakers(result):
    """Formatea la transcripción con hablantes y marcas de tiempo."""
    lines = []
    current_speaker = None
    text_buffer = ""
    start_time = ""

    for segment in result["segments"]:
        speaker = segment.get("speaker", "DESCONOCIDO")

        if speaker != current_speaker:
            if current_speaker is not None:
                # Escribir el buffer del hablante anterior
                lines.append(f"**{current_speaker} ({start_time} - {end_time}):** {text_buffer.strip()}")

            # Iniciar nuevo hablante
            current_speaker = speaker
            start_time = format_timestamp(segment['start'])
            text_buffer = ""

        text_buffer += segment['text'].strip() + " "
        end_time = format_timestamp(segment['end'])

    # Escribir el último buffer
    if current_speaker is not None:
        lines.append(f"**{current_speaker} ({start_time} - {end_time}):** {text_buffer.strip()}")

    return "\n\n".join(lines)


# --- 3. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribir_con_diarizacion(audio_path, model_name="base", language_code="es"):
    """
    Transcribe un archivo de audio usando WhisperX para obtener marcas de tiempo
    a nivel de palabra y realiza diarización de hablantes.
    Devuelve la transcripción y la ruta del audio.
    """
    if audio_path is None:
        gr.Warning("No se recibió audio. Por favor, graba o sube algo.")
        return "No se recibió audio.", None

    # --- Validación del token de Hugging Face ---
    if not HF_TOKEN:
        gr.Warning("No se ha configurado el token de Hugging Face (HF_TOKEN). La diarización no funcionará.")
        # No devolvemos un error, pero la diarización será omitida.

    # --- 1. Carga de Modelo y Audio ---
    transcription_model = get_model(model_name)
    if transcription_model is None:
        error_msg = f"Error: No se pudo cargar el modelo de transcripción '{model_name}'."
        gr.Error(error_msg)
        return error_msg, None

    try:
        gr.Info(f"Cargando audio desde: {audio_path}")
        audio = whisperx.load_audio(audio_path)
    except Exception as e:
        error_msg = f"Error al cargar el archivo de audio: {e}"
        gr.Error(error_msg)
        return error_msg, None

    # --- 2. Transcripción ---
    gr.Info(f"Transcribiendo con el modelo '{model_name}' en idioma '{language_code}'...")
    result = transcription_model.transcribe(audio, batch_size=16, language=language_code)

    # --- 3. Alineación de Marcas de Tiempo (si es posible) ---
    try:
        gr.Info("Alineando marcas de tiempo...")
        model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=DEVICE)
        result = whisperx.align(result["segments"], model_a, metadata, audio, DEVICE, return_char_alignments=False)
    except Exception as e:
        gr.Warning(f"No se pudo alinear para el idioma '{language_code}'. Transcripción sin alineación detallada.")
        pass

    # --- 4. Diarización de Hablantes (si hay token) ---
    if HF_TOKEN:
        try:
            gr.Info("Realizando diarización de hablantes...")
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=HF_TOKEN, device=DEVICE)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
        except Exception as e:
            gr.Warning(f"Error en diarización: {e}. Se omitirán los hablantes.")
            # La transcripción continuará sin la información de hablantes

    # --- 5. Formateo de la Salida ---
    if "segments" not in result or not result["segments"]:
        gr.Warning("La transcripción no produjo segmentos.")
        return "La transcripción no produjo segmentos.", audio_path

    # Si la diarización falló o se omitió, 'speaker' no estará en los segmentos
    if "speaker" in result["segments"][0]:
        final_transcription = format_transcription_with_speakers(result)
        gr.Info(f"Transcripción y diarización con '{model_name}' completada.")
    else:
        final_transcription = " ".join([seg['text'].strip() for seg in result.get("segments", [])])
        gr.Info(f"Transcripción con '{model_name}' completada (sin diarización).")

    return final_transcription, audio_path
