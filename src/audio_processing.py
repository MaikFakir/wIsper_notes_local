import whisperx
import torch
import os
import gc
import gradio as gr
from datetime import timedelta
from whisperx.diarize import DiarizationPipeline

# --- 1. CONFIGURACIÓN DEL ENTORNO ---
# Determina si se usará GPU (CUDA) o CPU y el tipo de cómputo.
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"
print(f"Usando dispositivo: {DEVICE} con tipo de cómputo: {COMPUTE_TYPE}")

def get_hf_token():
    """
    Obtiene el token de autenticación de Hugging Face desde las variables de entorno.
    Este token es necesario para descargar y utilizar los modelos de diarización de pyannote.
    """
    token = os.environ.get('HF_TOKEN')
    if not token:
        print("ADVERTENCIA: La variable de entorno 'HF_TOKEN' no está configurada.")
        print("La diarización (identificación de hablantes) no funcionará.")
    return token

HF_TOKEN = get_hf_token()

# --- 2. GESTIÓN DE CACHÉ PARA MODELOS ---
# Guardamos los modelos en memoria para no tener que recargarlos en cada llamada.
model_cache = {
    "transcription": {},
    "alignment": {}
}
diarization_pipeline = None

def get_model(model_name, lang_code=None, model_type="transcription"):
    """
    Carga y cachea un modelo de WhisperX (transcripción o alineación).
    """
    cache = model_cache[model_type]
    key = model_name if model_type == "transcription" else lang_code

    if key not in cache:
        print(f"Cargando modelo de {model_type} para '{key}'...")
        if model_type == "transcription":
            model = whisperx.load_model(key, DEVICE, compute_type=COMPUTE_TYPE)
        else: # alignment
            model, metadata = whisperx.load_align_model(language_code=key, device=DEVICE)
            model = (model, metadata) # Guardamos ambos en la caché
        cache[key] = model
        print(f"Modelo de {model_type} para '{key}' cargado y cacheado.")
    return cache[key]

def get_diarization_pipeline():
    """
    Carga y cachea el pipeline de diarización de pyannote.
    Solo se carga una vez y si el token de HF está disponible.
    """
    global diarization_pipeline
    if diarization_pipeline is None and HF_TOKEN:
        print("Cargando pipeline de diarización por primera vez...")
        diarization_pipeline = DiarizationPipeline(use_auth_token=HF_TOKEN, device=DEVICE)
        print("Pipeline de diarización cargado y cacheado.")
    return diarization_pipeline

# --- 3. FUNCIONES AUXILIARES DE FORMATO ---
def format_timestamp(seconds: float) -> str:
    """Convierte segundos a un formato de tiempo HH:MM:SS.ms."""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{hours:02}:{minutes:02}:{seconds:02}.{milliseconds:03}"

def format_diarized_transcription(result: dict) -> str:
    """
    Formatea la transcripción con hablantes y timestamps en un formato legible.
    """
    segments = result.get("segments", [])
    if not segments:
        return "No se detectó texto en el audio."

    output = []
    for segment in segments:
        start_time = format_timestamp(segment['start'])
        end_time = format_timestamp(segment['end'])
        speaker = segment.get('speaker', 'SPEAKER_UNKNOWN')
        text = segment['text'].strip()
        output.append(f"[{start_time} -> {end_time}] **{speaker}**: {text}")

    return "\n\n".join(output)

# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
def transcribir_con_diarizacion(audio_path: str, model_name: str, language_code: str):
    """
    Orquesta el proceso completo de transcripción y diarización.
    """
    if not audio_path:
        gr.Warning("No se ha proporcionado ningún archivo de audio.")
        return "Error: Archivo de audio no encontrado.", None

    gr.Info("Iniciando proceso de transcripción...")

    try:
        # --- PASO 1: Cargar audio ---
        gr.Info(f"Cargando audio desde: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # --- PASO 2: Transcripción con WhisperX ---
        gr.Info(f"Transcribiendo con el modelo '{model_name}'...")
        transcription_model = get_model(model_name, model_type="transcription")
        # Si no se especifica idioma, whisper lo detecta automáticamente.
        result = transcription_model.transcribe(audio, batch_size=16, language=language_code)
        detected_lang = result["language"]
        gr.Info(f"Idioma detectado: {detected_lang.upper()}")

        # --- PASO 3: Alineación de palabras ---
        gr.Info("Alineando las marcas de tiempo de las palabras...")
        align_model, align_metadata = get_model(None, lang_code=detected_lang, model_type="alignment")
        result = whisperx.align(result["segments"], align_model, align_metadata, audio, DEVICE, return_char_alignments=False)

        # --- PASO 4: Diarización (si el token está disponible) ---
        diarize_pipeline = get_diarization_pipeline()
        if diarize_pipeline:
            gr.Info("Realizando diarización para identificar hablantes...")
            diarize_segments = diarize_pipeline(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            final_transcription = format_diarized_transcription(result)
            gr.Info("¡Proceso de transcripción y diarización completado!")
        else:
            gr.Warning("Saltando la diarización. No se ha proporcionado HF_TOKEN.")
            # Formato sin hablantes si no hay diarización
            final_transcription = "\n".join([segment['text'].strip() for segment in result.get("segments", [])])
            gr.Info("Proceso de transcripción (sin diarización) completado.")

        return final_transcription, audio_path

    except Exception as e:
        error_message = f"Ha ocurrido un error crítico: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
        gr.Error(error_message)
        return error_message, audio_path # Devolver la ruta para poder reintentar

    finally:
        # --- Limpieza de memoria ---
        print("Liberando memoria de la GPU y recolectando basura...")
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        print("Limpieza de memoria completada.")