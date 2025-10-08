import sys
import os
import argparse
from src.audio_processing import transcribe_audio

def main():
    """
    Command-line interface for transcribing a single audio file.
    """
    parser = argparse.ArgumentParser(description="Transcribe a single audio file.")
    parser.add_argument("audio_path", help="The full path to the audio file.")
    parser.add_argument("--model", default="base", help="The transcription model to use (e.g., 'tiny', 'base', 'small').")

    args = parser.parse_args()

    if not os.path.exists(args.audio_path):
        print(f"Error: File not found at '{args.audio_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        # Call the transcription function with the specified model
        transcription = transcribe_audio(args.audio_path, model_name=args.model)
        # Print the result to standard output
        print(transcription)
    except Exception as e:
        print(f"An error occurred during transcription: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()