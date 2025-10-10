import gradio as gr
import os
from src.audio_processing import transcribir_con_diarizacion, HF_TOKEN
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    get_all_directories,
    get_folder_contents,
    get_audio_files_in_folder,
    load_viewer_data,
    create_folder_in_library,
    save_transcription_to_library,
    rename_library_item,
    delete_library_item,
    move_library_item,
)

# --- LISTAS Y VARIABLES GLOBALES ---
SUPPORTED_LANGUAGES = {
    "Español": "es", "Inglés": "en", "Portugués": "pt", "Francés": "fr",
    "Alemán": "de", "Italiano": "it", "Japonés": "ja", "Chino": "zh",
}

# --- LÓGICA DE FORMATO DE LA UI ---
def format_folder_contents_for_display(contents):
    """Añade prefijos a las carpetas para visualización en la UI."""
    folders = [f"[C] {name}" for name in contents["folders"]]
    files = contents["files"]
    return sorted(folders) + sorted(files)

# --- INTERFAZ DE GRADIO ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    # --- ESTADOS ---
    processed_audio_path_state = gr.State(value=None)

    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## 📂 Acciones Globales")
            with gr.Accordion("Crear Nueva Carpeta", open=False):
                new_folder_parent_selector = gr.Dropdown(label="Directorio Padre", choices=get_all_directories(), value=".", interactive=True)
                new_folder_name_sidebar = gr.Textbox(label="Nombre de la Nueva Carpeta", placeholder="Nombre...", lines=1)
                create_folder_button_sidebar = gr.Button("➕ Crear Carpeta")

            refresh_button = gr.Button("🔄 Refrescar Todas las Vistas")

        with gr.Column():
            with gr.Tabs() as tabs:
                with gr.TabItem("🎙️ Principal", id=0):
                    gr.Markdown("## Transcripción y Diarización con WhisperX")
                    with gr.Row():
                        model_selector = gr.Dropdown(["tiny", "base", "small", "medium", "large-v2", "large-v3"], label="🤖 Modelo", value="base")
                        language_selector = gr.Dropdown(list(SUPPORTED_LANGUAGES.keys()), label="🗣️ Idioma", value="Español")
                    audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio")
                    transcribe_button = gr.Button("🚀 Transcribir", variant="primary")
                    text_box = gr.Textbox(label="📝 Transcripción", lines=15, interactive=False, show_copy_button=True)
                    with gr.Row():
                        save_folder_dropdown = gr.Dropdown(label="Guardar en...", choices=get_all_directories(), interactive=True, scale=3)
                        save_button = gr.Button("💾 Guardar Transcripción", scale=1)

                with gr.TabItem("🗂️ Gestor de Archivos", id=1):
                    gr.Markdown("## Gestión de Archivos de Audio")
                    files_folder_selector = gr.Dropdown(label="Seleccionar Carpeta", choices=get_all_directories(), value=".", interactive=True)

                    # Usamos un estado para la selección para evitar problemas con la UI
                    selected_file_state = gr.State(None)

                    file_manager_list = gr.Radio(label="Contenido de la Carpeta", choices=format_folder_contents_for_display(get_folder_contents(".")), interactive=True)

                    with gr.Accordion("Acciones de Archivo", open=False):
                        with gr.Row():
                            new_name_input = gr.Textbox(label="Nuevo nombre", placeholder="Escribe y presiona 'Renombrar'", scale=3)
                            rename_button = gr.Button("✏️ Renombrar", scale=1)
                        with gr.Row():
                            destination_folder_dropdown = gr.Dropdown(label="Mover a...", choices=get_all_directories(), interactive=True, scale=3)
                            move_button = gr.Button("🚚 Mover", scale=1)
                        delete_button = gr.Button("🗑️ Eliminar Seleccionado", variant="stop")

                with gr.TabItem("👁️ Visualizador", id=2):
                    gr.Markdown("## Visualizador de Audio Guardado")
                    with gr.Row():
                        viewer_folder_selector = gr.Dropdown(label="Seleccionar Carpeta", choices=get_all_directories(), value=".", interactive=True)
                        viewer_file_selector = gr.Radio(label="Seleccionar Archivo de Audio", choices=get_audio_files_in_folder("."), interactive=True)
                    selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath", interactive=False)
                    selected_transcription_display = gr.Textbox(label="Transcripción Guardada", lines=15, interactive=False, show_copy_button=True)

    # --- LÓGICA DE LA INTERFAZ ---

    # --- Pestaña Principal ---
    transcribe_button.click(
        fn=transcribir_con_diarizacion,
        inputs=[audio_input, model_selector, language_selector],
        outputs=[text_box, processed_audio_path_state]
    )
    save_button.click(
        fn=save_transcription_to_library,
        inputs=[save_folder_dropdown, processed_audio_path_state, text_box]
    )

    # --- Pestaña Gestor de Archivos ---
    def update_file_manager_view(folder_path):
        """Actualiza la lista de archivos en el gestor cuando se cambia de carpeta."""
        contents = get_folder_contents(folder_path)
        formatted_contents = format_folder_contents_for_display(contents)
        return gr.update(choices=formatted_contents, value=None)

    files_folder_selector.change(
        fn=update_file_manager_view,
        inputs=[files_folder_selector],
        outputs=[file_manager_list]
    )

    # Guarda la selección en el estado para que los botones puedan usarla
    file_manager_list.change(fn=lambda x: x, inputs=file_manager_list, outputs=selected_file_state)

    rename_button.click(
        fn=rename_library_item,
        inputs=[files_folder_selector, selected_file_state, new_name_input],
    ).then(
        fn=update_file_manager_view,
        inputs=[files_folder_selector],
        outputs=[file_manager_list]
    )

    delete_button.click(
        fn=delete_library_item,
        inputs=[files_folder_selector, selected_file_state]
    ).then(
        fn=update_file_manager_view,
        inputs=[files_folder_selector],
        outputs=[file_manager_list]
    )

    move_button.click(
        fn=move_library_item,
        inputs=[files_folder_selector, selected_file_state, destination_folder_dropdown]
    ).then(
        fn=update_file_manager_view,
        inputs=[files_folder_selector],
        outputs=[file_manager_list]
    )

    # --- Pestaña Visualizador ---
    def update_viewer_files(folder_path):
        """Actualiza la lista de archivos en el visualizador."""
        files = get_audio_files_in_folder(folder_path)
        return gr.update(choices=files, value=None), gr.update(value=None), gr.update(value="")

    viewer_folder_selector.change(
        fn=update_viewer_files,
        inputs=[viewer_folder_selector],
        outputs=[viewer_file_selector, selected_audio_player, selected_transcription_display]
    )
    viewer_file_selector.change(
        fn=load_viewer_data,
        inputs=[viewer_folder_selector, viewer_file_selector],
        outputs=[selected_audio_player, selected_transcription_display]
    )

    # --- Acciones Globales ---
    def handle_create_folder(parent, name):
        """Llama a la función de backend y limpia el campo de texto."""
        create_folder_in_library(parent, name)
        return ""

    create_folder_button_sidebar.click(
        fn=handle_create_folder,
        inputs=[new_folder_parent_selector, new_folder_name_sidebar],
        outputs=[new_folder_name_sidebar]
    )

    def refresh_all_dropdowns():
        """Recarga la lista de directorios en todos los menús desplegables."""
        all_dirs = get_all_directories()
        return (
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs)
        )

    refresh_button.click(
        fn=refresh_all_dropdowns,
        outputs=[
            new_folder_parent_selector,
            save_folder_dropdown,
            files_folder_selector,
            destination_folder_dropdown,
            viewer_folder_selector
        ]
    )

if __name__ == "__main__":
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    if not HF_TOKEN:
        print("\n" + "="*80)
        print("AVISO: La variable de entorno HF_TOKEN no se ha configurado.")
        print("La diarización de hablantes no funcionará.")
        print("Para solucionarlo, configura la variable de entorno 'HF_TOKEN'.")
        print("="*80 + "\n")

    # El encadenamiento .then() requiere que la app se ejecute en una cola
    demo.queue()
    demo.launch(share=True, debug=True)