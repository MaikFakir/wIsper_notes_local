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

# --- FUNCIONES DE GESTIÓN DE LA BIBLIOTECA ---

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


def get_all_directories(root=AUDIO_LIBRARY_PATH):
    """
    Recursively gets all directory paths within the audio library.
    Returns paths relative to the library root.
    """
    dirs = ["."]  # Incluir el directorio raíz
    for dirpath, dirnames, _ in os.walk(root):
        # Filtrar para evitar incluir el propio directorio raíz dos veces o subdirectorios problemáticos
        if dirpath == root:
            # Para el directorio raíz, procesamos solo sus subdirectorios
            for dirname in dirnames:
                dirs.append(dirname)
        else:
            # Para subdirectorios, construimos la ruta relativa
            for dirname in dirnames:
                full_path = os.path.join(dirpath, dirname)
                relative_path = os.path.relpath(full_path, root)
                dirs.append(relative_path)

    # Asegurarse de que no haya duplicados y ordenar
    return sorted(list(set(dirs)))


def move_library_item(current_path, selection, destination_folder):
    """Mueve un archivo seleccionado a otra carpeta."""
    if not selection or selection.startswith("[C]"):
        return "Por favor, selecciona un archivo (no una carpeta) para mover.", gr.update(), gr.update(), gr.update()

    if not destination_folder:
        return "Por favor, selecciona una carpeta de destino.", gr.update(), gr.update(), gr.update()

    filename = selection
    source_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, filename)
    destination_path_full = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)

    if not os.path.exists(source_path_full):
        return f"Error: El archivo '{filename}' no existe en la ubicación actual.", gr.update(), gr.update(), gr.update()
    if os.path.exists(destination_path_full):
        return f"Error: Ya existe un archivo con el nombre '{filename}' en la carpeta de destino.", gr.update(), gr.update(), gr.update()

    try:
        shutil.move(source_path_full, destination_path_full)
    except Exception as e:
        return f"Error al mover el archivo: {e}", gr.update(), gr.update(), gr.update()

    # Actualizar metadatos
    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                pass  # El archivo se sobreescribirá si está corrupto

    old_metadata_key = os.path.normpath(os.path.join(current_path, filename))
    new_metadata_key = os.path.normpath(os.path.join(destination_folder, filename))

    if old_metadata_key in metadata:
        metadata[new_metadata_key] = metadata.pop(old_metadata_key)

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    # Refrescar la vista actual de la biblioteca
    browser_update, path_update = update_library_browser(current_path)
    # También es útil actualizar las carpetas de destino por si se ha creado una nueva
    destination_choices = get_all_directories()

    return f"Archivo '{filename}' movido a '{destination_folder}'.", browser_update, path_update, gr.update(choices=destination_choices, value=None)


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

def handle_library_selection(selection, current_path):
    """
    Gestiona la selección en la biblioteca.
    Navega si es una carpeta, carga si es un archivo.
    """
    if selection is None:
        # Esto ocurre tras una navegación o refresco, no hacer nada para no limpiar el reproductor.
        return current_path, gr.update(), gr.update(), gr.update(), gr.update()

    if selection.startswith("[C]"):
        # Navegar a la carpeta
        folder_name = selection.replace("[C] ", "")
        new_path = os.path.join(current_path, folder_name)
        browser_update, path_update = update_library_browser(new_path)
        # Limpiar reproductor y texto al navegar
        return new_path, None, "", browser_update, path_update
    else:
        # Cargar un archivo de audio
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

        # Actualizar solo el reproductor y la transcripción, sin refrescar el browser.
        return current_path, file_path_in_library, transcription, gr.update(), gr.update()

def navigate_up(current_path):
    """Navega al directorio padre y actualiza el estado."""
    new_path = "."
    if current_path != ".":
        new_path = os.path.dirname(current_path)
    return new_path