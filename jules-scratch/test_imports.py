import sys

print("--- STARTING IMPORT TEST ---", flush=True)

try:
    print("Importing: os", flush=True)
    import os
    print("Success: os", flush=True)

    print("Importing: tempfile", flush=True)
    import tempfile
    print("Success: tempfile", flush=True)

    print("Importing: ffmpeg", flush=True)
    import ffmpeg
    print("Success: ffmpeg", flush=True)

    print("Importing: torch", flush=True)
    import torch
    print("Success: torch", flush=True)

    print("Importing: faster_whisper", flush=True)
    from faster_whisper import WhisperModel
    print("Success: faster_whisper", flush=True)

    print("Importing: gradio", flush=True)
    import gradio
    print("Success: gradio", flush=True)

    print("--- ALL IMPORTS SUCCEEDED ---", flush=True)

except Exception as e:
    print(f"--- IMPORT FAILED ---", flush=True)
    print(f"Error: {e}", flush=True)
    sys.exit(1)