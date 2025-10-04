# Whisper Notes Local

This project is a Gradio application that provides audio transcription with speaker diarization. It uses `faster-whisper` for transcription and `resemblyzer` with DBSCAN clustering to identify and separate different speakers in an audio recording.

## Features

- **Audio Transcription:** Converts spoken audio into text.
- **Speaker Diarization:** Identifies different speakers and labels their contributions to the conversation.
- **Gradio Interface:** An easy-to-use web interface for recording and viewing transcriptions.

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MaikFakir/wIsper_notes_local.git
   cd wIsper_notes_local
   ```

2. **Install dependencies:**
   It is recommended to use a virtual environment.
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```
   You may also need to install `ffmpeg` on your system if you don't have it already.

## Usage

Run the application with the following command:

```bash
python app.py
```

This will launch a Gradio web server. Open the URL provided in your terminal (usually `http://127.0.0.1:7860`) in your web browser to use the application.

Record your audio using the microphone, and the transcription with speaker labels will appear in the textbox.