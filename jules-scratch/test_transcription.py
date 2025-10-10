import sys
import os

# Add the 'src' directory to the Python path to allow for relative imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.audio_processing import transcribir_con_diarizacion

def run_test():
    """
    Runs a direct test of the transcription function with a local audio file.
    """
    # Path to the audio file at the root of the repository
    audio_file = "El VIDEO más CORTO del CANAL - Lucas Castel D_20251008_200114.mp3"
    model_name = "base"
    language_code = "es" # Using the correct two-letter code directly for this test

    print(f"--- Iniciando prueba de transcripción ---")
    print(f"Archivo: {audio_file}")
    print(f"Modelo: {model_name}")
    print(f"Idioma: {language_code}")
    print("-" * 20)

    if not os.path.exists(audio_file):
        print(f"Error: El archivo de audio no se encuentra en la ruta: {audio_file}")
        return

    try:
        transcription, _ = transcribir_con_diarizacion(audio_file, model_name, language_code)
        print("\n--- Resultado de la Transcripción ---")
        print(transcription)
        print("\n--- Prueba Finalizada Exitosamente ---")
    except Exception as e:
        print(f"\n--- Ocurrió un error durante la prueba ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test()