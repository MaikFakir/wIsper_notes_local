import gradio as gr
import os
from src.audio_processing import transcribe_audio
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    METADATA_FILE,
    get_directory_contents,
    create_folder_in_library,
    save_to_library,
    get_file_data,
)
import json

# --- UI WRAPPER FUNCTIONS ---

def update_browser_and_title(current_path="."):
    """
    Controller function to get directory contents from the backend
    and return formatted updates for the UI components.
    """
    choices = get_directory_contents(current_path)

    # Determine the display name for the title
    if current_path == ".":
        display_path = "Reuniones de trabajo"
    else:
        display_path = os.path.basename(current_path)

    title_update = f"## {display_path}"
    browser_update = gr.update(choices=choices, value=None)

    return browser_update, title_update

def create_folder_and_refresh(current_path, new_folder_name):
    """
    UI controller to create a folder and then refresh the file browser.
    """
    # Call the backend function which returns a status message
    status = create_folder_in_library(current_path, new_folder_name)

    # After the backend action, get fresh updates for the UI
    browser_update, title_update = update_browser_and_title(current_path)

    # Return all the necessary updates for the Gradio interface
    return status, browser_update, title_update, "" # Clear the input textbox

def handle_selection_and_refresh(selection, current_path):
    """
    UI controller to handle file/folder selection. It navigates into
    folders or loads file data and returns the correct UI updates.
    """
    if selection is None:
        # This can happen on a refresh, just update the current view
        browser_update, title_update = update_browser_and_title(current_path)
        return current_path, gr.update(), gr.update(), browser_update, title_update

    if selection.startswith("[C]"):
        # A folder was selected, so navigate into it
        folder_name = selection.replace("[C] ", "")
        new_path = os.path.join(current_path, folder_name)
        browser_update, title_update = update_browser_and_title(new_path)
        # Return new path, clear audio player and textbox, update browser and title
        return new_path, None, "", browser_update, title_update
    else:
        # A file was selected
        # Call the backend to get the file's data
        audio_path, transcription = get_file_data(current_path, selection)
        # We don't need to change the path or the browser list, so we send gr.update()
        return current_path, audio_path, transcription, gr.update(), gr.update()

# --- INTERFAZ DE GRADIO ---

with gr.Blocks(theme=gr.themes.Soft(), css="style.css") as demo:
    # --- STATE MANAGEMENT ---
    processed_audio_path_state = gr.State(value=None)
    current_path_state = gr.State(value=".")

    with gr.Row(elem_classes="main-container"):
        # --- SIDEBAR ---
        with gr.Column(scale=1, elem_classes="sidebar"):
            gr.Markdown("### Mis Carpetas", elem_classes="sidebar-title")
            folder_search = gr.Textbox(placeholder="🔍 Buscar carpeta...", show_label=False)

            library_browser = gr.Dropdown(
                label="Contenido",
                choices=[],
                interactive=True,
                show_label=False,
                elem_classes="folder-list"
            )

            new_folder_button = gr.Button("➕ Nueva Carpeta", elem_id="new-folder-button")
            new_folder_name = gr.Textbox(
                placeholder="Nombre de la carpeta...",
                show_label=False,
                visible=False # Initially hidden
            )

        # --- MAIN CONTENT ---
        with gr.Column(scale=4, elem_classes="main-content"):
            main_title = gr.Markdown("## Reuniones de trabajo", elem_classes="main-title")

            with gr.Row():
                record_button = gr.Button("🎤 Grabar Audio")
                transcribe_button = gr.Button("✍️ Transcribir Audio")

            with gr.Tabs():
                with gr.TabItem("Cargar o Grabar Audio"):
                    audio_input = gr.Audio(
                        sources=["microphone", "upload"],
                        type="filepath",
                        label="Coloque el audio aquí o haga clic para cargar",
                        elem_classes="audio-input-box"
                    )

            transcription_output = gr.Textbox(
                label="Transcripción",
                lines=10,
                interactive=False,
                elem_classes="transcription-box"
            )

            status_box = gr.Textbox(label="ℹ️ Estado", lines=1, interactive=False, visible=False)

    # --- UI LOGIC AND EVENT HANDLERS ---

    def initial_load(current_path):
        return update_browser_and_title(current_path)

    demo.load(initial_load, inputs=current_path_state, outputs=[library_browser, main_title])

    def toggle_new_folder_input(current_state):
        return gr.update(visible=not current_state)

    new_folder_button.click(
        toggle_new_folder_input,
        inputs=new_folder_name.visible,
        outputs=new_folder_name
    )

    new_folder_name.submit(
        create_folder_and_refresh,
        inputs=[current_path_state, new_folder_name],
        outputs=[status_box, library_browser, main_title, new_folder_name]
    ).then(
        lambda: gr.update(visible=False),
        outputs=new_folder_name
    )

    library_browser.change(
        handle_selection_and_refresh,
        inputs=[library_browser, current_path_state],
        outputs=[current_path_state, audio_input, transcription_output, library_browser, main_title]
    )

    transcribe_button.click(
        transcribe_audio,
        inputs=audio_input,
        outputs=[transcription_output, processed_audio_path_state]
    )

if __name__ == "__main__":
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    if not os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, 'w') as f:
            json.dump({}, f)

    demo.launch(share=True, debug=True)