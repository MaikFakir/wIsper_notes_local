import os
import time
import traceback
import subprocess
import sys
from src.file_management import AUDIO_LIBRARY_PATH, list_library_contents, update_transcription_metadata

def run_transcription_process(file_path):
    """
    Runs the command-line transcriber in a separate process.
    Returns the transcription result.
    """
    print(f"Dispatcher: Starting transcription for {file_path}...")
    python_executable = sys.executable
    command = [python_executable, "-u", "transcribe_cli.py", file_path]

    # Using Popen to have more control and avoid blocking indefinitely in the same way.
    # It also helps with capturing stdout/stderr in real-time if needed, though here we wait.
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    try:
        # We use communicate with a timeout. This is a robust way to get output and handle hangs.
        stdout, stderr = process.communicate(timeout=300) # 5-minute timeout

        if process.returncode == 0:
            print(f"Dispatcher: Transcription for {file_path} succeeded.")
            return stdout.strip()
        else:
            error_message = stderr.strip()
            print(f"Dispatcher: Transcription process for {file_path} failed. Stderr: {error_message}")
            return f"Transcription failed: {error_message}"

    except subprocess.TimeoutExpired:
        process.kill() # Ensure the hung process is terminated
        stdout, stderr = process.communicate()
        print(f"Dispatcher: Transcription process for {file_path} timed out. Stderr: {stderr.strip()}")
        return "Transcription failed: Process timed out."

    except Exception as e:
        process.kill()
        print(f"Dispatcher: An unexpected error occurred. {e}")
        return f"Dispatcher error: {e}"


def main():
    """
    Main worker loop that scans for and processes files.
    """
    print("--- Audio Processing Dispatcher Started ---")
    print("Watching for files to process. Press Ctrl+C to exit.")

    while True:
        try:
            recordings = list_library_contents()
            files_to_process = [rec for rec in recordings if rec.get('status') == 'Processing']

            if files_to_process:
                print(f"Dispatcher: Found {len(files_to_process)} file(s) to process.")
                for recording in files_to_process:
                    relative_path = recording['path']
                    absolute_path = os.path.join(AUDIO_LIBRARY_PATH, relative_path)

                    transcription = run_transcription_process(absolute_path)

                    status = "Completed" if "failed" not in transcription.lower() and "error" not in transcription.lower() else "Failed"

                    update_transcription_metadata(relative_path, transcription, status)
                    print(f"Dispatcher: Updated metadata for {relative_path}. Status: {status}.")
            else:
                print("Dispatcher: No pending files found.")

        except Exception as e:
            print(f"An error occurred in the main dispatcher loop: {e}", file=sys.stderr)
            traceback.print_exc()

        time.sleep(10)

if __name__ == "__main__":
    main()