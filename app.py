import gradio as gr
import os
from src.audio_processing import transcribir_con_diarizacion, HF_TOKEN
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    create_folder_in_library,
    save_to_library,
    rename_library_item,
    delete_from_library,
    move_library_item,
    get_all_directories,
    get_folder_items,
    handle_folder_change,
    handle_file_selection,
)

# --- LISTAS Y VARIABLES GLOBALES ---
SUPPORTED_LANGUAGES = {
    "Español": "es", "Inglés": "en", "Portugués": "pt", "Francés": "fr",
    "Alemán": "de", "Italiano": "it", "Japonés": "ja", "Chino": "zh",
}

# --- INTERFAZ DE GRADIO ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    # --- ESTADOS ---
    processed_audio_path_state = gr.State(value=None)
    current_path_state = gr.State(value=".")

    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## 📂 Navegación")
            with gr.Row():
                new_folder_name_sidebar = gr.Textbox(label="Nueva Carpeta", placeholder="Nombre...", scale=3, lines=1)
                create_folder_button_sidebar = gr.Button("➕", scale=1)

            folder_selector_sidebar = gr.Dropdown(
                label="Seleccionar Carpeta",
                choices=get_all_directories(),
                value=".",
                interactive=True
            )
            refresh_button = gr.Button("🔄 Refrescar Vistas")

        with gr.Column():
            with gr.Tabs() as tabs:
                with gr.TabItem("🎙️ Principal", id=0):
                    gr.Markdown("## Transcripción y Diarización con WhisperX")
                    with gr.Row():
                        model_selector = gr.Dropdown(
                            ["tiny", "base", "small", "medium", "large-v2", "large-v3"],
                            label="🤖 Modelo", value="base"
                        )
                        language_selector = gr.Dropdown(
                            list(SUPPORTED_LANGUAGES.keys()),
                            label="🗣️ Idioma", value="Español"
                        )
                    audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio")
                    with gr.Row():
                        transcribe_button = gr.Button("🚀 Transcribir", variant="primary")
                        transcribe_again_button = gr.Button("🔄 Transcribir de Nuevo")
                    text_box = gr.Textbox(label="📝 Transcripción", lines=15, interactive=False, show_copy_button=True)
                    with gr.Row():
                        save_folder_dropdown = gr.Dropdown(label="Guardar en...", choices=get_all_directories(), interactive=True, scale=3)
                        save_button = gr.Button("💾 Guardar", scale=1)

                with gr.TabItem("🗂️ Archivos", id=1):
                    gr.Markdown("## Gestión de Archivos de Audio")
                    library_browser = gr.Radio(
                        label="Contenido de la Carpeta Actual",
                        choices=get_folder_items(),
                        interactive=True
                    )
                    with gr.Row():
                        new_name_input = gr.Textbox(label="Nuevo nombre", placeholder="Escribe y presiona 'Renombrar'", scale=3)
                        rename_button = gr.Button("✏️ Renombrar", scale=1)
                    delete_button = gr.Button("🗑️ Eliminar Seleccionado")
                    with gr.Row():
                        destination_folder_dropdown = gr.Dropdown(label="Mover a...", choices=get_all_directories(), interactive=True, scale=3)
                        move_button = gr.Button("🚚 Mover", scale=1)

                with gr.TabItem("👁️ Visualizador", id=2):
                    gr.Markdown("## Visualizador de Audio Guardado")
                    selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath", interactive=False)
                    selected_transcription_display = gr.Textbox(label="Transcripción Guardada", lines=15, interactive=False, show_copy_button=True)

    # --- LÓGICA DE LA INTERFAZ ---
    def on_transcribe(audio, model, lang_key):
        lang_code = SUPPORTED_LANGUAGES.get(lang_key, "es")
        # La función de backend ahora solo devuelve la transcripción y la ruta del audio
        transcription, audio_path = transcribir_con_diarizacion(audio, model, lang_code)
        return transcription, audio_path

    transcribe_button.click(
        fn=on_transcribe,
        inputs=[audio_input, model_selector, language_selector],
        outputs=[text_box, processed_audio_path_state]
    )
    transcribe_again_button.click(
        fn=on_transcribe,
        inputs=[processed_audio_path_state, model_selector, language_selector],
        outputs=[text_box, processed_audio_path_state]
    )

    save_button.click(
        fn=save_to_library,
        inputs=[save_folder_dropdown, processed_audio_path_state, text_box],
        outputs=[library_browser]
    )

    folder_selector_sidebar.change(
        fn=handle_folder_change,
        inputs=[folder_selector_sidebar],
        outputs=[current_path_state, library_browser]
    )

    library_browser.change(
        fn=handle_file_selection,
        inputs=[library_browser, current_path_state],
        outputs=[current_path_state, library_browser, selected_audio_player, selected_transcription_display, tabs]
    )

    def on_create_folder(current_path, new_folder):
        folder_list_update, new_name_update = create_folder_in_library(current_path, new_folder)
        return folder_list_update, folder_list_update, folder_list_update, new_name_update

    create_folder_button_sidebar.click(
        fn=on_create_folder,
        inputs=[current_path_state, new_folder_name_sidebar],
        outputs=[folder_selector_sidebar, save_folder_dropdown, destination_folder_dropdown, new_folder_name_sidebar]
    )

    rename_button.click(
        fn=rename_library_item,
        inputs=[current_path_state, library_browser, new_name_input],
        outputs=[library_browser, new_name_input]
    )

    delete_button.click(
        fn=delete_from_library,
        inputs=[current_path_state, library_browser],
        outputs=[library_browser, selected_audio_player, selected_transcription_display]
    )

    move_button.click(
        fn=move_library_item,
        inputs=[current_path_state, library_browser, destination_folder_dropdown],
        outputs=[library_browser]
    )

    def refresh_all_views(current_path):
        all_dirs = get_all_directories()
        current_items = get_folder_items(current_path)
        return (
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs),
            gr.update(choices=all_dirs),
            gr.update(choices=current_items)
        )

    refresh_button.click(
        fn=refresh_all_views,
        inputs=[current_path_state],
        outputs=[folder_selector_sidebar, save_folder_dropdown, destination_folder_dropdown, library_browser]
    )

if __name__ == "__main__":
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    if not HF_TOKEN:
        print("\n" + "="*80)
        print("AVISO: El token de Hugging Face no se ha encontrado.")
        print("La diarización de hablantes no funcionará.")
        print("Para solucionarlo, puedes:")
        print("  a) Crear un archivo llamado '.Hugging_Token' en la raíz del proyecto y pegar tu token dentro.")
        print("  b) O bien, configurar la variable de entorno HF_TOKEN.")
        print("\nRecuerda aceptar los términos de los modelos en Hugging Face para que la diarización funcione:")
        print("- pyannote/speaker-diarization-3.1")
        print("- pyannote/segmentation-3.0")
        print("="*80 + "\n")
    demo.launch(share=True, debug=True)