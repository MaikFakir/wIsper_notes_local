document.addEventListener('DOMContentLoaded', function() {
    const recordingsTbody = document.querySelector('.recordings-list tbody');

    async function fetchAndDisplayRecordings() {
        try {
            const response = await fetch('/api/recordings');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const recordings = await response.json();

            // Clear existing rows
            recordingsTbody.innerHTML = '';

            if (recordings.length === 0) {
                recordingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">No recordings found.</td></tr>';
                return;
            }

            // Populate the table
            recordings.forEach(rec => {
                const row = document.createElement('tr');

                const statusClass = rec.status.toLowerCase();

                row.innerHTML = `
                    <td>${rec.fileName}</td>
                    <td>${rec.duration}</td>
                    <td>${rec.dateCreated}</td>
                    <td><span class="status ${statusClass}">${rec.status}</span></td>
                    <td class="actions">
                        <button class="play-btn" data-path="${rec.path}">▶</button>
                        <button class="delete-btn" data-path="${rec.path}">🗑️</button>
                        <button class="copy-btn" data-path="${rec.path}">📋</button>
                    </td>
                `;
                recordingsTbody.appendChild(row);
            });

        } catch (error) {
            console.error("Failed to fetch recordings:", error);
            recordingsTbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">Error loading recordings.</td></tr>';
        }
    }

    // Initial load
    fetchAndDisplayRecordings();

    // Poll for updates every 3 seconds to reflect worker progress
    setInterval(fetchAndDisplayRecordings, 3000);

    // --- Event Listeners ---

    const uploadBtn = document.querySelector('.upload-btn');
    const fileInput = document.getElementById('audio-upload-input');

    uploadBtn.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/recordings', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Upload failed');
            }

            // Refresh the list to show the new file
            fetchAndDisplayRecordings();

        } catch (error) {
            console.error('Error uploading file:', error);
            alert(`Upload failed: ${error.message}`);
        } finally {
            // Reset the file input
            event.target.value = '';
        }
    });

    // Use event delegation for delete buttons
    recordingsTbody.addEventListener('click', async (event) => {
        if (event.target.classList.contains('delete-btn')) {
            const filePath = event.target.dataset.path;

            if (!confirm(`Are you sure you want to delete "${filePath}"?`)) {
                return;
            }

            try {
                const response = await fetch(`/api/recordings/${filePath}`, {
                    method: 'DELETE',
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || 'Delete failed');
                }

                // Remove the row from the table directly
                event.target.closest('tr').remove();

            } catch (error) {
                console.error('Error deleting file:', error);
                alert(`Delete failed: ${error.message}`);
            }
        }
    });
});