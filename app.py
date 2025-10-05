import gradio as gr
import os
from src.audio_processing import transcribir_con_diarizacion
from src.file_management import (
    AUDIO_LIBRARY_PATH,
    update_library_browser,
    create_folder_in_library,
    save_to_library,
    rename_library_item,
    delete_from_library,
    handle_library_selection,
    navigate_up
)

# --- INTERFAZ DE GRADIO ---

with gr.Blocks(theme=gr.themes.Soft(), css="style.css") as demo:
    # Estado para almacenar la ruta del último audio procesado
    processed_audio_path_state = gr.State(value=None)

    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## 📚 Biblioteca de Audios")

            # Estado para la ruta actual en la biblioteca
            current_path_state = gr.State(value=".")

            # UI de navegación y visualización de ruta
            with gr.Row():
                up_button = gr.Button("⬆️ Subir")
                refresh_button = gr.Button("🔄 Refrescar")
            current_path_display = gr.Textbox(label="Ubicación Actual", value="Biblioteca Principal", interactive=False)

            # Lista de archivos y carpetas
            library_browser = gr.Radio(label="Contenido", choices=[], interactive=True)

            # Reproductor de audio
            selected_audio_player = gr.Audio(label="Audio Seleccionado", type="filepath")

            # Acordeón para acciones de la biblioteca
            with gr.Accordion("📂 Acciones de Biblioteca", open=False):
                with gr.Blocks(elem_id="action-buttons"):
                    # Crear carpetas
                    with gr.Row():
                        new_folder_name = gr.Textbox(label="Nombre de la Carpeta", placeholder="Escribe y presiona Enter...", scale=3)
                        create_folder_button = gr.Button("➕ Crear", scale=1)

                    # Renombrar items
                    with gr.Row():
                        new_name_input = gr.Textbox(label="Nuevo Nombre", placeholder="Nuevo nombre para el item...", scale=3)
                        rename_button = gr.Button("✏️ Renombrar", scale=1)

                    # Eliminar
                    delete_button = gr.Button("🗑️ Eliminar Seleccionado")

        with gr.Column():
            gr.Markdown("## 🎙️ Transcriptor con Diarización (Resemblyzer + DBSCAN)")
            gr.Markdown("Graba una conversación. El sistema transcribirá y agrupará los segmentos por hablante.")

            audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="🎤 Graba o sube tu audio aquí")
            text_box = gr.Textbox(label="📝 Transcripción", lines=15, interactive=False)

            with gr.Row():
                save_button = gr.Button("💾 Guardar en la Biblioteca")

            status_box = gr.Textbox(label="ℹ️ Estado", lines=1, interactive=False)

    # --- Lógica de la Interfaz ---

    # Cargar el contenido inicial de la biblioteca
    demo.load(update_library_browser, outputs=[library_browser, current_path_display])

    # Conexiones de eventos de la transcripción principal
    audio_input.change(transcribir_con_diarizacion, inputs=audio_input, outputs=[text_box, processed_audio_path_state])
    save_button.click(
        save_to_library,
        inputs=[current_path_state, processed_audio_path_state, text_box],
        outputs=[status_box]
    ).then(
        update_library_browser,
        inputs=[current_path_state],
        outputs=[library_browser, current_path_display]
    )

    # Conexiones de la biblioteca
    create_folder_button.click(
        create_folder_in_library,
        inputs=[current_path_state, new_folder_name],
        outputs=[status_box, library_browser, current_path_display, new_folder_name]
    )

    up_button.click(
        navigate_up,
        inputs=[current_path_state],
        outputs=[current_path_state]
    ).then(
        update_library_browser,
        inputs=[current_path_state],
        outputs=[library_browser, current_path_display]
    )

    refresh_button.click(update_library_browser, inputs=[current_path_state], outputs=[library_browser, current_path_display])

    library_browser.change(
        handle_library_selection,
        inputs=[library_browser, current_path_state],
        outputs=[current_path_state, selected_audio_player, text_box, library_browser, current_path_display]
    )

    rename_button.click(
        rename_library_item,
        inputs=[current_path_state, library_browser, new_name_input],
        outputs=[status_box, library_browser, current_path_display, new_name_input]
    )

    delete_button.click(
        delete_from_library,
        inputs=[current_path_state, library_browser],
        outputs=[status_box, library_browser, current_path_display, selected_audio_player, text_box]
    )


if __name__ == "__main__":
    # Crear el directorio de la biblioteca si no existe
    if not os.path.exists(AUDIO_LIBRARY_PATH):
        os.makedirs(AUDIO_LIBRARY_PATH)
    demo.launch(share=True, debug=True)