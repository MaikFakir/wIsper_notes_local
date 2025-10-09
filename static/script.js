document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const recordBtn = document.getElementById('record-btn');
    const uploadBtn = document.getElementById('upload-btn');
    const audioUploadInput = document.getElementById('audio-upload-input');
    const transcriptionOutput = document.getElementById('transcription-output');
    const audioPlayerContainer = document.getElementById('audio-player-container');

    // Modal elements
    const modelModal = document.getElementById('model-selection-modal');
    const modelConfirmBtn = document.getElementById('model-confirm-btn');
    const modelOptions = document.querySelectorAll('.model-option');
    const closeModalBtn = document.querySelector('.modal .close-btn');

    // --- State Variables ---
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let selectedModel = 'base';
    let audioFileToProcess = null;

    // --- Core Functions ---

    /**
     * Sends the audio file to the backend for transcription.
     * @param {File} audioFile The audio file to transcribe.
     * @param {string} model The selected transcription model.
     */
    async function transcribeAudio(audioFile, model) {
        transcriptionOutput.value = 'Transcribing... Please wait.';
        transcriptionOutput.placeholder = 'Transcribing... Please wait.';

        const formData = new FormData();
        formData.append('file', audioFile);
        formData.append('model', model);
        // The simplified version doesn't need a destination folder
        formData.append('destination_folder', '.');

        try {
            const response = await fetch('/api/recordings', {
                method: 'POST',
                body: formData,
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || 'Transcription failed.');
            }

            // We need the backend to return the transcription directly or poll for it.
            // For now, let's assume we need to poll the file details.
            if (result.filePath) {
                pollForTranscription(result.filePath);
            } else {
                 throw new Error('Did not receive a file path from the server.');
            }

        } catch (error) {
            console.error('Transcription error:', error);
            transcriptionOutput.value = `Error: ${error.message}`;
        }
    }

    /**
     * Polls the backend for the transcription result.
     * @param {string} filePath The path of the file being processed.
     */
    async function pollForTranscription(filePath) {
        const poller = setInterval(async () => {
            try {
                const response = await fetch(`/api/file/${encodeURIComponent(filePath)}`);
                const details = await response.json();

                if (!response.ok) {
                    throw new Error(details.error || 'Could not fetch file details.');
                }

                if (details.status === 'Completed') {
                    transcriptionOutput.value = details.transcription || 'Transcription finished, but no text was produced.';
                    clearInterval(poller);
                } else if (details.status === 'Failed') {
                    transcriptionOutput.value = 'Transcription failed. Please try again.';
                    clearInterval(poller);
                }
                // If still 'Processing', do nothing and wait for the next poll.
            } catch (error) {
                console.error('Polling error:', error);
                transcriptionOutput.value = `Error fetching transcription: ${error.message}`;
                clearInterval(poller);
            }
        }, 3000);
    }


    /**
     * Displays the audio player for a given audio blob.
     * @param {Blob} audioBlob The audio data to play.
     */
    function displayAudioPlayer(audioBlob) {
        const audioUrl = URL.createObjectURL(audioBlob);
        audioPlayerContainer.innerHTML = `<audio controls src="${audioUrl}"></audio>`;
        audioPlayerContainer.style.display = 'block';
    }


    // --- Recording Logic ---

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                const fileName = `recording_${new Date().toISOString()}.webm`;
                audioFileToProcess = new File([audioBlob], fileName, { type: 'audio/webm' });

                displayAudioPlayer(audioBlob);
                openModal(); // Ask for model after recording is done
            };

            mediaRecorder.start();
            isRecording = true;
            recordBtn.classList.add('recording');
            recordBtn.querySelector('span').textContent = 'Stop Recording';
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please grant permission.');
        }
    };

    const stopRecording = () => {
        mediaRecorder.stop();
        isRecording = false;
        recordBtn.classList.remove('recording');
        recordBtn.querySelector('span').textContent = 'Record';
    };


    // --- Modal Logic ---

    const openModal = () => {
        modelModal.classList.add('show');
    };

    const closeModal = () => {
        modelModal.classList.remove('show');
        audioFileToProcess = null; // Discard file if modal is closed
    };

    modelOptions.forEach(option => {
        option.addEventListener('click', () => {
            modelOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            selectedModel = option.dataset.model;
        });
    });

    modelConfirmBtn.addEventListener('click', () => {
        if (audioFileToProcess) {
            transcribeAudio(audioFileToProcess, selectedModel);
        }
        modelModal.classList.remove('show');
    });

    closeModalBtn.addEventListener('click', closeModal);


    // --- Event Listeners ---

    recordBtn.addEventListener('click', () => {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    uploadBtn.addEventListener('click', () => {
        audioUploadInput.click();
    });

    audioUploadInput.addEventListener('change', event => {
        const file = event.target.files[0];
        if (file) {
            audioFileToProcess = file;
            const blob = new Blob([file], { type: file.type });
            displayAudioPlayer(blob);
            openModal();
        }
        // Reset the input so the same file can be selected again
        event.target.value = '';
    });
});