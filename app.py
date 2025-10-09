import gradio as gr
import os
from src.audio_processing import transcribir_con_diarizacion
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    create_folder_in_library,
    save_to_library,
    rename_library_item,
    delete_from_library,
    move_library_item,
    update_all_views,
    handle_folder_selection,
    handle_library_selection,
    navigate_up,
)

# --- INTERFAZ DE GRADIO ---

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    # --- Estados ---
    processed_audio_path_state = gr.State(value=None)
    current_path_state = gr.State(value=".")

    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## 📂 Carpetas")
            with gr.Row():
                new_folder_name_sidebar = gr.Textbox(label="Nueva Carpeta", placeholder="Nombre...", scale=3, lines=1)
                create_folder_button_sidebar = gr.Button("➕", scale=1)

            up_button = gr.Button("⬆️ Subir a la carpeta padre")
            folder_browser = gr.Radio(label="Navegar por carpetas", choices=[], interactive=True)
            refresh_button = gr.Button("🔄 Refrescar Vistas")

        with gr.Column():
            status_box = gr.Textbox(label="ℹ️ Estado", lines=1, interactive=False)

            with gr.Tabs() as tabs:
                with gr.TabItem("🎙️ Principal", id=0):
                    gr.Markdown("## Transcripción y Diarización")
                    gr.Markdown("Graba o sube una conversación para transcribir y agrupar por hablante.")

                    model_selector = gr.Dropdown(
                        ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3", "distil-large-v2"],
                        label="🤖 Modelo de Whisper",
                        value="base",
                        info="Modelos más grandes son más precisos pero más lentos."
                    )

                    audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio aquí")

                    with gr.Row():
                        transcribe_again_button = gr.Button("🔄 Transcribir de Nuevo")

                    text_box = gr.Textbox(label="📝 Transcripción", lines=10, interactive=False)

                    with gr.Row():
                        save_folder_dropdown = gr.Dropdown(label="Guardar en...", choices=[], interactive=True, scale=3)
                        save_button = gr.Button("💾 Guardar", scale=1)

                with gr.TabItem("🗂️ Archivos", id=1):
                    gr.Markdown("## Gestión de Archivos")
                    current_path_display = gr.Textbox(label="Ruta Actual", value=".", interactive=False)
                    library_browser = gr.Radio(label="Contenido de la Carpeta Actual", choices=[], interactive=True)

                    with gr.Row():
                        new_name_input = gr.Textbox(label="Nuevo nombre", placeholder="Escribe y presiona 'Renombrar'", scale=3)
                        rename_button = gr.Button("✏️ Renombrar", scale=1)

                    delete_button = gr.Button("🗑️ Eliminar Seleccionado")

                    with gr.Row():
                        destination_folder_dropdown = gr.Dropdown(label="Mover a...", choices=[], interactive=True, scale=3)
                        move_button = gr.Button("🚚 Mover", scale=1)

                with gr.TabItem("👁️ Visualizador", id=2):
                    gr.Markdown("## Visualizador de Audio Guardado")
                    selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath", interactive=False)
                    selected_transcription_display = gr.Textbox(label="Transcripción Guardada", lines=15, interactive=False)

    # --- Lógica de la Interfaz ---

    # Salidas comunes para refrescar la UI
    ui_refresh_outputs = [
        status_box,
        folder_browser,
        library_browser,
        current_path_display,
        destination_folder_dropdown,
        save_folder_dropdown
    ]

    # Carga inicial
    demo.load(
        fn=update_all_views,
        inputs=current_path_state,
        outputs=ui_refresh_outputs
    )

    # --- Eventos de la Barra Lateral ---
    create_folder_button_sidebar.click(
        fn=create_folder_in_library,
        inputs=[current_path_state, new_folder_name_sidebar],
        outputs=ui_refresh_outputs + [new_folder_name_sidebar]
    )

    folder_browser.change(
        fn=handle_folder_selection,
        inputs=[folder_browser, current_path_state],
        outputs=[current_path_state, library_browser, current_path_display]
    )

    up_button.click(
        fn=navigate_up,
        inputs=[current_path_state],
        outputs=[current_path_state] + ui_refresh_outputs
    )

    refresh_button.click(
        fn=update_all_views,
        inputs=[current_path_state],
        outputs=ui_refresh_outputs
    )

    # --- Eventos de la Pestaña Principal ---
    audio_input.change(
        fn=transcribir_con_diarizacion,
        inputs=[audio_input, model_selector],
        outputs=[text_box, processed_audio_path_state, status_box]
    )

    transcribe_again_button.click(
        fn=transcribir_con_diarizacion,
        inputs=[processed_audio_path_state, model_selector],
        outputs=[text_box, processed_audio_path_state, status_box]
    )

    save_button.click(
        fn=save_to_library,
        inputs=[save_folder_dropdown, processed_audio_path_state, text_box],
        outputs=[status_box, library_browser]
    )

    # --- Eventos de la Pestaña Archivos ---
    library_browser.change(
        fn=handle_library_selection,
        inputs=[library_browser, current_path_state],
        outputs=[current_path_state, selected_audio_player, selected_transcription_display, tabs]
    )

    rename_button.click(
        fn=rename_library_item,
        inputs=[current_path_state, library_browser, new_name_input],
        outputs=ui_refresh_outputs + [new_name_input]
    )

    delete_button.click(
        fn=delete_from_library,
        inputs=[current_path_state, library_browser],
        outputs=ui_refresh_outputs + [selected_audio_player, selected_transcription_display]
    )

    move_button.click(
        fn=move_library_item,
        inputs=[current_path_state, library_browser, destination_folder_dropdown],
        outputs=ui_refresh_outputs
    )


if __name__ == "__main__":
    # Crear el directorio de la biblioteca si no existe
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    demo.launch(share=True, debug=True)