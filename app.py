import os
from flask import Flask, render_template, jsonify, request
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    list_directory_contents,
    get_library_tree,
    create_folder,
    save_uploaded_file,
    delete_recording,
    rename_item,
    move_item,
    get_file_details,
)
from pyngrok import ngrok

app = Flask(__name__, template_folder='templates', static_folder='static')

@app.route('/')
def index():
    """Renders the main application page."""
    return render_template('index.html')

@app.route('/api/recordings', methods=['GET'])
def get_recordings():
    """
    Returns a list of recordings from a specific folder.
    Defaults to the root of the library if no path is provided.
    """
    folder_path = request.args.get('path', '.')
    recordings = list_directory_contents(folder_path)
    return jsonify(recordings)

@app.route('/api/folders/tree', methods=['GET'])
def get_folder_tree():
    """Returns the nested folder structure of the audio library."""
    tree = get_library_tree()
    return jsonify(tree)

@app.route('/api/folders', methods=['POST'])
def create_new_folder():
    """Creates a new folder in the audio library."""
    data = request.get_json()
    if not data or 'path' not in data:
        return jsonify({"error": "No path provided"}), 400

    response, status_code = create_folder(data['path'])
    return jsonify(response), status_code

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

@app.route('/api/recordings/<path:file_path>', methods=['DELETE'])
def delete_recording_endpoint(file_path):
    """Deletes a specific recording."""
    response, status_code = delete_recording(file_path)
    return jsonify(response), status_code

@app.route('/api/item/rename', methods=['POST'])
def rename_item_endpoint():
    """Renames a file or folder."""
    data = request.get_json()
    if not data or 'path' not in data or 'new_name' not in data:
        return jsonify({"error": "Missing path or new_name"}), 400

    response, status_code = rename_item(data['path'], data['new_name'])
    return jsonify(response), status_code

@app.route('/api/item/move', methods=['POST'])
def move_item_endpoint():
    """Moves a file or folder."""
    data = request.get_json()
    if not data or 'source' not in data or 'destination' not in data:
        return jsonify({"error": "Missing source or destination"}), 400

    response, status_code = move_item(data['source'], data['destination'])
    return jsonify(response), status_code

@app.route('/api/file/<path:relative_path>', methods=['GET'])
def get_file_details_endpoint(relative_path):
    """Gets all details for a single file."""
    response, status_code = get_file_details(relative_path)
    return jsonify(response), status_code

# Check if running in Google Colab and try to import userdata
try:
    from google.colab import userdata
    IS_COLAB = True
except ImportError:
    IS_COLAB = False

if __name__ == '__main__':
    # --- ngrok Tunnel Setup ---
    ngrok_authtoken = None

    # 1. (Colab-specific) Try to get the token from Colab's userdata
    if IS_COLAB:
        print("INFO: Running in Google Colab. Checking for NGROK_AUTHTOKEN in Colab secrets.")
        try:
            ngrok_authtoken = userdata.get('NGROK_AUTHTOKEN')
            if ngrok_authtoken:
                print("INFO: Found ngrok token in Colab secrets.")
        except Exception as e:
            print(f"INFO: Could not retrieve token from Colab secrets: {e}")


    # 2. If not found in Colab, try environment variable
    if not ngrok_authtoken:
        print("INFO: Checking for NGROK_AUTHTOKEN environment variable.")
        ngrok_authtoken = os.environ.get("NGROK_AUTHTOKEN")
        if ngrok_authtoken:
            print("INFO: Found ngrok token in environment variables.")


    # 3. If not found in env, try to read from a file
    if not ngrok_authtoken:
        print("INFO: Checking for .ngrok_authtoken file.")
        try:
            with open(".ngrok_authtoken", "r") as f:
                ngrok_authtoken = f.read().strip()
            if ngrok_authtoken:
                print("INFO: Found ngrok token in .ngrok_authtoken file.")
        except FileNotFoundError:
            pass # This is an expected case
        except Exception as e:
            print(f"ERROR: Could not read .ngrok_authtoken file: {e}")

    # Set the token if it was found by any method
    if ngrok_authtoken:
        print("INFO: Setting ngrok authtoken.")
        ngrok.set_auth_token(ngrok_authtoken)
    else:
        print("WARNING: ngrok authtoken not found. The tunnel will be temporary. Sign up at https://ngrok.com/signup to get a free token.")


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
