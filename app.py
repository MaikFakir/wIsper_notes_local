import os
from flask import Flask, render_template, jsonify, request
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    list_library_contents,
    save_uploaded_file,
    delete_recording,
)

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    """Renders the main application page."""
    return render_template('index.html')

@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """Returns a list of all audio recordings."""
    recordings = list_library_contents()
    return jsonify(recordings)

@app.route('/api/recordings', methods=['POST'])
def upload_recording():
    """Handles file uploads and marks them for processing."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # This function now just saves the file and sets status to "Processing"
    response, status_code = save_uploaded_file(file)

    return jsonify(response), status_code

@app.route('/api/recordings/<path:file_path>', methods=['DELETE'])
def delete_recording_endpoint(file_path):
    """Deletes a specific recording."""
    response, status_code = delete_recording(file_path)
    return jsonify(response), status_code

if __name__ == '__main__':
    # Create the audio library directory if it doesn't exist
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)

    # Run the Flask app
    app.run(debug=True, port=5000)