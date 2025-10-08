import os
import json
import shutil
from datetime import datetime

# --- CONSTANTS ---
AUDIO_LIBRARY_PATH = "audio_library"
METADATA_FILE = os.path.join(AUDIO_LIBRARY_PATH, "metadata.json")

# --- METADATA HELPERS ---

def _load_metadata():
    """Loads the metadata file."""
    if not os.path.exists(METADATA_FILE):
        return {}
    # Create backup and handle empty or corrupted file
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            # Check if file is empty
            if os.path.getsize(METADATA_FILE) == 0:
                return {}
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # If file is corrupted or not found, create a backup and return empty metadata
        if os.path.exists(METADATA_FILE):
            shutil.copyfile(METADATA_FILE, f"{METADATA_FILE}.bak_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        return {}


def _save_metadata(metadata):
    """Saves the metadata file."""
    with open(METADATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

# --- API-FACING FUNCTIONS ---

def list_directory_contents(relative_dir_path="."):
    """
    Scans a specific directory within the audio library and returns a flat list
    of its contents (folders and files). The path is relative to the audio library root.
    """
    # Sanitize path to prevent traversal attacks
    if ".." in relative_dir_path:
        return []

    # Use os.path.abspath to resolve the path and prevent directory traversal
    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    path_to_scan = os.path.abspath(os.path.join(library_root, relative_dir_path))

    # Security check: ensure the resolved path is still within the library
    if not path_to_scan.startswith(library_root):
        return []

    # Create the directory if it doesn't exist, e.g., on first run
    if not os.path.exists(path_to_scan):
        os.makedirs(path_to_scan, exist_ok=True)
        return []

    items = []
    metadata = _load_metadata()

    # First, process directories
    for entry_name in sorted(os.listdir(path_to_scan)):
        full_path = os.path.join(path_to_scan, entry_name)
        if os.path.isdir(full_path) and not entry_name.startswith('.'):
            relative_path = os.path.relpath(full_path, AUDIO_LIBRARY_PATH)
            items.append({
                "type": "folder",
                "name": entry_name,
                "path": str(relative_path).replace('\\', '/')
            })

    # Then, process files
    for entry_name in sorted(os.listdir(path_to_scan)):
        full_path = os.path.join(path_to_scan, entry_name)
        if os.path.isfile(full_path):
            # Skip metadata file and hidden files
            if entry_name == os.path.basename(METADATA_FILE) or entry_name.startswith('.'):
                continue

            if entry_name.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg', '.flac')):
                relative_path = os.path.relpath(full_path, AUDIO_LIBRARY_PATH)
                try:
                    date_modified_ts = os.path.getmtime(full_path)
                    date_modified = datetime.fromtimestamp(date_modified_ts).strftime("%B %d, %Y")
                    duration_formatted = "--:--"
                except Exception as e:
                    print(f"Could not process file metadata for {full_path}: {e}")
                    date_modified = "Unknown"
                    duration_formatted = "N/A"

                file_metadata = metadata.get(str(relative_path), {})
                status = file_metadata.get("status", "Processing")

                items.append({
                    "type": "file",
                    "fileName": entry_name,
                    "duration": duration_formatted,
                    "dateCreated": date_modified,
                    "status": status,
                    "path": str(relative_path).replace('\\', '/')
                })
    return items

def get_library_tree():
    """
    Recursively scans the audio library and returns a nested structure of folders.
    """
    def _scan_dir(path):
        folders = []
        try:
            for entry in os.scandir(path):
                if entry.is_dir() and not entry.name.startswith('.'):
                    relative_path = os.path.relpath(entry.path, AUDIO_LIBRARY_PATH)
                    children = _scan_dir(entry.path)
                    folder_data = {
                        "type": "folder",
                        "name": entry.name,
                        "path": str(relative_path).replace('\\', '/'),
                        "children": children
                    }
                    folders.append(folder_data)
        except FileNotFoundError:
            return [] # Return empty list if path doesn't exist
        # Sort folders by name for consistent ordering
        return sorted(folders, key=lambda f: f['name'])

    # Ensure the root library path exists before scanning
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)

    return _scan_dir(AUDIO_LIBRARY_PATH)

def create_folder(new_folder_path):
    """
    Creates a new folder inside the audio library.
    The path is relative to the audio library root.
    """
    # Sanitize path to prevent traversal attacks
    if ".." in new_folder_path or os.path.isabs(new_folder_path):
        return {"error": "Invalid folder path"}, 400

    # Use os.path.abspath to resolve the path and prevent directory traversal
    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    full_path = os.path.abspath(os.path.join(library_root, new_folder_path))

    # Security check: ensure the resolved path is still within the library
    if not full_path.startswith(library_root):
        return {"error": "Invalid folder path"}, 400

    if os.path.exists(full_path):
        return {"error": "Folder already exists"}, 409 # HTTP 409 Conflict

    try:
        os.makedirs(full_path)
        return {"message": f"Folder '{new_folder_path}' created successfully"}, 201
    except Exception as e:
        print(f"Error creating folder {new_folder_path}: {e}")
        return {"error": "Could not create folder"}, 500

def save_uploaded_file(file_storage, destination_folder=".", model="base"):
    """
    Saves an uploaded file to a specific folder within the audio library
    and records the selected transcription model.
    """
    if not file_storage:
        return {"error": "No file provided"}, 400

    filename = file_storage.filename
    # Security checks for filename
    if ".." in filename or os.path.isabs(filename):
        return {"error": "Invalid filename"}, 400

    # Security checks for destination folder
    if ".." in destination_folder or os.path.isabs(destination_folder):
        return {"error": "Invalid destination folder"}, 400

    # Resolve the destination path safely
    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    destination_path = os.path.abspath(os.path.join(library_root, destination_folder))

    # Final security check to ensure we are still inside the library
    if not destination_path.startswith(library_root):
        return {"error": "Invalid destination folder"}, 400

    # Create the destination directory if it doesn't exist
    os.makedirs(destination_path, exist_ok=True)

    # Create a unique filename to avoid overwrites
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(filename)
    safe_filename = f"{base.replace(' ', '_')}_{timestamp}{ext}"

    save_path = os.path.join(destination_path, safe_filename)

    try:
        file_storage.save(save_path)

        # Add a basic entry to metadata, now including the model
        metadata = _load_metadata()
        relative_path = os.path.relpath(save_path, AUDIO_LIBRARY_PATH)
        metadata[str(relative_path).replace('\\', '/')] = {
            "status": "Processing",
            "model": model
        }
        _save_metadata(metadata)

        return {
            "message": f"File '{safe_filename}' uploaded successfully to '{destination_folder}'",
            "filePath": str(relative_path).replace('\\', '/')
        }, 201

    except Exception as e:
        print(f"Error saving file {safe_filename}: {e}")
        return {"error": "Could not save file"}, 500


def delete_recording(file_path):
    """
    Deletes a recording from the library and its metadata.
    """
    if ".." in file_path or os.path.isabs(file_path):
        return {"error": "Invalid file path"}, 400

    full_path = os.path.join(AUDIO_LIBRARY_PATH, file_path)

    if not os.path.exists(full_path):
        return {"error": "File not found"}, 404

    try:
        os.remove(full_path)

        # Remove from metadata
        metadata = _load_metadata()
        relative_path = os.path.relpath(full_path, AUDIO_LIBRARY_PATH)
        if str(relative_path) in metadata:
            del metadata[str(relative_path)]
            _save_metadata(metadata)

        return {"message": f"File '{file_path}' deleted successfully"}, 200

    except Exception as e:
        print(f"Error deleting file {file_path}: {e}")
        return {"error": "Could not delete file"}, 500

def update_transcription_metadata(file_path, transcription, status):
    """
    Updates the metadata for a specific file with its transcription and status.
    """
    if ".." in file_path or os.path.isabs(file_path):
        print(f"Invalid path provided to update_transcription_metadata: {file_path}")
        return

    metadata = _load_metadata()

    # The key in metadata is the relative path
    if file_path in metadata:
        metadata[file_path]["transcription"] = transcription
        metadata[file_path]["status"] = status
    else:
        # This case might happen if the file was added but metadata wasn't created
        metadata[file_path] = {
            "transcription": transcription,
            "status": status
        }

    _save_metadata(metadata)

def rename_item(relative_path, new_name):
    """
    Renames a file or folder and updates its metadata.
    """
    # Security checks
    if ".." in relative_path or os.path.isabs(relative_path) or ".." in new_name or "/" in new_name:
        return {"error": "Invalid path or name"}, 400

    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    old_full_path = os.path.abspath(os.path.join(library_root, relative_path))

    if not old_full_path.startswith(library_root) or not os.path.exists(old_full_path):
        return {"error": "File or folder not found"}, 404

    # Construct new path
    new_full_path = os.path.join(os.path.dirname(old_full_path), new_name)
    new_relative_path = os.path.relpath(new_full_path, library_root)

    if os.path.exists(new_full_path):
        return {"error": "An item with the new name already exists"}, 409

    try:
        # Rename the actual file/folder
        os.rename(old_full_path, new_full_path)

        # Update metadata
        metadata = _load_metadata()
        updated_metadata = {}
        for key, value in metadata.items():
            if key == relative_path:
                updated_metadata[new_relative_path] = value
            elif key.startswith(relative_path + '/'):
                new_key = new_relative_path + key[len(relative_path):]
                updated_metadata[new_key] = value
            else:
                updated_metadata[key] = value
        _save_metadata(updated_metadata)

        return {"message": "Item renamed successfully"}, 200

    except Exception as e:
        print(f"Error renaming item '{relative_path}': {e}")
        return {"error": "Could not rename item"}, 500

def move_item(source_relative_path, dest_relative_path):
    """
    Moves a file or folder to a new destination and updates metadata.
    """
    # Security checks
    if ".." in source_relative_path or os.path.isabs(source_relative_path) or \
       ".." in dest_relative_path or os.path.isabs(dest_relative_path):
        return {"error": "Invalid source or destination path"}, 400

    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    source_full_path = os.path.abspath(os.path.join(library_root, source_relative_path))
    dest_full_path = os.path.abspath(os.path.join(library_root, dest_relative_path))

    # Check if source exists and is in the library
    if not source_full_path.startswith(library_root) or not os.path.exists(source_full_path):
        return {"error": "Source item not found"}, 404

    # Check if destination is in the library
    if not dest_full_path.startswith(library_root):
        return {"error": "Invalid destination"}, 400

    # Ensure destination is a directory
    if os.path.exists(dest_full_path) and not os.path.isdir(dest_full_path):
        return {"error": "Destination is not a folder"}, 400

    os.makedirs(dest_full_path, exist_ok=True)

    # Final destination path for the moved item
    final_path = os.path.join(dest_full_path, os.path.basename(source_full_path))
    final_relative_path = os.path.relpath(final_path, library_root)

    if os.path.exists(final_path):
        return {"error": "An item with the same name already exists in the destination"}, 409

    try:
        # Move the file/folder
        shutil.move(source_full_path, final_path)

        # Update metadata
        metadata = _load_metadata()
        updated_metadata = {}
        for key, value in metadata.items():
            if key == source_relative_path:
                updated_metadata[final_relative_path] = value
            elif key.startswith(source_relative_path + '/'):
                new_key = final_relative_path + key[len(source_relative_path):]
                updated_metadata[new_key] = value
            else:
                updated_metadata[key] = value
        _save_metadata(updated_metadata)

        return {"message": "Item moved successfully"}, 200

    except Exception as e:
        print(f"Error moving item '{source_relative_path}': {e}")
        return {"error": "Could not move item"}, 500

def get_file_details(relative_path):
    """
    Retrieves all available details for a single file, including its transcription.
    """
    # Security checks
    if ".." in relative_path or os.path.isabs(relative_path):
        return {"error": "Invalid file path"}, 400

    library_root = os.path.abspath(AUDIO_LIBRARY_PATH)
    full_path = os.path.abspath(os.path.join(library_root, relative_path))

    if not full_path.startswith(library_root) or not os.path.isfile(full_path):
        return {"error": "File not found"}, 404

    metadata = _load_metadata()
    file_metadata = metadata.get(relative_path, {})

    details = {
        "fileName": os.path.basename(relative_path),
        "path": relative_path,
        "status": file_metadata.get("status", "Unknown"),
        "transcription": file_metadata.get("transcription", None),
        "spectrogram": file_metadata.get("spectrogram", None) # Placeholder for now
    }

    return details, 200
