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

def get_folder_contents(path="."):
    """
    Obtiene solo las carpetas de un directorio para el navegador de carpetas.
    No prefija los nombres.
    """
    path = os.path.normpath(path)
    if path.startswith("..") or os.path.isabs(path):
        path = "."

    base_path = os.path.join(AUDIO_LIBRARY_PATH, path)
    folders = []
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    for item in sorted(os.listdir(base_path)):
        if os.path.isdir(os.path.join(base_path, item)):
            folders.append(item)
    return folders


def get_directory_contents(path="."):
    """
    Obtiene el contenido completo (carpetas y archivos .wav) de un directorio.
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
        full_item_path = os.path.join(base_path, item)
        if os.path.isdir(full_item_path):
            contents.append(f"[C] {item}")
        elif item.lower().endswith('.wav'):
            contents.append(item)

    return contents

def get_all_directories(root=AUDIO_LIBRARY_PATH):
    """
    Obtiene recursivamente todos los directorios para los menús desplegables.
    Devuelve rutas relativas a la raíz de la biblioteca.
    """
    dirs = ["."]  # Directorio raíz
    for dirpath, dirnames, _ in os.walk(root):
        # Limpiar dirnames para evitar entrar en directorios problemáticos si los hubiera
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]
        for dirname in dirnames:
            full_path = os.path.join(dirpath, dirname)
            relative_path = os.path.relpath(full_path, root)
            dirs.append(relative_path)
    return sorted(list(set(dirs)))


# --- FUNCIONES DE ACTUALIZACIÓN DE LA INTERFAZ (UI) ---

def update_folder_browser(current_path="."):
    """Actualiza solo el navegador de carpetas de la barra lateral."""
    # El navegador de carpetas siempre muestra el contenido de la carpeta actual
    choices = get_folder_contents(current_path)
    # Limpiar la selección para evitar clics accidentales
    return gr.update(choices=choices, value=None)

def update_library_browser(current_path="."):
    """Actualiza el navegador de archivos de la pestaña 'Archivos'."""
    choices = get_directory_contents(current_path)
    # Limpiar la selección
    return gr.update(choices=choices, value=None)

def update_all_views(current_path=".", status_message=""):
    """
    Función unificada para refrescar todas las vistas relevantes de la biblioteca.
    """
    # 1. Actualizar el navegador de carpetas de la barra lateral
    folder_browser_update = update_folder_browser(current_path)

    # 2. Actualizar el navegador de la pestaña 'Archivos'
    library_browser_update = update_library_browser(current_path)

    # 3. Actualizar la ruta visible
    path_display_update = gr.update(value=current_path)

    # 4. Actualizar los menús desplegables de carpetas
    all_dirs = get_all_directories()
    destination_folder_update = gr.update(choices=all_dirs)
    save_folder_update = gr.update(choices=all_dirs)

    # 5. Devolver todas las actualizaciones
    return (
        status_message,
        folder_browser_update,
        library_browser_update,
        path_display_update,
        destination_folder_update,
        save_folder_update
    )

# --- FUNCIONES DE MANEJO DE EVENTOS ---

def handle_folder_selection(selection, current_path):
    """
    Gestiona la selección en el navegador de carpetas de la barra lateral.
    Actualiza la ruta actual y refresca las vistas.
    """
    if selection is None:
        return current_path, gr.update(), gr.update()

    # Navegar a la subcarpeta
    new_path = os.path.join(current_path, selection)

    # Actualizar la vista de la biblioteca y la ruta visible
    library_browser_update = update_library_browser(new_path)
    path_display_update = gr.update(value=new_path)

    return new_path, library_browser_update, path_display_update


def handle_library_selection(selection, current_path):
    """
    Gestiona la selección en el navegador principal de la pestaña 'Archivos'.
    Navega si es una carpeta, carga en el visualizador si es un archivo.
    """
    if selection is None:
        # Evita errores si la selección se borra
        return current_path, gr.update(), gr.update(), gr.update(selected_tab=1)

    if selection.startswith("[C]"):
        # Navegar a la subcarpeta
        folder_name = selection.replace("[C] ", "")
        new_path = os.path.join(current_path, folder_name)

        # Refrescar todas las vistas para reflejar la nueva ruta
        _, folder_update, library_update, path_update, _, _ = update_all_views(new_path)

        # Devolver las actualizaciones y mantener la pestaña 'Archivos' seleccionada
        return new_path, folder_update, library_update, path_update, gr.update(selected_tab=1)
    else:
        # Es un archivo, cargarlo en el visualizador
        file_path_in_library = os.path.join(AUDIO_LIBRARY_PATH, current_path, selection)
        metadata_key = os.path.normpath(os.path.join(current_path, selection))

        transcription = "Transcripción no encontrada."
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                try:
                    metadata = json.load(f)
                    transcription = metadata.get(metadata_key, {}).get("transcription", "Transcripción no encontrada.")
                except (json.JSONDecodeError, AttributeError):
                    pass # Dejar la transcripción por defecto

        # Cambiar a la pestaña del visualizador y cargar los datos
        return current_path, gr.update(value=file_path_in_library), gr.update(value=transcription), gr.update(selected_tab=2)


def navigate_up(current_path):
    """Navega al directorio padre y actualiza el estado y las vistas."""
    new_path = "."
    if current_path != ".":
        new_path = os.path.dirname(current_path)

    # Refrescar todas las vistas desde la nueva ruta
    return new_path, *update_all_views(new_path, "Navegado hacia arriba.")[1:]


# --- FUNCIONES DE MANIPULACIÓN DE ARCHIVOS/CARPETAS ---

def create_folder_in_library(current_path, new_folder):
    """Crea una nueva carpeta en la ruta actual."""
    if not new_folder.strip() or ".." in new_folder or "/" in new_folder:
        return *update_all_views(current_path, "Nombre de carpeta inválido."), gr.update()

    folder_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_folder)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        status = f"Carpeta '{new_folder}' creada."
        # Limpiar el campo de texto después de crear
        return *update_all_views(current_path, status), gr.update(value="")
    else:
        status = f"La carpeta '{new_folder}' ya existe."
        return *update_all_views(current_path, status), gr.update()


def save_to_library(destination_folder, audio_path, transcription):
    """Guarda el audio y su transcripción en la carpeta de destino."""
    if not audio_path or not transcription:
        return "Nada que guardar.", gr.update()
    if not destination_folder:
        return "Por favor, selecciona una carpeta de destino.", gr.update()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"audio_{timestamp}.wav"

    physical_save_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)
    metadata_key = os.path.normpath(os.path.join(destination_folder, filename))

    try:
        wav, sr = librosa.load(audio_path, sr=16000)
        sf.write(physical_save_path, wav, sr)
    except Exception as e:
        return f"Error al guardar el archivo: {e}", gr.update()

    metadata = {}
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except json.JSONDecodeError:
                pass

    metadata[metadata_key] = {"transcription": transcription, "timestamp": timestamp}

    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

    status = f"¡Guardado! '{filename}' en '{destination_folder}'."
    # Después de guardar, refrescar la vista de la carpeta donde se guardó
    library_browser_update = update_library_browser(destination_folder)
    return status, library_browser_update


def rename_library_item(current_path, selection, new_name):
    """Renombra un archivo o carpeta."""
    if not selection or not new_name.strip():
        return *update_all_views(current_path, "Selecciona un item y proporciona un nuevo nombre."), gr.update()

    old_name = selection.replace("[C] ", "")
    new_name = new_name.strip()
    old_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, old_name)
    new_path_full = os.path.join(AUDIO_LIBRARY_PATH, current_path, new_name)

    if not os.path.exists(old_path_full):
        return *update_all_views(current_path, f"Error: El item '{old_name}' no existe."), gr.update()
    if os.path.exists(new_path_full):
        return *update_all_views(current_path, f"Error: Ya existe un item con el nombre '{new_name}'."), gr.update()

    # Lógica de renombrado (sin cambios)
    os.rename(old_path_full, new_path_full)

    # Actualización de metadatos (sin cambios)
    # ... (código de metadatos omitido por brevedad, es idéntico al original) ...

    status = f"Item renombrado a '{new_name}'."
    return *update_all_views(current_path, status), gr.update(value="")


def delete_from_library(current_path, selection):
    """Elimina un archivo o carpeta."""
    if not selection:
        return *update_all_views(current_path, "No se ha seleccionado ningún item."), gr.update(), gr.update()

    item_name = selection.replace("[C] ", "")
    path_to_delete = os.path.join(AUDIO_LIBRARY_PATH, current_path, item_name)

    if not os.path.exists(path_to_delete):
        return *update_all_views(current_path, f"Error: El item '{item_name}' no existe."), gr.update(), gr.update()

    # Lógica de eliminación (sin cambios)
    if os.path.isdir(path_to_delete):
        shutil.rmtree(path_to_delete)
    else:
        os.remove(path_to_delete)

    # Actualización de metadatos (sin cambios)
    # ... (código de metadatos omitido por brevedad, es idéntico al original) ...

    status = f"Item '{item_name}' eliminado."
    # Limpiar visualizador si se borra el item que se estaba viendo
    return *update_all_views(current_path, status), gr.update(value=None), gr.update(value="")

def move_library_item(current_path, selection, destination_folder):
    """Mueve un archivo seleccionado a otra carpeta."""
    if not selection or selection.startswith("[C]"):
        return *update_all_views(current_path, "Selecciona un archivo para mover."),

    if not destination_folder:
        return *update_all_views(current_path, "Selecciona una carpeta de destino."),

    filename = selection
    source_path = os.path.join(AUDIO_LIBRARY_PATH, current_path, filename)
    dest_path = os.path.join(AUDIO_LIBRARY_PATH, destination_folder, filename)

    if not os.path.exists(source_path):
        return *update_all_views(current_path, f"Error: El archivo '{filename}' no existe."),
    if os.path.exists(dest_path):
        return *update_all_views(current_path, f"Error: Ya existe un archivo con ese nombre en el destino."),

    # Lógica de movimiento y metadatos (sin cambios)
    shutil.move(source_path, dest_path)
    # ... (código de metadatos omitido por brevedad, es idéntico al original) ...

    status = f"Archivo '{filename}' movido a '{destination_folder}'."
    return *update_all_views(current_path, status),