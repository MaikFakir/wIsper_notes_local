import os
import json
import shutil
from datetime import datetime
import librosa
import soundfile as sf
import gradio as gr

# --- CONSTANTES ---
AUDIO_LIBRARY_PATH = "audio_library"
METADATA_FILE = os.path.join(AUDIO_LIBRARY_PATH, "metadata.json")

# --- FUNCIONES DE LECTURA DEL SISTEMA DE ARCHIVOS ---

def get_all_directories(root=AUDIO_LIBRARY_PATH):
    """
    Obtiene recursivamente todos los directorios para los menús desplegables.
    Devuelve rutas relativas a la raíz de la biblioteca.
    """
    if not os.path.exists(root):
        os.makedirs(root)
    dirs = ["."]  # Directorio raíz
    for dirpath, dirnames, _ in os.walk(root):
        # Limpiar dirnames para evitar entrar en directorios problemáticos
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for dirname in dirnames:
            full_path = os.path.join(dirpath, dirname)
            relative_path = os.path.relpath(full_path, root)
            dirs.append(relative_path)
    return sorted(list(set(dirs)))

def get_folder_items(path="."):
    """
    Obtiene el contenido de una carpeta, separando carpetas y archivos.
    """
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path):
        path = "."

    base_path = os.path.join(AUDIO_LIBRARY_PATH, path)
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    items = []
    for item in sorted(os.listdir(base_path)):
        full_item_path = os.path.join(base_path, item)
        if os.path.isdir(full_item_path):
            items.append(f"[C] {item}")
        elif item.lower().endswith(('.wav', '.mp3', '.flac')):
            items.append(item)
    return items

# --- METADATOS ---

def load_metadata():
    """Carga los metadatos desde el archivo JSON."""
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_metadata(metadata):
    """Guarda los metadatos en el archivo JSON."""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

# --- FUNCIONES DE MANIPULACIÓN DE ARCHIVOS/CARPETAS ---

def create_folder_in_library(current_path, new_folder):
    """Crea una nueva carpeta en la ruta actual."""
    if not new_folder.strip() or ".." in new_folder or "/" in new_folder:
        gr.Warning("Nombre de carpeta inválido.")
        # Devuelve actualizaciones vacías para no afectar los valores
        return gr.update(), gr.update(value="")

    folder_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        gr.Info(f"Carpeta '{new_folder}' creada.")
    else:
        gr.Warning(f"La carpeta '{new_folder}' ya existe.")

    # Devuelve la nueva lista de directorios y limpia el campo de texto
    return gr.update(choices=get_all_directories()), gr.update(value="")


def save_to_library(destination_folder, audio_path, transcription):
    """Guarda el audio y su transcripción en la carpeta de destino."""
    if not audio_path or not transcription:
        gr.Warning("No hay audio o transcripción para guardar.")
        return gr.update()
    if not destination_folder:
        gr.Warning("Por favor, selecciona una carpeta de destino.")
        return gr.update()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_{timestamp}.wav"

    physical_save_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)
    metadata_key = os.path.normpath(os.path.join(destination_folder, filename))

    try:
        wav, sr = librosa.load(audio_path, sr=16000)
        sf.write(physical_save_path, wav, sr)
    except Exception as e:
        gr.Error(f"Error al guardar el archivo de audio: {e}")
        return gr.update()

    metadata = load_metadata()
    metadata[metadata_key] = {"transcription": transcription, "timestamp": timestamp}
    save_metadata(metadata)

    gr.Info(f"¡Guardado! '{filename}' en '{destination_folder}'.")
    # Devuelve la lista de items actualizada de la carpeta de destino
    return gr.update(choices=get_folder_items(destination_folder))


def rename_library_item(current_path, selection, new_name):
    """Renombra un archivo o carpeta seleccionada."""
    if not selection or not new_name.strip():
        gr.Warning("Selecciona un ítem y proporciona un nuevo nombre.")
        return gr.update(), gr.update()

    old_name = selection.replace("[C] ", "")
    new_name = new_name.strip()

    old_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, old_name)
    new_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_name)

    if not os.path.exists(old_path_full):
        gr.Error(f"Error: El ítem '{old_name}' no existe.")
        return gr.update(), gr.update()
    if os.path.exists(new_path_full):
        gr.Error(f"Error: Ya existe un ítem con el nombre '{new_name}'.")
        return gr.update(), gr.update()

    os.rename(old_path_full, new_path_full)

    metadata = load_metadata()
    # Si es una carpeta, actualiza todos los metadatos que la contengan
    if selection.startswith("[C]"):
        updated_metadata = {}
        old_prefix = os.path.normpath(os.path.join(current_path, old_name))
        new_prefix = os.path.normpath(os.path.join(current_path, new_name))
        for key, value in metadata.items():
            if key.startswith(old_prefix + os.path.sep):
                new_key = new_prefix + key[len(old_prefix):]
                updated_metadata[new_key] = value
            else:
                updated_metadata[key] = value
        metadata = updated_metadata
    # Si es un archivo, actualiza solo su clave
    else:
        old_key = os.path.normpath(os.path.join(current_path, old_name))
        new_key = os.path.normpath(os.path.join(current_path, new_name))
        if old_key in metadata:
            metadata[new_key] = metadata.pop(old_key)

    save_metadata(metadata)

    gr.Info(f"Ítem renombrado a '{new_name}'.")
    return gr.update(choices=get_folder_items(current_path)), gr.update(value="")


def delete_from_library(current_path, selection):
    """Elimina un archivo o carpeta seleccionada."""
    if not selection:
        gr.Warning("No se ha seleccionado ningún ítem para eliminar.")
        return gr.update(), gr.update(), gr.update()

    item_name = selection.replace("[C] ", "")
    path_to_delete = os.path.join(AUDIO_LIBRARY_PATH, current_path, item_name)

    if not os.path.exists(path_to_delete):
        gr.Error(f"Error: El ítem '{item_name}' no existe.")
        return gr.update(), gr.update(), gr.update()

    metadata = load_metadata()
    if os.path.isdir(path_to_delete):
        shutil.rmtree(path_to_delete)
        # Eliminar metadatos de la carpeta
        prefix_to_delete = os.path.normpath(os.path.join(current_path, item_name))
        metadata = {k: v for k, v in metadata.items() if not k.startswith(prefix_to_delete)}
    else:
        os.remove(path_to_delete)
        key_to_delete = os.path.normpath(os.path.join(current_path, item_name))
        if key_to_delete in metadata:
            del metadata[key_to_delete]

    save_metadata(metadata)

    gr.Info(f"Ítem '{item_name}' eliminado.")
    return gr.update(choices=get_folder_items(current_path)), gr.update(value=None), gr.update(value="")


def move_library_item(current_path, selection, destination_folder):
    """Mueve un archivo seleccionado a otra carpeta."""
    if not selection or selection.startswith("[C]"):
        gr.Warning("Por favor, selecciona un archivo para mover.")
        return gr.update()
    if not destination_folder:
        gr.Warning("Por favor, selecciona una carpeta de destino.")
        return gr.update()

    filename = selection
    source_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, filename)
    dest_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)

    if not os.path.exists(source_path):
        gr.Error(f"Error: El archivo '{filename}' no existe.")
        return gr.update()
    if os.path.exists(dest_path):
        gr.Error(f"Error: Ya existe un archivo con ese nombre en el destino.")
        return gr.update()

    shutil.move(source_path, dest_path)

    metadata = load_metadata()
    old_key = os.path.normpath(os.path.join(current_path, filename))
    new_key = os.path.normpath(os.path.join(destination_folder, filename))
    if old_key in metadata:
        metadata[new_key] = metadata.pop(old_key)
        save_metadata(metadata)

    gr.Info(f"Archivo '{filename}' movido a '{destination_folder}'.")
    return gr.update(choices=get_folder_items(current_path))

# --- HANDLERS PARA LA UI ---

def get_audio_files_in_folder(path="."):
    """
    Obtiene solo los archivos de audio de una carpeta específica.
    """
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path):
        path = "."

    base_path = os.path.join(AUDIO_LIBRARY_PATH, path)
    if not os.path.exists(base_path):
        return []

    audio_files = []
    for item in sorted(os.listdir(base_path)):
        if os.path.isfile(os.path.join(base_path, item)) and item.lower().endswith(('.wav', '.mp3', '.flac')):
            audio_files.append(item)
    return audio_files

def load_viewer_data(folder_path, filename):
    """
    Carga el audio y la transcripción para un archivo seleccionado en el visualizador.
    """
    if not folder_path or not filename:
        # No selection, return empty updates
        return gr.update(value=None), gr.update(value="")

    file_path_in_library = os.path.join(AUDIO_LIBRARY_PATH, folder_path, filename)
    metadata_key = os.path.normpath(os.path.join(folder_path, filename))

    metadata = load_metadata()
    transcription = metadata.get(metadata_key, {}).get("transcription", "Transcripción no encontrada.")

    return gr.update(value=file_path_in_library), gr.update(value=transcription)


def handle_folder_change(selected_folder):
    """
    Se activa al cambiar el dropdown de carpetas.
    Actualiza la ruta actual y la lista de archivos.
    """
    return selected_folder, gr.update(choices=get_folder_items(selected_folder), value=None)

def handle_file_selection(selection, current_path):
    """
    Se activa al seleccionar un ítem en la lista de archivos.
    Si es una carpeta, navega. Si es un archivo, lo carga en el visualizador.
    """
    # Siempre debe devolver 6 valores para coincidir con los outputs de la UI
    if selection is None:
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    if selection.startswith("[C]"):
        folder_name = selection.replace("[C] ", "")
        new_path = os.path.join(current_path, folder_name)
        # Actualiza el dropdown de la barra lateral al nuevo path
        # y la lista de archivos de la pestaña de archivos
        return (
            gr.update(value=new_path),  # current_path_state
            gr.update(choices=get_folder_items(new_path), value=None),  # library_browser
            gr.update(),  # selected_audio_player
            gr.update(),  # selected_transcription_display
            gr.update(),  # tabs
            gr.update(value=new_path)  # folder_selector_sidebar
        )
    else: # Es un archivo
        file_path_in_library = os.path.join(AUDIO_LIBRARY_PATH, current_path, selection)
        metadata_key = os.path.normpath(os.path.join(current_path, selection))
        metadata = load_metadata()
        transcription = metadata.get(metadata_key, {}).get("transcription", "Transcripción no encontrada.")

        # Cambiar a la pestaña del visualizador y cargar los datos
        return (
            gr.update(),  # current_path_state
            gr.update(),  # library_browser
            gr.update(value=file_path_in_library),  # selected_audio_player
            gr.update(value=transcription),  # selected_transcription_display
            gr.update(selected=2),  # tabs
            gr.update()  # folder_selector_sidebar
        )