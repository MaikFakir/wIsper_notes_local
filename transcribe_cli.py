import sys
import os
from src.audio_processing import transcribe_audio

def main():
    """
    Command-line interface for transcribing a single audio file.
    Takes a file path as its only argument and prints the transcription result.
    """
    if len(sys.argv) != 2:
        print("Usage: python transcribe_cli.py <path_to_audio_file>", file=sys.stderr)
        sys.exit(1)

    audio_path = sys.argv[1]

    if not os.path.exists(audio_path):
        print(f"Error: File not found at '{audio_path}'", file=sys.stderr)
        sys.exit(1)

    try:
        # Call the simplified transcription function
        transcription = transcribe_audio(audio_path)
        # Print the result to standard output
        print(transcription)
    except Exception as e:
        print(f"An error occurred during transcription: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()