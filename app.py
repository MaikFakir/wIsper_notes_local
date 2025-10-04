# --- 1. INSTALACIONES E IMPORTACIONES ---
# Este script asume que las siguientes librerías están instaladas.
# Se pueden instalar con: pip install faster-whisper gradio resemblyzer librosa ffmpeg-python scikit-learn torch numpy

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
# 'turbo' no es un tamaño de modelo estándar, lo cambiamos por 'base'.
print("Cargando modelo de transcripción...")
transcription_model = WhisperModel("base", device=DEVICE, compute_type=COMPUTE_TYPE)
print("Modelo de transcripción cargado.")

# Cargar encoder de voces. Es recomendable usar CPU para evitar conflictos de VRAM.
print("Cargando modelo de codificación de voz...")
voice_encoder = VoiceEncoder(device="cpu")
print("Modelo de codificación de voz cargado.")


# --- 3. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribir_con_diarizacion(audio_path):
    """
    Transcribe un archivo de audio y realiza diarización de hablantes.
    """
    if audio_path is None:
        return "No se recibió audio. Por favor, graba algo."

    # 1️⃣ Cargar audio UNA SOLA VEZ
    # Optimizacion: Cargamos el audio con librosa y lo pasamos como un array de numpy a Whisper.
    # Esto evita que el archivo se lea del disco dos veces.
    try:
        wav, sr = librosa.load(audio_path, sr=16000)
    except Exception as e:
        return f"Error al cargar el archivo de audio: {e}"

    # 2️⃣ Transcripción con Whisper
    # Pasamos el array de numpy 'wav' directamente al modelo.
    segments_generator, info = transcription_model.transcribe(wav, language="es", word_timestamps=True)

    # Convertimos el generador a una lista para poder acceder a su longitud y elementos múltiples veces.
    segments = list(segments_generator)

    if not segments:
        return "No se pudo transcribir el audio (posiblemente silencio)."

    # 3️⃣ Extraer embeddings de voz de cada segmento
    embeddings = []
    valid_segments = []
    for seg in segments:
        start_sample = int(seg.start * sr)
        end_sample = int(seg.end * sr)
        segment_wav = wav[start_sample:end_sample]

        # Nos aseguramos de que el segmento de audio no sea demasiado corto para el encoder.
        if len(segment_wav) < 400: # El encoder necesita al menos 400 muestras (25ms)
            continue

        try:
            emb = voice_encoder.embed_utterance(segment_wav)
            embeddings.append(emb)
            valid_segments.append(seg)
        except Exception as e:
            print(f"No se pudo procesar el segmento de {seg.start} a {seg.end}: {e}")


    if not valid_segments:
        # Si no se pudo obtener ningún embedding, devolvemos la transcripción simple
        return " ".join([s.text for s in segments])

    # Convertimos a numpy array para el clustering
    embeddings = np.array(embeddings)

    # 4️⃣ Clustering de hablantes con DBSCAN
    # El valor 'eps' es el más importante a ajustar. Un valor más bajo crea más clusters (más hablantes).
    # Un valor más alto agrupa más voces juntas. 0.5 es un buen punto de partida.
    clustering = DBSCAN(eps=0.5, min_samples=1, metric="cosine").fit(embeddings)
    labels = clustering.labels_

    # 5️⃣ Construir la transcripción final formateada
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

    # Asegurarse de agregar el último párrafo que quedó en el buffer
    if current_speaker_label != -1:
        speaker_name = f"Hablante {current_speaker_label + 1}"
        transcripcion += f"**{speaker_name}:** {current_text.strip()}\\n\\n"

    return transcripcion.strip()

# --- 4. INTERFAZ DE GRADIO ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("## 🎙️ Transcriptor con Diarización (Resemblyzer + DBSCAN)")
    gr.Markdown("Graba una conversación. El sistema transcribirá y agrupará los segmentos por hablante.")

    with gr.Row():
        mic = gr.Audio(sources=["microphone"], type="filepath", label="🎤 Graba tu audio aquí")

    with gr.Row():
        text_box = gr.Textbox(label="📝 Transcripción con Hablantes", lines=20, interactive=False)

    mic.change(transcribir_con_diarizacion, inputs=mic, outputs=text_box)

if __name__ == "__main__":
    demo.launch(share=True, debug=True)