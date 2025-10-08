import os
import tempfile
import traceback
import ffmpeg
import torch
from faster_whisper import WhisperModel

# --- 1. MODEL MANAGEMENT (LAZY LOADING) ---

class ModelContainer:
    """A container to manage multiple transcription models, loading them lazily."""
    def __init__(self):
        self._models = {}
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.compute_type = "float16" if torch.cuda.is_available() else "int8"

    def load_model(self, model_name="base"):
        """Loads a model by name. If already loaded, returns the existing instance."""
        if model_name not in self._models:
            print(f"Loading transcription model (faster-whisper: {model_name})...")
            try:
                model = WhisperModel(model_name, device=self.device, compute_type=self.compute_type)
                self._models[model_name] = model
                print(f"Model '{model_name}' loaded successfully.")
            except Exception as e:
                print(f"FATAL: Error loading transcription model '{model_name}': {e}")
                # Don't raise here, allow fallback or error handling downstream
                return None
        return self._models.get(model_name)

MODELS = ModelContainer()

# --- 2. AUDIO PROCESSING UTILITIES ---

def _convert_audio_to_wav(input_path):
    """
    Converts any audio file to a temporary 16kHz mono WAV file for processing.
    """
    temp_wav = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_wav = temp_file.name

        (
            ffmpeg.input(input_path)
            .output(temp_wav, acodec='pcm_s16le', ac=1, ar='16k')
            .run(overwrite_output=True, quiet=True)
        )
        return temp_wav
    except Exception as e:
        print(f"Error during audio conversion: {e}")
        if temp_wav and os.path.exists(temp_wav):
            os.remove(temp_wav)
        raise

# --- 3. CORE TRANSCRIPTION LOGIC ---

def transcribe_audio(audio_path, model_name="base"):
    """
    Transcribes an audio file into plain text using a specified model.
    """
    if not audio_path or not os.path.exists(audio_path):
        return "Error: Audio file path is missing or invalid."

    temp_wav_path = None
    try:
        # Step 1: Ensure the requested model is ready
        transcription_model = MODELS.load_model(model_name)
        if not transcription_model:
            return f"Error: Could not load transcription model '{model_name}'."

        # Step 2: Convert audio to a standard format
        temp_wav_path = _convert_audio_to_wav(audio_path)

        # Step 3: Transcribe audio to get segments
        print(f"Starting transcription for {audio_path}...")
        segments_gen, _ = transcription_model.transcribe(temp_wav_path, language="es")

        # Step 4: Concatenate segments into a single text block
        full_transcription = " ".join(segment.text.strip() for segment in segments_gen)

        print(f"Transcription for {audio_path} complete.")
        return full_transcription

    except Exception as e:
        print(f"An unexpected error occurred during transcription: {e}")
        traceback.print_exc()
        return f"Error during transcription: {e}"
    finally:
        # Clean up the temporary WAV file
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)
            print(f"Temporary file {temp_wav_path} removed.")