import os
import json
import shutil
import re
from datetime import datetime
import librosa
import soundfile as sf
import gradio as gr

# --- CONSTANTES ---
AUDIO_LIBRARY_PATH = "audio_library"
METADATA_FILE = os.path.join(AUDIO_LIBRARY_PATH, "metadata.json")
VALID_FILENAME_REGEX = re.compile(r"^[a-zA-Z0-9_.-]+$")

# --- FUNCIONES DE LECTURA DEL SISTEMA DE ARCHIVOS ---

def get_all_directories(root=AUDIO_LIBRARY_PATH):
    """
    Obtiene recursivamente todos los directorios. Devuelve rutas relativas limpias.
    """
    if not os.path.exists(root):
        os.makedirs(root)
    dirs = ["."]
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for dirname in dirnames:
            full_path = os.path.join(dirpath, dirname)
            relative_path = os.path.relpath(full_path, root)
            dirs.append(relative_path)
    return sorted(list(set(dirs)))

def get_folder_contents(path="."):
    """
    Obtiene el contenido de una carpeta, devolviendo listas separadas para carpetas y archivos.
    """
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path) or path == "..":
        path = "."

    base_path = os.path.join(AUDIO_LIBRARY_PATH, path)
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    folders = []
    files = []
    for item in sorted(os.listdir(base_path)):
        full_item_path = os.path.join(base_path, item)
        if os.path.isdir(full_item_path):
            folders.append(item)
        elif item.lower().endswith(('.wav', '.mp3', '.flac')):
            files.append(item)
    return {"folders": folders, "files": files}

def get_audio_files_in_folder(path="."):
    """
    Obtiene solo los archivos de audio de una carpeta específica (para el visualizador).
    """
    contents = get_folder_contents(path)
    return contents["files"]

# --- METADATOS ---

def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_metadata(metadata):
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

# --- LÓGICA DEL VISUALIZADOR ---

def load_viewer_data(folder_path, filename):
    if not folder_path or not filename:
        return gr.update(value=None), gr.update(value="")

    file_path_in_library = os.path.join(AUDIO_LIBRARY_PATH, folder_path, filename)
    metadata_key = os.path.normpath(os.path.join(folder_path, filename))
    metadata = load_metadata()
    transcription = metadata.get(metadata_key, {}).get("transcription", "Transcripción no encontrada.")
    return gr.update(value=file_path_in_library), gr.update(value=transcription)

# --- FUNCIONES DE MANIPULACIÓN DE ARCHIVOS/CARPETAS (LÓGICA ROBUSTA) ---

def create_folder_in_library(base_path, new_folder_name):
    if not new_folder_name or not new_folder_name.strip():
        gr.Warning("El nombre de la carpeta no puede estar vacío.")
        return
    if not VALID_FILENAME_REGEX.match(new_folder_name):
        gr.Warning("Nombre de carpeta inválido. Use solo letras, números, guiones y puntos.")
        return

    folder_path = os.path.join(AUDIO_LIBRARY_PATH, base_path, new_folder_name)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        gr.Info(f"Carpeta '{new_folder_name}' creada en '{base_path}'.")
    else:
        gr.Warning(f"La carpeta '{new_folder_name}' ya existe en '{base_path}'.")

def save_transcription_to_library(destination_folder, audio_path, transcription):
    if not audio_path or not transcription:
        gr.Warning("No hay audio o transcripción para guardar.")
        return
    if not destination_folder:
        gr.Warning("Por favor, selecciona una carpeta de destino.")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_{timestamp}.wav"
    physical_save_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)
    metadata_key = os.path.normpath(os.path.join(destination_folder, filename))

    try:
        wav, sr = librosa.load(audio_path, sr=16000)
        sf.write(physical_save_path, wav, sr)
        metadata = load_metadata()
        metadata[metadata_key] = {"transcription": transcription, "timestamp": timestamp}
        save_metadata(metadata)
        gr.Info(f"¡Guardado! '{filename}' en '{destination_folder}'.")
    except Exception as e:
        gr.Error(f"Error al guardar el archivo de audio: {e}")

def rename_library_item(current_path, selection, new_name):
    if not selection or not new_name or not new_name.strip():
        gr.Warning("Selecciona un ítem y proporciona un nuevo nombre válido.")
        return
    if not VALID_FILENAME_REGEX.match(new_name):
        gr.Warning("Nombre nuevo inválido. Use solo letras, números, guiones y puntos.")
        return

    is_folder = selection.startswith("[C] ")
    old_name = selection.replace("[C] ", "")
    old_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, old_name)
    new_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_name)

    if not os.path.exists(old_path_full):
        gr.Error(f"Error: El ítem '{old_name}' no existe.")
        return
    if os.path.exists(new_path_full):
        gr.Error(f"Error: Ya existe un ítem con el nombre '{new_name}'.")
        return

    os.rename(old_path_full, new_path_full)
    metadata = load_metadata()
    if is_folder:
        old_prefix = os.path.normpath(os.path.join(current_path, old_name))
        new_prefix = os.path.normpath(os.path.join(current_path, new_name))
        metadata = { (new_prefix + k[len(old_prefix):] if k.startswith(old_prefix) else k): v for k, v in metadata.items() }
    else:
        old_key = os.path.normpath(os.path.join(current_path, old_name))
        if old_key in metadata:
            new_key = os.path.normpath(os.path.join(current_path, new_name))
            metadata[new_key] = metadata.pop(old_key)
    save_metadata(metadata)
    gr.Info(f"Ítem renombrado a '{new_name}'.")

def delete_library_item(current_path, selection):
    if not selection:
        gr.Warning("No se ha seleccionado ningún ítem para eliminar.")
        return

    is_folder = selection.startswith("[C] ")
    item_name = selection.replace("[C] ", "")
    path_to_delete = os.path.join(AUDIO_LIBRARY_PATH, current_path, item_name)

    if not os.path.exists(path_to_delete):
        gr.Error(f"Error: El ítem '{item_name}' no existe.")
        return

    metadata = load_metadata()
    if is_folder:
        shutil.rmtree(path_to_delete)
        prefix_to_delete = os.path.normpath(os.path.join(current_path, item_name))
        metadata = {k: v for k, v in metadata.items() if not k.startswith(prefix_to_delete)}
    else:
        os.remove(path_to_delete)
        key_to_delete = os.path.normpath(os.path.join(current_path, item_name))
        if key_to_delete in metadata:
            del metadata[key_to_delete]
    save_metadata(metadata)
    gr.Info(f"Ítem '{item_name}' eliminado.")

def move_library_item(current_path, selection, destination_folder):
    if not selection or selection.startswith("[C] "):
        gr.Warning("Por favor, selecciona un ARCHIVO para mover.")
        return
    if not destination_folder:
        gr.Warning("Por favor, selecciona una carpeta de destino.")
        return

    filename = selection
    source_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, filename)
    dest_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)

    if not os.path.exists(source_path):
        gr.Error(f"Error: El archivo '{filename}' no existe.")
        return
    if os.path.exists(dest_path):
        gr.Error(f"Error: Ya existe un archivo con ese nombre en el destino.")
        return

    shutil.move(source_path, dest_path)
    metadata = load_metadata()
    old_key = os.path.normpath(os.path.join(current_path, filename))
    new_key = os.path.normpath(os.path.join(destination_folder, filename))
    if old_key in metadata:
        metadata[new_key] = metadata.pop(old_key)
        save_metadata(metadata)
    gr.Info(f"Archivo '{filename}' movido a '{destination_folder}'.")