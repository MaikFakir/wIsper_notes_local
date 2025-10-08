import os
import time
import traceback
import subprocess
import sys
from src.file_management import AUDIO_LIBRARY_PATH, _load_metadata, update_transcription_metadata

def run_transcription_process(file_path, model_name="base"):
    """
    Runs the command-line transcriber in a separate process, specifying the model.
    """
    print(f"Dispatcher: Starting transcription for {file_path} using model '{model_name}'...")
    python_executable = sys.executable
    command = [
        python_executable,
        "-u",
        "transcribe_cli.py",
        file_path,
        "--model",
        model_name
    ]

    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        stdout, stderr = process.communicate(timeout=600) # 10-minute timeout for larger models

        if process.returncode == 0:
            print(f"Dispatcher: Transcription for {file_path} succeeded.")
            return stdout.strip()
        else:
            error_message = stderr.strip()
            print(f"Dispatcher: Transcription process for {file_path} failed. Stderr: {error_message}")
            return f"Transcription failed: {error_message}"

    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        print(f"Dispatcher: Transcription for {file_path} timed out. Stderr: {stderr.strip()}")
        return "Transcription failed: Process timed out."
    except Exception as e:
        process.kill()
        print(f"Dispatcher: An unexpected error occurred. {e}")
        return f"Dispatcher error: {e}"

def main():
    """
    Main worker loop that scans for and processes files based on metadata.
    """
    print("--- Audio Processing Dispatcher Started ---")
    print("Watching for files to process. Press Ctrl+C to exit.")

    while True:
        try:
            all_metadata = _load_metadata()
            files_to_process = []
            for path, data in all_metadata.items():
                # Ensure the item is a file with a 'status' key
                if isinstance(data, dict) and data.get('status') == 'Processing':
                    # Add path to the data so we can use it later
                    data['path'] = path
                    files_to_process.append(data)

            if files_to_process:
                print(f"Dispatcher: Found {len(files_to_process)} file(s) to process.")
                for recording_data in files_to_process:
                    relative_path = recording_data['path']
                    model = recording_data.get('model', 'base') # Default to 'base'
                    absolute_path = os.path.join(AUDIO_LIBRARY_PATH, relative_path)

                    if not os.path.exists(absolute_path):
                        print(f"Warning: File '{relative_path}' found in metadata but not on disk. Skipping.")
                        continue

                    transcription = run_transcription_process(absolute_path, model)

                    status = "Completed" if "failed" not in transcription.lower() and "error" not in transcription.lower() else "Failed"

                    update_transcription_metadata(relative_path, transcription, status)
                    print(f"Dispatcher: Updated metadata for {relative_path}. Status: {status}.")
            else:
                # This message is useful for debugging to know the worker is alive.
                # print("Dispatcher: No pending files found.")
                pass

        except Exception as e:
            print(f"An error occurred in the main dispatcher loop: {e}", file=sys.stderr)
            traceback.print_exc()

        time.sleep(10)

if __name__ == "__main__":
    main()