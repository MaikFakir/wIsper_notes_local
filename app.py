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
import os
import json
import shutil
from datetime import datetime

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


# --- 3. CONSTANTES Y FUNCIONES DE LA BIBLIOTECA ---

AUDIO_LIBRARY_PATH = "audio_library"
METADATA_FILE = os.path.join(AUDIO_LIBRARY_PATH, "metadata.json")

def get_library_contents():
    """Lee los metadatos y devuelve una lista de audios para mostrar."""
    if not os.path.exists(METADATA_FILE):
        return []

    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        try:
            metadata = json.load(f)
        except json.JSONDecodeError:
            return []

    # Devolver una lista de tuplas (nombre_archivo, transcripcion)
    return [(filename, data.get("transcription", "No disponible")) for filename, data in metadata.items()]

def refresh_library_list():
    """Actualiza la lista de audios en la interfaz."""
    return gr.update(choices=[item[0] for item in get_library_contents()])


def rename_library_item(current_filename, new_filename):
    """Renombra un archivo en la biblioteca y actualiza los metadatos."""
    if not current_filename or not new_filename:
        return "Selecciona un archivo y proporciona un nuevo nombre.", gr.update(), gr.update()

    # Añadir extensión .wav si no está presente
    if not new_filename.lower().endswith('.wav'):
        new_filename += '.wav'

    current_filepath = os.path.join(AUDIO_LIBRARY_PATH, current_filename)
    new_filepath = os.path.join(AUDIO_LIBRARY_PATH, new_filename)

    if not os.path.exists(current_filepath):
        return f"Error: El archivo '{current_filename}' no existe.", gr.update(), gr.update()

    if os.path.exists(new_filepath):
        return f"Error: Ya existe un archivo con el nombre '{new_filename}'.", gr.update(), gr.update()

    # Renombrar el archivo de audio
    os.rename(current_filepath, new_filepath)

    # Actualizar los metadatos
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r+', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
                if current_filename in metadata:
                    metadata[new_filename] = metadata.pop(current_filename)

                f.seek(0)
                json.dump(metadata, f, indent=4, ensure_ascii=False)
                f.truncate()
            except json.JSONDecodeError:
                pass

    return f"Archivo renombrado a '{new_filename}'.", gr.update(choices=[item[0] for item in get_library_contents()], value=new_filename), gr.update(value="")


def delete_from_library(filename_to_delete):
    """Elimina un audio y su metadato de la biblioteca."""
    if not filename_to_delete:
        # Devuelve 4 valores para coincidir con los outputs, sin hacer cambios
        return "No se ha seleccionado ningún archivo para eliminar.", gr.update(), gr.update(), gr.update()

    # Eliminar archivo de audio
    audio_path_to_delete = os.path.join(AUDIO_LIBRARY_PATH, filename_to_delete)
    if os.path.exists(audio_path_to_delete):
        os.remove(audio_path_to_delete)

    # Eliminar metadato
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r+', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
                if filename_to_delete in metadata:
                    del metadata[filename_to_delete]

                f.seek(0)
                json.dump(metadata, f, indent=4, ensure_ascii=False)
                f.truncate()
            except json.JSONDecodeError:
                pass  # El archivo de metadatos está corrupto o vacío

    # Devolver una confirmación y actualizar la interfaz para limpiar los campos
    return (
        f"Archivo '{filename_to_delete}' eliminado.",
        gr.update(choices=[item[0] for item in get_library_contents()], value=None),
        gr.update(value=None),
        gr.update(value="")
    )


def save_to_library(audio_path, transcription):
    """Guarda el audio y su transcripción en la biblioteca."""
    if not audio_path or not transcription:
        return "Nada que guardar."

    # Crear un nombre de archivo único con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_{timestamp}.wav"
    new_audio_path = os.path.join(AUDIO_LIBRARY_PATH, filename)

    # Copiar el archivo de audio a la biblioteca
    shutil.copy(audio_path, new_audio_path)

    # Cargar y actualizar metadatos
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r+', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                metadata = {}

            metadata[filename] = {
                "transcription": transcription,
                "original_path": audio_path,
                "timestamp": timestamp
            }
            f.seek(0)
            json.dump(metadata, f, indent=4, ensure_ascii=False)
            f.truncate()
    else:
         with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            metadata = {
                filename: {
                    "transcription": transcription,
                    "original_path": audio_path,
                    "timestamp": timestamp
                }
            }
            json.dump(metadata, f, indent=4, ensure_ascii=False)


    return f"¡Guardado! Audio '{filename}' añadido a la biblioteca."


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

# --- 4. INTERFAZ DE GRADIO ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    # Estado para almacenar la ruta del último audio procesado
    processed_audio_path_state = gr.State(value=None)

    gr.Markdown("## 🎙️ Transcriptor con Diarización (Resemblyzer + DBSCAN)")
    gr.Markdown("Graba una conversación. El sistema transcribirá y agrupará los segmentos por hablante.")

    with gr.Row():
        audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio aquí")

    with gr.Row():
        text_box = gr.Textbox(label="📝 Transcripción con Hablantes", lines=15, interactive=False)

    with gr.Row():
        save_button = gr.Button("💾 Guardar en la Biblioteca")

    status_box = gr.Textbox(label="ℹ️ Estado", lines=1, interactive=False)

    # --- Sección de la Biblioteca ---
    with gr.Accordion("📚 Biblioteca de Audios", open=False):
        library_list = gr.Dropdown(label="Audios Guardados", choices=[item[0] for item in get_library_contents()])
        with gr.Row():
            refresh_button = gr.Button("🔄 Refrescar")
            delete_button = gr.Button("🗑️ Eliminar Seleccionado")

        with gr.Row():
            new_name_input = gr.Textbox(label="Nuevo nombre para el archivo seleccionado", placeholder="Escribe el nuevo nombre aquí...")
            rename_button = gr.Button("✏️ Renombrar")

        selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath")

    # --- Lógica de la Interfaz ---

    def on_select_library_item(filename):
        """
        Se activa al seleccionar un item de la biblioteca.
        Carga el audio y la transcripción correspondiente.
        """
        if not filename:
            return None, ""

        audio_path = os.path.join(AUDIO_LIBRARY_PATH, filename)

        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        transcription = metadata.get(filename, {}).get("transcription", "Transcripción no encontrada.")

        return audio_path, transcription

    # Conexiones de eventos
    audio_input.change(transcribir_con_diarizacion, inputs=audio_input, outputs=[text_box, processed_audio_path_state])
    save_button.click(save_to_library, inputs=[processed_audio_path_state, text_box], outputs=[status_box]).then(refresh_library_list, outputs=library_list)

    library_list.change(on_select_library_item, inputs=library_list, outputs=[selected_audio_player, text_box])
    refresh_button.click(refresh_library_list, outputs=library_list)
    delete_button.click(delete_from_library, inputs=library_list, outputs=[status_box, library_list, selected_audio_player, text_box])
    rename_button.click(rename_library_item, inputs=[library_list, new_name_input], outputs=[status_box, library_list, new_name_input])


if __name__ == "__main__":
    # Crear el directorio de la biblioteca si no existe
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    demo.launch(share=True, debug=True)
