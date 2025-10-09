import os
from flask import Flask, render_template, jsonify, request
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    save_uploaded_file,
    get_file_details,
)
from pyngrok import ngrok

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    """Renders the main application page."""
    return render_template('index.html')

@app.route('/api/recordings', methods=['POST'])
def upload_recording():
    """Handles file uploads and marks them for processing."""
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    # Get destination folder and model from the form data
    destination_folder = request.form.get('destination_folder', '.')
    model = request.form.get('model', 'base') # Default to 'base' if not provided

    response, status_code = save_uploaded_file(file, destination_folder, model)
    return jsonify(response), status_code

@app.route('/api/file/<path:relative_path>', methods=['GET'])
def get_file_details_endpoint(relative_path):
    """Gets all details for a single file."""
    response, status_code = get_file_details(relative_path)
    return jsonify(response), status_code

if __name__ == '__main__':
    # --- ngrok Tunnel Setup ---
    # Try to get the authtoken from the environment variable first.
    ngrok_authtoken = os.environ.get("NGROK_AUTHTOKEN")

    # If not found in env, try to read from a file named .ngrok_authtoken
    if not ngrok_authtoken:
        try:
            with open(".ngrok_authtoken", "r") as f:
                ngrok_authtoken = f.read().strip()
        except FileNotFoundError:
            print("INFO: .ngrok_authtoken file not found. Continuing without a persistent token.")
        except Exception as e:
            print(f"ERROR: Could not read .ngrok_authtoken file: {e}")

    if ngrok_authtoken:
        print("INFO: Setting ngrok authtoken.")
        ngrok.set_auth_token(ngrok_authtoken)
    else:
        print("WARNING: ngrok authtoken not found. The tunnel will be temporary.")


    # Create the audio library directory if it doesn't exist
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)

    # Define the port
    port = 5000

    try:
        # Open a ngrok tunnel to the Flask app
        public_url = ngrok.connect(port)
        print("*****************************************************************")
        print(f"--> URL Pública: {public_url}")
        print("--> Copia esta URL y pégala en tu navegador.")
        print("*****************************************************************")
    except Exception as e:
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"ERROR: Failed to start ngrok tunnel. This might be due to a missing or invalid authtoken.")
        print(f"Please ensure your NGROK_AUTHTOKEN is set correctly as an environment variable or in a '.ngrok_authtoken' file.")
        print(f"Ngrok error: {e}")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        exit()


    # Run the Flask app without the reloader for stability with ngrok
    app.run(port=port, use_reloader=False)