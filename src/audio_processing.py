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

# Cargar modelo Whisper. 'base' es un buen equilibrio entre velocidad y precisión para timestamps.
print("Cargando modelo de transcripción...")
transcription_model = WhisperModel("base", device=DEVICE, compute_type=COMPUTE_TYPE)
print("Modelo de transcripción cargado.")

# Cargar encoder de voces. Es recomendable usar CPU para evitar conflictos de VRAM.
print("Cargando modelo de codificación de voz...")
voice_encoder = VoiceEncoder(device="cpu")
print("Modelo de codificación de voz cargado.")

# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribir_con_diarizacion(audio_path):
    """
    Transcribe un archivo de audio y realiza diarización de hablantes.
    Devuelve la transcripción y la ruta del archivo de audio.
    """
    if audio_path is None:
        return "No se recibió audio. Por favor, graba algo.", None

    # 1️⃣ Cargar audio UNA SOLA VEZ
    try:
        wav, sr = librosa.load(audio_path, sr=16000)
    except Exception as e:
        return f"Error al cargar el archivo de audio: {e}", None

    # 2️⃣ Transcripción con Whisper
    segments_generator, info = transcription_model.transcribe(wav, language="es", word_timestamps=True)
    segments = list(segments_generator)

    if not segments:
        return "No se pudo transcribir el audio (posiblemente silencio).", audio_path

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
        return " ".join([s.text for s in segments]), audio_path

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

    return transcripcion.strip(), audio_path