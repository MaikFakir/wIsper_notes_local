import whisperx
import torch
import os
import gc
import gradio as gr
from datetime import timedelta
from whisperx.diarize import DiarizationPipeline

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

# --- GESTIÓN DE CACHÉ PARA MODELOS ---
# La caché ahora es consciente del dispositivo para evitar conflictos.
model_cache = {
    "transcription": {},
    "alignment": {}
}
diarization_pipelines = {} # Cache de pipelines por dispositivo

def get_model(model_name, device, compute_type, lang_code=None, model_type="transcription"):
    """
    Carga y cachea un modelo de WhisperX (transcripción o alineación).
    La clave de la caché ahora incluye el dispositivo para evitar conflictos.
    """
    cache = model_cache[model_type]
    key = (model_name, device) if model_type == "transcription" else (lang_code, device)

    if key not in cache:
        print(f"Cargando modelo de {model_type} para '{key[0]}' en dispositivo '{device}'...")
        if model_type == "transcription":
            # key[0] es el nombre del modelo
            model = whisperx.load_model(key[0], device, compute_type=compute_type)
        else: # alignment
            # key[0] es el código de idioma
            model, metadata = whisperx.load_align_model(language_code=key[0], device=device)
            model = (model, metadata)
        cache[key] = model
        print(f"Modelo de {model_type} para '{key[0]}' cargado y cacheado.")
    return cache[key]

def get_diarization_pipeline(device):
    """
    Carga y cachea el pipeline de diarización de pyannote para un dispositivo específico.
    """
    global diarization_pipelines
    if device not in diarization_pipelines and HF_TOKEN:
        print(f"Cargando pipeline de diarización por primera vez para el dispositivo '{device}'...")
        diarization_pipelines[device] = DiarizationPipeline(use_auth_token=HF_TOKEN, device=device)
        print(f"Pipeline de diarización para '{device}' cargado y cacheado.")
    return diarization_pipelines.get(device)

# --- FUNCIONES AUXILIARES DE FORMATO ---
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

# --- FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---
def transcribir_con_diarizacion(audio_path: str, model_name: str, language_code: str, device_choice: str):
    """
    Orquesta el proceso completo de transcripción y diarización, permitiendo la selección de dispositivo.
    """
    if not audio_path:
        return "Error: Archivo de audio no encontrado.", None, None

    # --- Selección de dispositivo y validación ---
    warning_message = None
    if device_choice == "GPU" and torch.cuda.is_available():
        device = "cuda"
        compute_type = "float16"
        gr.Info("Usando GPU para la transcripción.")
    else:
        device = "cpu"
        compute_type = "int8"
        if device_choice == "GPU":
            warning_message = "ADVERTENCIA: No se detectó una GPU compatible. Se usará la CPU en su lugar."
            gr.Warning(warning_message)
        gr.Info("Usando CPU para la transcripción.")

    print(f"Dispositivo seleccionado: {device.upper()} con tipo de cómputo: {compute_type}")

    try:
        gr.Info("Iniciando proceso de transcripción...")

        # --- PASO 1: Cargar audio ---
        gr.Info(f"Cargando audio desde: {audio_path}")
        audio = whisperx.load_audio(audio_path)

        # --- PASO 2: Transcripción con WhisperX ---
        gr.Info(f"Transcribiendo con el modelo '{model_name}'...")
        transcription_model = get_model(model_name, device, compute_type, model_type="transcription")
        result = transcription_model.transcribe(audio, batch_size=16, language=language_code)
        detected_lang = result["language"]
        gr.Info(f"Idioma detectado: {detected_lang.upper()}")

        # --- PASO 3: Alineación de palabras ---
        gr.Info("Alineando las marcas de tiempo de las palabras...")
        align_model, align_metadata = get_model(None, device, None, lang_code=detected_lang, model_type="alignment")
        result = whisperx.align(result["segments"], align_model, align_metadata, audio, device, return_char_alignments=False)

        # --- PASO 4: Diarización (si el token está disponible) ---
        diarize_pipeline = get_diarization_pipeline(device)
        if diarize_pipeline:
            gr.Info("Realizando diarización para identificar hablantes...")
            diarize_segments = diarize_pipeline(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)
            final_transcription = format_diarized_transcription(result)
            gr.Info("¡Proceso de transcripción y diarización completado!")
        else:
            gr.Warning("Saltando la diarización. No se ha proporcionado HF_TOKEN.")
            final_transcription = "\n".join([segment['text'].strip() for segment in result.get("segments", [])])
            gr.Info("Proceso de transcripción (sin diarización) completado.")

        return final_transcription, audio_path, warning_message

    except Exception as e:
        error_message = f"Ha ocurrido un error crítico: {str(e)}"
        print(error_message)
        import traceback
        traceback.print_exc()
        gr.Error(error_message)
        return error_message, audio_path, warning_message

    finally:
        # --- Limpieza de memoria ---
        print("Liberando memoria y recolectando basura...")
        if device == "cuda":
            torch.cuda.empty_cache()
        gc.collect()
        print("Limpieza de memoria completada.")