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
import soundfile as sf
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

# --- Nuevas funciones para el sistema de carpetas ---

def get_directory_contents(path="."):
    """
    Obtiene el contenido de un directorio dentro de la biblioteca de audios.
    Prefija las carpetas con '[C]' para distinguirlas.
    """
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path):
        path = "."

    base_path = os.path.join(AUDIO_LIBRARY_PATH, path)
    contents = []
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    for item in sorted(os.listdir(base_path)):
        if os.path.isdir(os.path.join(base_path, item)):
            contents.append(f"[C] {item}")
        elif item.lower().endswith('.wav'):
            contents.append(item)

    return contents

def update_library_browser(current_path="."):
    """Actualiza el navegador de la biblioteca y la ruta visible."""
    choices = get_directory_contents(current_path)
    return gr.update(choices=choices, value=None), gr.update(value=current_path)

def create_folder_in_library(current_path, new_folder):
    """Crea una nueva carpeta en la ruta actual."""
    if not new_folder.strip() or ".." in new_folder or "/" in new_folder:
        return "Nombre de carpeta inválido.", gr.update(), gr.update(), gr.update()

    folder_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        status = f"Carpeta '{new_folder}' creada."
        browser_update, path_update = update_library_browser(current_path)
        return status, browser_update, path_update, gr.update(value="")
    else:
        return f"La carpeta '{new_folder}' ya existe.", gr.update(), gr.update(), gr.update()

def navigate_up(current_path):
    """Navega al directorio padre y actualiza el estado."""
    new_path = "."
    if current_path != ".":
        new_path = os.path.dirname(current_path)
    return new_path

def handle_selection_and_path_update(current_path, selection):
    """
    Decide si navegar a una carpeta o cargar un archivo.
    Actualiza el estado de la ruta actual si se selecciona una carpeta.
    """
    if selection is None:
        return current_path

    if selection.startswith("[C]"):
        folder_name = selection.replace("[C] ", "")
        new_path = os.path.join(current_path, folder_name)
        return new_path
    else:
        return current_path

def load_selected_file(selection, current_path):
    """Carga el audio y la transcripción de un archivo seleccionado."""
    if selection is None or selection.startswith("[C]"):
        return None, ""

    file_path_in_library = os.path.join(AUDIO_LIBRARY_PATH, current_path, selection)
    metadata_key = os.path.normpath(os.path.join(current_path, selection))

    transcription = "Transcripción no encontrada."
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
                transcription = metadata.get(metadata_key, {}).get("transcription", "Transcripción no encontrada.")
            except json.JSONDecodeError:
                pass

    return file_path_in_library, transcription


def save_to_library(current_path, audio_path, transcription):
    """Guarda el audio y su transcripción en la ruta actual de la biblioteca."""
    if not audio_path or not transcription:
        return "Nada que guardar."

    # Crear un nombre de archivo único con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_{timestamp}.wav"

    # La ruta completa donde se guardará el archivo físico
    physical_save_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, filename)

    # La clave para los metadatos (ruta relativa desde la raíz de la biblioteca)
    metadata_key = os.path.normpath(os.path.join(current_path, filename))

    try:
        # Cargar y convertir el audio a WAV
        wav, sr = librosa.load(audio_path, sr=16000)
        sf.write(physical_save_path, wav, sr)
    except Exception as e:
        return f"Error al guardar el archivo: {e}"

    # Cargar y actualizar metadatos
    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                pass  # El archivo se sobreescribirá

    metadata[metadata_key] = {
        "transcription": transcription,
        "timestamp": timestamp
    }

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    return f"¡Guardado! Audio '{filename}' añadido a '{current_path}'."


def rename_library_item(current_path, selection, new_name):
    """Renombra un archivo o carpeta en la ruta actual."""
    if not selection or not new_name.strip():
        return "Selecciona un item y proporciona un nuevo nombre.", gr.update(), gr.update(), gr.update()

    old_name = selection.replace("[C] ", "")
    new_name = new_name.strip()
    old_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, old_name)
    new_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_name)

    if not os.path.exists(old_path_full):
        return f"Error: El item '{old_name}' no existe.", gr.update(), gr.update(), gr.update()
    if os.path.exists(new_path_full):
        return f"Error: Ya existe un item con el nombre '{new_name}'.", gr.update(), gr.update(), gr.update()

    # Renombrar el archivo/carpeta físico
    os.rename(old_path_full, new_path_full)

    # Actualizar metadatos
    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                pass

    new_metadata = {}
    old_metadata_key_base = os.path.normpath(os.path.join(current_path, old_name))
    new_metadata_key_base = os.path.normpath(os.path.join(current_path, new_name))

    if os.path.isdir(new_path_full):  # Si es una carpeta
        # Actualizar todas las claves que comiencen con la ruta de la carpeta antigua
        for key, value in metadata.items():
            if key.startswith(old_metadata_key_base + os.sep):
                new_key = new_metadata_key_base + key[len(old_metadata_key_base):]
                new_metadata[new_key] = value
            elif key != old_metadata_key_base:
                new_metadata[key] = value
    else:  # Si es un archivo
        old_metadata_key = old_metadata_key_base
        new_metadata_key = new_metadata_key_base
        # Añadir extensión .wav si no está presente en el nuevo nombre
        if not new_name.lower().endswith('.wav'):
             new_metadata_key += '.wav'
             os.rename(new_path_full, new_path_full + '.wav')

        for key, value in metadata.items():
            if key == old_metadata_key:
                new_metadata[new_metadata_key] = value
            else:
                new_metadata[key] = value

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_metadata, f, indent=4, ensure_ascii=False)

    return f"Item renombrado a '{new_name}'.", *update_library_browser(current_path), gr.update(value="")


def delete_from_library(current_path, selection):
    """Elimina un archivo o carpeta de la ruta actual."""
    if not selection:
        return "No se ha seleccionado ningún item.", gr.update(), gr.update(), gr.update(), gr.update()

    item_name = selection.replace("[C] ", "")
    path_to_delete_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, item_name)

    if not os.path.exists(path_to_delete_full):
         return f"Error: El item '{item_name}' no existe.", gr.update(), gr.update(), gr.update(), gr.update()

    # Eliminar archivo/carpeta físico
    if os.path.isdir(path_to_delete_full):
        shutil.rmtree(path_to_delete_full)
    else:
        os.remove(path_to_delete_full)

    # Actualizar metadatos
    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                pass

    new_metadata = {}
    metadata_key_to_delete = os.path.normpath(os.path.join(current_path, item_name))

    for key, value in metadata.items():
        # No incluir la clave a eliminar ni ninguna clave dentro de la carpeta eliminada
        if not (key == metadata_key_to_delete or key.startswith(metadata_key_to_delete + os.sep)):
            new_metadata[key] = value

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_metadata, f, indent=4, ensure_ascii=False)

    return f"Item '{item_name}' eliminado.", *update_library_browser(current_path), gr.update(value=None), gr.update(value="")


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

    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## 📚 Biblioteca de Audios")

            # Estado para la ruta actual en la biblioteca
            current_path_state = gr.State(value=".")

            # UI para la creación de carpetas
            with gr.Row():
                new_folder_name = gr.Textbox(label="Nombre de la Carpeta", placeholder="Escribe y presiona Enter...", scale=3)
                create_folder_button = gr.Button("➕ Crear Carpeta", scale=1)

            # UI para la navegación
            with gr.Row():
                up_button = gr.Button("⬆️ Subir")
                refresh_button = gr.Button("🔄 Refrescar")

            current_path_display = gr.Textbox(label="Ruta Actual", value=".", interactive=False)

            # Lista de archivos y carpetas
            library_browser = gr.Radio(label="Contenido", choices=[], interactive=True)

            # Controles de renombrar y eliminar
            with gr.Row():
                new_name_input = gr.Textbox(label="Nuevo nombre", placeholder="Nuevo nombre para el item...", scale=3)
                rename_button = gr.Button("✏️ Renombrar", scale=1)
            delete_button = gr.Button("🗑️ Eliminar Seleccionado")

            # Reproductor de audio
            selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath")

        with gr.Column():
            gr.Markdown("## 🎙️ Transcriptor con Diarización (Resemblyzer + DBSCAN)")
            gr.Markdown("Graba una conversación. El sistema transcribirá y agrupará los segmentos por hablante.")

            audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio aquí")
            text_box = gr.Textbox(label="📝 Transcripción", lines=15, interactive=False)

            with gr.Row():
                save_button = gr.Button("💾 Guardar en la Biblioteca")

            status_box = gr.Textbox(label="ℹ️ Estado", lines=1, interactive=False)

    # --- Lógica de la Interfaz ---

    # --- Lógica de la Interfaz ---

    # Cargar el contenido inicial de la biblioteca
    demo.load(update_library_browser, outputs=[library_browser, current_path_display])

    # Conexiones de eventos de la transcripción principal
    audio_input.change(transcribir_con_diarizacion, inputs=audio_input, outputs=[text_box, processed_audio_path_state])
    save_button.click(
        save_to_library,
        inputs=[current_path_state, processed_audio_path_state, text_box],
        outputs=[status_box]
    ).then(
        update_library_browser,
        inputs=[current_path_state],
        outputs=[library_browser, current_path_display]
    )

    # Conexiones de la biblioteca
    create_folder_button.click(
        create_folder_in_library,
        inputs=[current_path_state, new_folder_name],
        outputs=[status_box, library_browser, current_path_display, new_folder_name]
    )

    up_button.click(
        navigate_up,
        inputs=[current_path_state],
        outputs=[current_path_state]
    ).then(
        update_library_browser,
        inputs=[current_path_state],
        outputs=[library_browser, current_path_display]
    )

    refresh_button.click(update_library_browser, inputs=[current_path_state], outputs=[library_browser, current_path_display])

    library_browser.change(
        handle_selection_and_path_update,
        inputs=[current_path_state, library_browser],
        outputs=[current_path_state]
    ).then(
        update_library_browser,
        inputs=[current_path_state],
        outputs=[library_browser, current_path_display]
    ).then(
        load_selected_file,
        inputs=[library_browser, current_path_state],
        outputs=[selected_audio_player, text_box]
    )

    rename_button.click(
        rename_library_item,
        inputs=[current_path_state, library_browser, new_name_input],
        outputs=[status_box, library_browser, current_path_display, new_name_input]
    )

    delete_button.click(
        delete_from_library,
        inputs=[current_path_state, library_browser],
        outputs=[status_box, library_browser, current_path_display, selected_audio_player, text_box]
    )


if __name__ == "__main__":
    # Crear el directorio de la biblioteca si no existe
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    demo.launch(share=True, debug=True)
