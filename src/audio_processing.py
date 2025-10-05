# --- 1. INSTALACIONES E IMPORTACIONES ---
import ffmpeg
import tempfile
import os
from faster_whisper import WhisperModel
import gradio as gr
from resemblyzer import VoiceEncoder
import numpy as np
import librosa
from sklearn.cluster import DBSCAN
import torch

# --- 2. UTILIDADES DE AUDIO ---

def convert_audio_to_wav(audio_path):
    """
    Convierte un archivo de audio a formato WAV a 16kHz, mono.
    Devuelve la ruta del archivo temporal convertido.
    """
    try:
        # Crea un archivo temporal con la extensión .wav
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_filename = temp_file.name

        # Usa ffmpeg para la conversión
        (
            ffmpeg
            .input(audio_path)
            .output(temp_filename, acodec='pcm_s16le', ac=1, ar='16k')
            .run(overwrite_output=True, quiet=True)
        )
        return temp_filename
    except ffmpeg.Error as e:
        print(f"Error de ffmpeg: {e.stderr.decode()}")
        raise
    except Exception as e:
        print(f"Error inesperado en la conversión de audio: {e}")
        raise

# --- 3. CARGA DE MODELOS ---

# Determina el dispositivo a usar
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

# Cargar modelo Whisper. 'base' es un buen equilibrio entre velocidad y precisión para timestamps.
print("Cargando modelo de transcripción...")
transcription_model = WhisperModel("base", device=DEVICE, compute_type=COMPUTE_TYPE)
print("Modelo de transcripción cargado.")

# Cargar encoder de voces. Es recomendable usar CPU para evitar conflictos de VRAM.
print("Cargando modelo de codificación de voz...")
voice_encoder = VoiceEncoder(device="cpu")
print("Modelo de codificación de voz cargado.")

# --- 4. FUNCIÓN PRINCIPAL DE PROCESAMIENTO ---

def transcribir_con_diarizacion(audio_path):
    """
    Transcribe un archivo de audio, realiza diarización de hablantes y optimiza
    el uso de memoria para archivos grandes.
    """
    if audio_path is None:
        return "No se recibió audio. Por favor, graba algo.", None

    temp_wav_path = None
    try:
        # 1️⃣ Convertir a WAV estándar para compatibilidad y eficiencia
        print("Convirtiendo audio a formato WAV...")
        temp_wav_path = convert_audio_to_wav(audio_path)
        print(f"Audio convertido y guardado en: {temp_wav_path}")

        # 2️⃣ Transcripción directa desde el archivo
        print("Iniciando transcripción...")
        segments_generator, info = transcription_model.transcribe(
            temp_wav_path, language="es", word_timestamps=True
        )
        segments = list(segments_generator)
        print("Transcripción completada.")

        if not segments:
            return "No se pudo transcribir el audio (posiblemente silencio).", audio_path

        # 3️⃣ Diarización optimizada (cargando solo los segmentos necesarios)
        print("Iniciando diarización...")
        embeddings = []
        valid_segments_for_diarization = []
        for segment in segments:
            # Cargar solo el audio necesario para el embedding
            try:
                segment_audio, sr = librosa.load(
                    temp_wav_path,
                    sr=16000,
                    offset=segment.start,
                    duration=(segment.end - segment.start)
                )
                if len(segment_audio) < 400:  # Mínimo para el encoder
                    continue

                embedding = voice_encoder.embed_utterance(segment_audio)
                embeddings.append(embedding)
                valid_segments_for_diarization.append(segment)
            except Exception as e:
                print(f"Error procesando segmento de {segment.start} a {segment.end}: {e}")

        if not valid_segments_for_diarization:
             # Si la diarización falla, devolver solo la transcripción
            return " ".join([s.text for s in segments]).strip(), audio_path


        # 4️⃣ Clustering de hablantes
        print("Clustering de hablantes...")
        embeddings_array = np.array(embeddings)
        clustering = DBSCAN(eps=0.5, min_samples=1, metric="cosine").fit(embeddings_array)
        labels = clustering.labels_

        # Asignar hablante a cada segmento original usando una clave inmutable
        diarization_results = {}
        for i, segment in enumerate(valid_segments_for_diarization):
            key = (segment.start, segment.end)
            diarization_results[key] = labels[i]

        # 5️⃣ Construir la transcripción final formateada
        print("Construyendo transcripción final...")
        final_transcription = []
        for segment in segments:
            key = (segment.start, segment.end)
            speaker_label = diarization_results.get(key, -1) # Usar -1 si no fue diarizado
            speaker_name = f"Hablante {speaker_label + 1}" if speaker_label != -1 else "Desconocido"
            final_transcription.append({
                "speaker": speaker_name,
                "text": segment.text.strip(),
                "start": segment.start
            })

        # Agrupar texto por hablante
        grouped_transcription = ""
        if final_transcription:
            current_speaker = final_transcription[0]['speaker']
            current_text = ""
            for item in final_transcription:
                if item['speaker'] != current_speaker:
                    grouped_transcription += f"**{current_speaker}:** {current_text.strip()}\\n\\n"
                    current_speaker = item['speaker']
                    current_text = item['text']
                else:
                    current_text += " " + item['text']
            # Añadir el último bloque
            grouped_transcription += f"**{current_speaker}:** {current_text.strip()}\\n\\n"

        print("Proceso completado.")
        return grouped_transcription.strip(), audio_path

    except ffmpeg.Error as e:
        return f"Error de FFMPEG: {e.stderr.decode()}", None
    except Exception as e:
        import traceback
        return f"Ocurrió un error inesperado: {e}\\n{traceback.format_exc()}", None
    finally:
        # 6️⃣ Limpieza del archivo temporal
        if temp_wav_path and os.path.exists(temp_wav_path):
            os.remove(temp_wav_path)
            print(f"Archivo temporal eliminado: {temp_wav_path}")