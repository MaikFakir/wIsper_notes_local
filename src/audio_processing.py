import whisperx
import torch
import os
import gradio as gr
import gc
from datetime import timedelta
from whisperx.diarize import DiarizationPipeline

# --- 1. CONFIGURACIÓN ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

def get_hf_token():
    """Obtiene el token de Hugging Face desde las variables de entorno."""
    token = os.environ.get('HF_TOKEN')
    if not token:
        print("Advertencia: La variable de entorno 'HF_TOKEN' no se ha configurado. La diarización puede fallar.")
    return token

HF_TOKEN = get_hf_token()

# --- 2. CARGA DE MODELOS (CACHEADOS) ---
model_cache = {}
diarization_pipeline_cache = None
align_model_cache = {}

def get_transcription_model(model_name):
    """Carga y cachea los modelos de WhisperX."""
    if model_name not in model_cache:
        print(f"Cargando modelo de transcripción: {model_name}...")
        model = whisperx.load_model(model_name, DEVICE, compute_type=COMPUTE_TYPE)
        model_cache[model_name] = model
        print(f"Modelo '{model_name}' cargado.")
    return model_cache[model_name]

def get_align_model(language_code):
    """Carga y cachea los modelos de alineación."""
    if language_code not in align_model_cache:
        print(f"Cargando modelo de alineación para el idioma: {language_code}...")
        model, metadata = whisperx.load_align_model(language_code=language_code, device=DEVICE)
        align_model_cache[language_code] = (model, metadata)
        print(f"Modelo de alineación para '{language_code}' cargado.")
    return align_model_cache[language_code]

def get_diarization_pipeline():
    """Carga y cachea el pipeline de diarización."""
    global diarization_pipeline_cache
    if diarization_pipeline_cache is None and HF_TOKEN:
        print("Cargando pipeline de diarización...")
        diarization_pipeline_cache = DiarizationPipeline(use_auth_token=HF_TOKEN, device=DEVICE)
        print("Pipeline de diarización cargado.")
    return diarization_pipeline_cache

# --- 3. FUNCIONES AUXILIARES DE FORMATO ---
def format_timestamp(seconds):
    """Convierte segundos a un formato de tiempo HH:MM:SS.ms."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

def format_transcription_with_speakers(result):
    """Formatea la transcripción final con la información de los hablantes."""
    lines = []
    current_speaker = None
    text_buffer = ""
    start_time = ""

    for segment in result["segments"]:
        speaker = segment.get("speaker", "SPEAKER_UNKNOWN")

        if speaker != current_speaker:
            if current_speaker is not None:
                lines.append(f"**{current_speaker} ({start_time} - {end_time}):** {text_buffer.strip()}")
            current_speaker = speaker
            start_time = format_timestamp(segment['start'])
            text_buffer = ""

        text_buffer += segment['text'].strip() + " "
        end_time = format_timestamp(segment['end'])

    if current_speaker is not None:
        lines.append(f"**{current_speaker} ({start_time} - {end_time}):** {text_buffer.strip()}")

    return "\n\n".join(lines) if lines else "No se pudo generar la transcripción."


# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
def transcribir_con_diarizacion(audio_path, model_name="base", language_code="es"):
    """
    Procesa un audio siguiendo el flujo oficial de WhisperX:
    1. Transcribe
    2. Alinea
    3. Diariza y asigna hablantes
    """
    if not audio_path:
        gr.Warning("No se recibió audio. Por favor, graba o sube algo.")
        return "No se recibió audio.", None

    try:
        # --- Paso 0: Carga de modelos y audio ---
        transcription_model = get_transcription_model(model_name)
        gr.Info(f"Cargando audio desde: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # --- Paso 1: Transcripción ---
        gr.Info(f"Transcribiendo con el modelo '{model_name}'...")
        result = transcription_model.transcribe(audio, batch_size=16, language=language_code)

        # --- Paso 2: Alineación ---
        gr.Info("Alineando marcas de tiempo...")
        align_model, metadata = get_align_model(result["language"])
        result = whisperx.align(result["segments"], align_model, metadata, audio, DEVICE, return_char_alignments=False)

        # --- Paso 3: Diarización y asignación de hablantes ---
        if HF_TOKEN:
            diarize_pipeline = get_diarization_pipeline()
            if diarize_pipeline:
                gr.Info("Realizando diarización y asignando hablantes...")
                diarize_segments = diarize_pipeline(audio)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                final_transcription = format_transcription_with_speakers(result)
                gr.Info("Proceso completado.")
            else:
                gr.Warning("El pipeline de diarización no se pudo cargar. Se omitirán los hablantes.")
                final_transcription = " ".join([seg['text'].strip() for seg in result.get("segments", [])])
        else:
            gr.Warning("No se ha configurado el token de Hugging Face (HF_TOKEN). Se omitirá la diarización.")
            final_transcription = " ".join([seg['text'].strip() for seg in result.get("segments", [])])

        return final_transcription, audio_path

    except Exception as e:
        error_message = f"Ha ocurrido un error inesperado durante el procesamiento: {e}"
        print(error_message)
        gr.Error(error_message)
        return error_message, None
    finally:
        # Liberar memoria de la GPU
        torch.cuda.empty_cache()
        gc.collect()