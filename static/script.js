document.addEventListener('DOMContentLoaded', function() {
    const recordingsTbody = document.querySelector('.recordings-list tbody');
    const folderTreeContainer = document.getElementById('folder-tree');
    const currentFolderTitle = document.getElementById('current-folder-title');
    const uploadBtn = document.querySelector('.upload-btn');
    const fileInput = document.getElementById('audio-upload-input');

    let currentPath = '.'; // To keep track of the currently viewed folder
    let pollingInterval; // To hold the interval ID

    // --- Core Functions ---

    /**
     * Fetches and displays the contents (files and folders) of a given directory path.
     * @param {string} path - The relative path of the folder to display.
     */
    async function fetchAndDisplayContents(path = '.') {
        currentPath = path;
        const displayPath = path === '.' ? 'My Recordings' : path;
        currentFolderTitle.textContent = displayPath;

        try {
            const response = await fetch(`/api/recordings?path=${encodeURIComponent(path)}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const contents = await response.json();
            renderContents(contents);
        } catch (error) {
            console.error(`Failed to fetch contents for path "${path}":`, error);
            recordingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Error loading recordings.</td></tr>';
        }
    }

    /**
     * Renders the files and folders in the main content area.
     * @param {Array} contents - An array of file and folder objects.
     */
    function renderContents(contents) {
        recordingsTbody.innerHTML = ''; // Clear existing rows

        if (contents.length === 0) {
            recordingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">This folder is empty.</td></tr>';
            return;
        }

        // Render folders first
        contents.filter(item => item.type === 'folder').forEach(folder => {
            const row = document.createElement('tr');
            row.className = 'folder-row';
            row.dataset.path = folder.path;
            row.innerHTML = `
                <td colspan="5" class="folder-cell">
                    <span class="folder-icon">📁</span>
                    ${folder.name}
                </td>
            `;
            recordingsTbody.appendChild(row);
        });

        // Then render files
        contents.filter(item => item.type === 'file').forEach(rec => {
            const row = document.createElement('tr');
            const statusClass = rec.status.toLowerCase();
            row.innerHTML = `
                <td>${rec.fileName}</td>
                <td class="optional-column">${rec.duration}</td>
                <td class="optional-column">${rec.dateCreated}</td>
                <td><span class="status ${statusClass}">${rec.status}</span></td>
                <td class="actions">
                    <button class="actions-btn" data-path="${rec.path}">...</button>
                </td>
            `;
            recordingsTbody.appendChild(row);
        });
    }

    /**
     * Fetches the folder structure and renders it in the sidebar.
     */
    async function renderFolderTree() {
        try {
            const response = await fetch('/api/folders/tree');
            const tree = await response.json();

            const root = {
                type: 'folder',
                name: 'My Recordings',
                path: '.',
                children: tree
            };

            folderTreeContainer.innerHTML = ''; // Clear existing tree
            const treeHtml = createFolderHtml(root);
            folderTreeContainer.innerHTML = `<ul>${treeHtml}</ul><button class="new-folder-btn">+ New Folder</button>`;

        } catch (error) {
            console.error('Failed to fetch folder tree:', error);
            folderTreeContainer.innerHTML = '<p>Error loading folders.</p>';
        }
    }

    /**
     * Recursively creates the HTML for the folder tree.
     * @param {object} folder - The folder object to create HTML for.
     */
    function createFolderHtml(folder) {
        let childrenHtml = '';
        if (folder.children && folder.children.length > 0) {
            childrenHtml = `<ul>${folder.children.map(createFolderHtml).join('')}</ul>`;
        }
        return `
            <li>
                <div class="folder-item" data-path="${folder.path}">
                    <span class="folder-name">${folder.name}</span>
                </div>
                ${childrenHtml}
            </li>
        `;
    }

    /**
     * Starts or restarts the polling mechanism to refresh the current view.
     */
    function startPolling() {
        // Clear any existing interval
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
        // Start a new one
        pollingInterval = setInterval(() => fetchAndDisplayContents(currentPath), 3000);
    }

    // --- Event Listeners ---

    // For clicking on folders in the sidebar
    folderTreeContainer.addEventListener('click', (event) => {
        const folderItem = event.target.closest('.folder-item');
        if (folderItem) {
            const path = folderItem.dataset.path;
            fetchAndDisplayContents(path);
        }

        if (event.target.classList.contains('new-folder-btn')) {
            const folderName = prompt('Enter new folder name:');
            if (folderName) {
                const newFolderPath = currentPath === '.' ? folderName : `${currentPath}/${folderName}`;
                createNewFolder(newFolderPath);
            }
        }
    });

    // For clicking on folders in the main content area
    recordingsTbody.addEventListener('click', (event) => {
        const folderRow = event.target.closest('.folder-row');
        if (folderRow) {
            const path = folderRow.dataset.path;
            fetchAndDisplayContents(path);
        }
    });

    async function createNewFolder(path) {
        try {
            const response = await fetch('/api/folders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: path })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to create folder');
            }

            // Refresh both the folder tree and the current view
            await renderFolderTree();
            await fetchAndDisplayContents(currentPath);

        } catch (error) {
            console.error('Error creating folder:', error);
            alert(`Could not create folder: ${error.message}`);
        }
    }

    // --- Model Selection Modal ---
    const modelModal = document.getElementById('model-selection-modal');
    const modelConfirmBtn = document.getElementById('model-confirm-btn');
    const modelOptions = document.querySelectorAll('.model-selection .model-option');
    const newRecordingBtn = document.querySelector('.new-recording-btn');

    let selectedModel = 'base'; // Default model
    let modalAction = null; // 'record' or 'upload'
    let fileToUpload = null;

    function openModelModal(action, file = null) {
        modalAction = action;
        if (action === 'upload') {
            fileToUpload = file;
            document.getElementById('model-modal-title').textContent = `Transcribe "${file.name}"`;
            document.getElementById('model-modal-description').textContent = 'Select a model to process your uploaded file.';
            modelConfirmBtn.textContent = 'Transcribe';
        } else { // record
            fileToUpload = null;
            document.getElementById('model-modal-title').textContent = 'New Recording';
            document.getElementById('model-modal-description').textContent = 'Select a model for your new recording.';
            modelConfirmBtn.textContent = 'Start Recording';
        }
        modelModal.style.display = 'block';
    }

    modelOptions.forEach(option => {
        option.addEventListener('click', () => {
            modelOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            selectedModel = option.dataset.model;
        });
    });

    // --- Audio Recording Logic ---
    let mediaRecorder;
    let audioChunks = [];

    async function startRecording(model) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = event => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                audioChunks = []; // Reset for next recording
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const recordedFile = new File([audioBlob], `recording_${timestamp}.webm`, { type: 'audio/webm' });

                // Use the existing upload logic to send the recorded file
                uploadFile(recordedFile, model);

                // Stop microphone track
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();

            // Update UI to show recording is in progress
            modelConfirmBtn.textContent = 'Stop Recording';
            modelConfirmBtn.onclick = () => {
                mediaRecorder.stop();
                // Reset button behavior
                modelConfirmBtn.textContent = 'Start';
                modelConfirmBtn.onclick = modelConfirmClickHandler;
                closeModal(modelModal);
            };

        } catch (error) {
            console.error("Error accessing microphone:", error);
            alert("Could not access microphone. Please ensure you have granted permission.");
            closeModal(modelModal);
        }
    }

    const modelConfirmClickHandler = async () => {
        if (modalAction === 'upload') {
            await uploadFile(fileToUpload, selectedModel);
            closeModal(modelModal);
        } else if (modalAction === 'record') {
            // This button's behavior is now changed inside startRecording
            // to become a "Stop" button.
            await startRecording(selectedModel);
        }
    };

    modelConfirmBtn.addEventListener('click', modelConfirmClickHandler);

    // --- Upload Logic (Updated) ---
    async function uploadFile(file, model) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('destination_folder', currentPath);
        formData.append('model', model); // Pass selected model

        try {
            const response = await fetch('/api/recordings', {
                method: 'POST',
                body: formData,
            });
            if (!response.ok) throw new Error((await response.json()).error);
            fetchAndDisplayContents(currentPath); // Refresh view
        } catch (error) {
            console.error('Error uploading file:', error);
            alert(`Upload failed: ${error.message}`);
        } finally {
            fileInput.value = ''; // Reset input
        }
    }

    // Hook up buttons to open the model selection modal
    newRecordingBtn.addEventListener('click', () => openModelModal('record'));
    uploadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            openModelModal('upload', file);
        }
    });

    // --- Action Menu Handling ---

    function closeAllActionMenus() {
        document.querySelectorAll('.actions-menu').forEach(menu => menu.remove());
    }

    function createActionMenu(path, targetCell) {
        closeAllActionMenus(); // Close any open menus first

        const menu = document.createElement('ul');
        menu.className = 'actions-menu';
        menu.innerHTML = `
            <li><a href="#" class="action-open" data-path="${path}">Open</a></li>
            <li><a href="#" class="action-rename" data-path="${path}">Rename</a></li>
            <li><a href="#" class="action-move" data-path="${path}">Move</a></li>
            <li><hr></li>
            <li><a href="#" class="action-delete delete" data-path="${path}">Delete</a></li>
        `;
        targetCell.appendChild(menu);
        menu.style.display = 'block'; // Show the menu
    }

    async function deleteFile(filePath) {
        if (!confirm(`Are you sure you want to delete "${filePath}"?`)) {
            return;
        }
        try {
            const response = await fetch(`/api/recordings/${encodeURIComponent(filePath)}`, {
                method: 'DELETE',
            });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Delete failed');
            }
            // Refresh the view to show the file has been removed
            fetchAndDisplayContents(currentPath);
        } catch (error) {
            console.error('Error deleting file:', error);
            alert(`Delete failed: ${error.message}`);
        }
    }


    // Global click listener to close menus
    document.addEventListener('click', (event) => {
        // If the click is not on an actions button, close any open menus
        if (!event.target.classList.contains('actions-btn')) {
            closeAllActionMenus();
        }
    });

    // --- Modal Handling ---

    const renameModal = document.getElementById('rename-modal');
    const moveModal = document.getElementById('move-modal');
    const renameInput = document.getElementById('rename-input');
    const renameConfirmBtn = document.getElementById('rename-confirm-btn');
    const moveConfirmBtn = document.getElementById('move-confirm-btn');
    const moveFolderTreeContainer = document.getElementById('move-folder-tree');

    let itemToRename = null;
    let itemToMove = null;
    let moveToPath = null;

    function closeModal(modal) {
        modal.style.display = 'none';
    }

    // Add event listeners to close buttons
    document.querySelectorAll('.modal .close-btn').forEach(btn => {
        btn.onclick = () => closeModal(btn.closest('.modal'));
    });

    // Open Rename Modal
    function openRenameModal(path) {
        itemToRename = path;
        const itemName = path.split('/').pop();
        document.getElementById('rename-item-name').textContent = itemName;
        renameInput.value = itemName;
        renameModal.style.display = 'block';
        renameInput.focus();
    }

    // Open Move Modal
    async function openMoveModal(path) {
        itemToMove = path;
        moveToPath = null; // Reset selection
        moveConfirmBtn.disabled = true;
        document.getElementById('move-item-name').textContent = path.split('/').pop();

        // Fetch and render folder tree for moving
        const response = await fetch('/api/folders/tree');
        const tree = await response.json();
        const root = { type: 'folder', name: 'My Recordings (Root)', path: '.', children: tree };
        moveFolderTreeContainer.innerHTML = `<ul>${createFolderHtml(root)}</ul>`;

        moveModal.style.display = 'block';
    }

    // Confirm Rename
    renameConfirmBtn.addEventListener('click', async () => {
        const newName = renameInput.value.trim();
        if (!newName || newName.includes('/')) {
            alert('Invalid name.');
            return;
        }
        try {
            const response = await fetch('/api/item/rename', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: itemToRename, new_name: newName }),
            });
            if (!response.ok) throw new Error((await response.json()).error);

            closeModal(renameModal);
            await renderFolderTree(); // Folder structure might have changed
            await fetchAndDisplayContents(currentPath);
        } catch (error) {
            alert(`Rename failed: ${error.message}`);
        }
    });

    // Select folder in Move modal
    moveFolderTreeContainer.addEventListener('click', (event) => {
        const target = event.target.closest('.folder-item');
        if (target) {
            // Clear previous selection
            moveFolderTreeContainer.querySelectorAll('.folder-item.selected').forEach(el => el.classList.remove('selected'));
            // Select new one
            target.classList.add('selected');
            moveToPath = target.dataset.path;
            moveConfirmBtn.disabled = false;
        }
    });

    // Confirm Move
    moveConfirmBtn.addEventListener('click', async () => {
        if (!itemToMove || moveToPath === null) return;
        try {
            const response = await fetch('/api/item/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source: itemToMove, destination: moveToPath }),
            });
            if (!response.ok) throw new Error((await response.json()).error);

            closeModal(moveModal);
            await renderFolderTree();
            await fetchAndDisplayContents(currentPath);
        }
        catch (error)
        {
            alert(`Move failed: ${error.message}`);
        }
    });

    // --- View Switching ---
    const fileBrowserView = document.getElementById('file-browser-view');
    const detailView = document.getElementById('detail-view');
    const backToBrowserBtn = document.getElementById('back-to-browser-btn');

    function showBrowserView() {
        detailView.style.display = 'none';
        fileBrowserView.style.display = 'block';
        startPolling(); // Restart polling when returning to browser
    }

    async function showDetailView(path) {
        if (pollingInterval) clearInterval(pollingInterval); // Stop polling

        try {
            const response = await fetch(`/api/file/${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error((await response.json()).error);

            const details = await response.json();

            document.getElementById('detail-file-name').textContent = details.fileName;

            // TODO: Actually render a spectrogram image when available
            const spectrogramContainer = document.getElementById('spectrogram-container');
            spectrogramContainer.innerHTML = details.spectrogram
                ? `<img src="${details.spectrogram}" alt="Spectrogram">`
                : '<p>Spectrogram not yet generated.</p>';

            const transcriptionText = document.getElementById('transcription-text');
            if (details.status === 'Completed' && details.transcription) {
                transcriptionText.textContent = details.transcription;
            } else if (details.status === 'Processing') {
                transcriptionText.textContent = 'Transcription is currently processing...';
            } else {
                transcriptionText.textContent = 'Transcription not available.';
            }

            fileBrowserView.style.display = 'none';
            detailView.style.display = 'block';

        } catch (error) {
            alert(`Error opening file: ${error.message}`);
        }
    }

    backToBrowserBtn.addEventListener('click', showBrowserView);


    // --- Event Listeners (Final Update) ---

    // Use event delegation for action buttons and menu items
    recordingsTbody.addEventListener('click', async (event) => {
        event.preventDefault();
        const target = event.target;

        if (target.classList.contains('actions-btn')) {
            const path = target.dataset.path;
            const cell = target.closest('td');
            if (!cell.querySelector('.actions-menu')) {
                 createActionMenu(path, cell);
            }
            return;
        }

        if (target.closest('.actions-menu')) {
            const path = target.dataset.path;
            if (target.classList.contains('action-delete')) {
                await deleteFile(path);
            } else if (target.classList.contains('action-open')) {
                await showDetailView(path); // <-- Connect to detail view
            } else if (target.classList.contains('action-rename')) {
                openRenameModal(path);
            } else if (target.classList.contains('action-move')) {
                await openMoveModal(path);
            }
            closeAllActionMenus();
        }
    });

    // --- Initial Load ---
    async function initialize() {
        await renderFolderTree();
        await fetchAndDisplayContents(currentPath);
        startPolling();
    }

    initialize();
});