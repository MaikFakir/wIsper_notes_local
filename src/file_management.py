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

def list_library_contents():
    """
    Scans the audio library and returns a structured list of all audio files.
    """
    file_list = []
    metadata = _load_metadata()

    # Ensure library path exists
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)

    for root, _, files in os.walk(AUDIO_LIBRARY_PATH):
        for file in files:
            if file == os.path.basename(METADATA_FILE) or file.startswith('.'):
                continue

            if file.lower().endswith(('.wav', '.mp3', '.m4a', '.ogg', '.flac')):
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, AUDIO_LIBRARY_PATH)

                try:
                    date_modified_ts = os.path.getmtime(full_path)
                    date_modified = datetime.fromtimestamp(date_modified_ts).strftime("%B %d, %Y")
                    # Duration calculation removed for stability
                    duration_formatted = "--:--"

                except Exception as e:
                    print(f"Could not process file metadata for {full_path}: {e}")
                    date_modified = "Unknown"
                    duration_formatted = "N/A"

                file_metadata = metadata.get(str(relative_path), {})
                status = file_metadata.get("status", "Processing") # Default to processing

                file_list.append({
                    "fileName": file,
                    "duration": duration_formatted,
                    "dateCreated": date_modified,
                    "status": status,
                    "path": str(relative_path)
                })

    # Sort by date, most recent first
    try:
        file_list.sort(key=lambda x: datetime.strptime(x['dateCreated'], "%B %d, %Y") if x['dateCreated'] != 'Unknown' else datetime.min, reverse=True)
    except ValueError as e:
        print(f"Error sorting files by date: {e}")

    return file_list

def save_uploaded_file(file_storage):
    """
    Saves an uploaded file to the audio library.
    """
    if not file_storage:
        return {"error": "No file provided"}, 400

    filename = file_storage.filename
    # Avoid path traversal attacks
    if ".." in filename or filename.startswith("/"):
        return {"error": "Invalid filename"}, 400

    # Create a unique filename to avoid overwrites
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base, ext = os.path.splitext(filename)
    safe_filename = f"{base}_{timestamp}{ext}"

    save_path = os.path.join(AUDIO_LIBRARY_PATH, safe_filename)

    try:
        file_storage.save(save_path)

        # Add a basic entry to metadata
        metadata = _load_metadata()
        relative_path = os.path.relpath(save_path, AUDIO_LIBRARY_PATH)
        metadata[str(relative_path)] = {"status": "Processing"}
        _save_metadata(metadata)

        return {
            "message": f"File '{safe_filename}' uploaded successfully",
            "filePath": str(relative_path)
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
