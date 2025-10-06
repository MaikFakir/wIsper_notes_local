import os
import json
import shutil
from datetime import datetime
import librosa
import soundfile as sf
import gradio as gr

# --- CONSTANTES ---
# Define paths relative to this file's location to make them absolute and robust.
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)  # Assumes src/ is one level down from root
AUDIO_LIBRARY_PATH = os.path.join(_PROJECT_ROOT, "audio_library")
METADATA_FILE = os.path.join(AUDIO_LIBRARY_PATH, "metadata.json")

# --- FUNCIONES DE GESTIÓN DE LA BIBLIOTECA ---

def get_directory_contents(path="."):
    """
    Obtiene el contenido de un directorio dentro de la biblioteca de audios.
    Prefija las carpetas con '[C]' para distinguirlas.
    """
    path = os.path.normpath(path)
    # Basic security check
    if ".." in path.split(os.sep) or os.path.isabs(path):
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
    """Renombra un archivo o carpeta y devuelve un mensaje de estado."""
    if not selection or not new_name.strip():
        return "Selecciona un item y proporciona un nuevo nombre."

    old_name = selection.replace("[C] ", "")
    new_name = new_name.strip()
    old_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, old_name)
    new_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_name)

    if not os.path.exists(old_path_full):
        return f"Error: El item '{old_name}' no existe."
    if os.path.exists(new_path_full):
        return f"Error: Ya existe un item con el nombre '{new_name}'."

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
        for key, value in metadata.items():
            if key.startswith(old_metadata_key_base + os.sep):
                new_key = new_metadata_key_base + key[len(old_metadata_key_base):]
                new_metadata[new_key] = value
            elif key != old_metadata_key_base:
                new_metadata[key] = value
    else:  # Si es un archivo
        old_metadata_key = old_metadata_key_base
        new_metadata_key = new_metadata_key_base
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

    return f"Item renombrado a '{new_name}'."


def delete_from_library(current_path, selection):
    """Elimina un archivo o carpeta y devuelve un mensaje de estado."""
    if not selection:
        return "No se ha seleccionado ningún item."

    item_name = selection.replace("[C] ", "")
    path_to_delete_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, item_name)

    if not os.path.exists(path_to_delete_full):
         return f"Error: El item '{item_name}' no existe."

    if os.path.isdir(path_to_delete_full):
        shutil.rmtree(path_to_delete_full)
    else:
        os.remove(path_to_delete_full)

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
        if not (key == metadata_key_to_delete or key.startswith(metadata_key_to_delete + os.sep)):
            new_metadata[key] = value

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(new_metadata, f, indent=4, ensure_ascii=False)

    return f"Item '{item_name}' eliminado."

def get_file_data(current_path, selection):
    """
    Obtiene la ruta y la transcripción de un archivo seleccionado.
    """
    if selection is None or selection.startswith("[C]"):
        return None, "Selecciona un archivo para ver su transcripción."

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