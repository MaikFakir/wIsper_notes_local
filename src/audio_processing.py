# --- 1. INSTALACIONES E IMPORTACIONES ---
from faster_whisper import WhisperModel
import gradio as gr
from resemblyzer import VoiceEncoder
import numpy as np
import librosa
from sklearn.cluster import DBSCAN
import torch

# --- 2. CARGA DE MODELOS ---

# Determina el dispositivo a usar
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# Diccionario para cachear los modelos de transcripción
transcription_models_cache = {}

def get_transcription_model(model_name="base"):
    """
    Carga un modelo de Whisper si no está en caché y lo devuelve.
    """
    if model_name not in transcription_models_cache:
        print(f"Cargando modelo de transcripción: {model_name}...")
        try:
            model = WhisperModel(model_name, device=DEVICE, compute_type=COMPUTE_TYPE)
            transcription_models_cache[model_name] = model
            print(f"Modelo '{model_name}' cargado.")
        except Exception as e:
            print(f"Error al cargar el modelo '{model_name}': {e}")
            # Devolver el modelo base como fallback si existe, o None
            return transcription_models_cache.get("base")
    return transcription_models_cache[model_name]

# Cargar el modelo por defecto al iniciar
get_transcription_model("base")

# Cargar encoder de voces. Es recomendable usar CPU para evitar conflictos de VRAM.
print("Cargando modelo de codificación de voz...")
voice_encoder = VoiceEncoder(device="cpu")
print("Modelo de codificación de voz cargado.")


# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribir_con_diarizacion(audio_path, model_name="base"):
    """
    Transcribe un archivo de audio y realiza diarización de hablantes.
    Devuelve la transcripción y la ruta del archivo de audio.
    """
    if audio_path is None:
        return "No se recibió audio. Por favor, graba algo.", None, gr.update()

    # Obtener el modelo de transcripción seleccionado
    transcription_model = get_transcription_model(model_name)
    if transcription_model is None:
        return f"Error: No se pudo cargar el modelo de transcripción '{model_name}'.", None, gr.update()

    # 1️⃣ Cargar audio UNA SOLA VEZ
    try:
        wav, sr = librosa.load(audio_path, sr=16000)
    except Exception as e:
        return f"Error al cargar el archivo de audio: {e}", None, gr.update()

    # 2️⃣ Transcripción con Whisper
    status_update = f"Transcribiendo con el modelo '{model_name}'..."
    # A status_update a gr.Info() for better visibility
    gr.Info(status_update)


    segments_generator, info = transcription_model.transcribe(wav, language="es", word_timestamps=True)
    segments = list(segments_generator)

    if not segments:
        return "No se pudo transcribir el audio (posiblemente silencio).", audio_path, f"Transcripción con '{model_name}' completada."

    # 3️⃣ Extraer embeddings de voz de cada segmento
    embeddings = []
    valid_segments = []
    for seg in segments:
        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        segment_wav = wav[start_sample:end_sample]

        if len(segment_wav) < 400:
            continue

        try:
            emb = voice_encoder.embed_utterance(segment_wav)
            embeddings.append(emb)
            valid_segments.append(seg)
        except Exception as e:
            print(f"No se pudo procesar el segmento de {seg.start} a {seg.end}: {e}")

    if not valid_segments:
        return " ".join([s.text for s in segments]), audio_path, f"Transcripción con '{model_name}' completada (sin diarización)."

    # 4️⃣ Clustering de hablantes
    embeddings = np.array(embeddings)
    clustering = DBSCAN(eps=0.5, min_samples=1, metric="cosine").fit(embeddings)
    labels = clustering.labels_

    # 5️⃣ Construir la transcripción final
    transcripcion = ""
    current_speaker_label = -1
    current_text = ""

    for i, seg in enumerate(valid_segments):
        speaker_label = labels[i]

        if speaker_label != current_speaker_label and current_speaker_label != -1:
            speaker_name = f"Hablante {current_speaker_label + 1}"
            transcripcion += f"**{speaker_name}:** {current_text.strip()}\\n\\n"
            current_text = ""

        current_speaker_label = speaker_label
        current_text += " " + seg.text

    if current_speaker_label != -1:
        speaker_name = f"Hablante {current_speaker_label + 1}"
        transcripcion += f"**{speaker_name}:** {current_text.strip()}\\n\\n"

    return transcripcion.strip(), audio_path, f"Transcripción y diarización con '{model_name}' completada."