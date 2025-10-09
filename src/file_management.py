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
