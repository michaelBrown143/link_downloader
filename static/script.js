const YOUTUBE_REGEX = /^(https?:\/\/)?(www\.youtube\.com|youtube\.com|youtu\.be)(\/.+)?$/;
const SOUNDCLOUD_REGEX = /^(https?:\/\/)?((www|on|m)\.soundcloud\.com|soundcloud\.com)(\/.+)?$/;
var error_occurred = false;
var function_returned = false;
const form = document.getElementById('download-form');
const progressBarFill = document.getElementById('progress-bar-fill');
const successDiv = document.getElementById('success');
const errorDiv = document.getElementById('js-error');

const linkInput = document.getElementById('link');

// Reset the validation message whenever the link input value changes
linkInput.addEventListener('input', function() {
    linkInput.setCustomValidity('');
});

function download(blob) {
    // Create a new blob object
    const newBlob = new Blob([blob]);
    const link = document.createElement('a');
    link.href = URL.createObjectURL(newBlob);
    link.download = 'requested_track.m4a';  // Replace with your desired file name and extension
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
function updateAllTasks() {
    fetch('/update_all_tasks')
        .then(response => response.json())
        .then(data => {
            console.log('Data:', data);
            if (data.status == 'ERROR') {
                throw new Error(data.message);
            };
            // similar to above, but for each of the other lists
            const inProgressList = document.getElementById('in-progress-list');
            inProgressList.innerHTML = '';
            const availableList = document.getElementById('available-list');
            availableList.innerHTML = '';
            const onServerList = document.getElementById('on-server-list');
            onServerList.innerHTML = '';
            // iterate through the in_progress, available_for_download, and available_on_server lists
            data.in_progress.forEach(task => {
                const inProgressList = document.getElementById('in-progress-list');
                inProgressList.innerHTML = '';
                const availableList = document.getElementById('available-list');
                availableList.innerHTML = '';
                const onServerList = document.getElementById('on-server-list');
                onServerList.innerHTML = '';
                // iterate through the in_progress, available_for_download, and available_on_server lists
                data.in_progress.forEach(task => {
                const inProgressList = document.getElementById('in-progress-list');

                // Create the row container
                const taskRow = document.createElement('div');
                taskRow.className = 'progress-bar-container';

                // File name column
                const fileName = document.createElement('div');
                fileName.className = 'file-name';
                fileName.textContent = task.title; // Assuming task has a name property
                taskRow.appendChild(fileName);

                // Progress bars container
                const progressBars = document.createElement('div');
                progressBars.className = 'progress-bars';

                // Download progress bar
                const downloadProgressBar = document.createElement('div');
                downloadProgressBar.className = 'progress-bar';
                const downloadFill = document.createElement('div');
                downloadFill.className = 'progress-bar-fill';
                downloadFill.style.width = task.download_progress; // e.g., '50%'
                const downloadLabel = document.createElement('div');
                downloadLabel.className = 'progress-bar-label';
                downloadLabel.textContent = task.download_progress; // e.g., '50%'
                downloadProgressBar.appendChild(downloadFill);
                downloadProgressBar.appendChild(downloadLabel);
                progressBars.appendChild(downloadProgressBar);

                // Conversion progress bar
                const conversionProgressBar = document.createElement('div');
                conversionProgressBar.className = 'progress-bar';
                const conversionFill = document.createElement('div');
                conversionFill.className = 'progress-bar-fill';
                conversionFill.style.width = task.conversion_progress; // e.g., '75%'
                const conversionLabel = document.createElement('div');
                conversionLabel.className = 'progress-bar-label';
                conversionLabel.textContent = task.conversion_progress; // e.g., '75%'
                conversionProgressBar.appendChild(conversionFill);
                conversionProgressBar.appendChild(conversionLabel);
                progressBars.appendChild(conversionProgressBar);

                taskRow.appendChild(progressBars);
                inProgressList.appendChild(taskRow);
                });
            });
            //iterate through the available_for_download list, no progress bars but a link to the file
            data.available_for_download.forEach(task => {
                const taskDiv = document.createElement('div');
                taskDiv.textContent = task.title;
                const link = document.createElement('a');
                link.href = '/download/' + task.file_name;  // Replace '/downloads/' with the actual path to the downloads directory
                link.textContent = 'Download ' + task.file_name;
                taskDiv.appendChild(link);
                availableList.appendChild(taskDiv);
            });
            //iterate through the available_on_server list, no progress bars
            data.on_server.forEach(task => {
                const taskDiv = document.createElement('div');
                taskDiv.textContent = task.title;
                onServerList.appendChild(taskDiv);
            });
        })
        .catch(error => {
            errorDiv.textContent = 'An error occurred. Please try again.';
            errorDiv.style.display = 'block';
            console.error('Error:', error);
        });
    // repeat this function every 5 seconds
    setTimeout(updateAllTasks, 2000);
};

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('download-form');
    const successDiv = document.getElementById('success');
    const errorDiv = document.getElementById('js-error');

    // Handle form submission with AJAX
    form.addEventListener('submit', function(event) {
        event.preventDefault();
        console.log('Form submitted');
        const linkInput = document.getElementById('link');
        const link = linkInput.value.trim();
        const artist = document.getElementById('artist').value.trim();
        const album = document.getElementById('album').value.trim();
        const title = document.getElementById('title').value.trim();
        const download_location = document.querySelector('input[name="download-location"]:checked').value;
        var task_id = '';
        const data = {
            link: link,
            artist: artist,
            album: album,
            title: title,
            download_location: download_location
        }; // Prevent form submission
        successDiv.textContent = '';  // Clear the success message
        successDiv.style.display = 'none';
        errorDiv.textContent = '';  // Clear the error message
        errorDiv.style.display = 'none';
        if (!YOUTUBE_REGEX.test(link) && !SOUNDCLOUD_REGEX.test(link)) {
            // If the link is invalid, show an alert and prevent form submission
            linkInput.setCustomValidity('Please enter a valid YouTube or SoundCloud link.');
        } else {
            linkInput.setCustomValidity('');
            event.preventDefault();  // Prevent the default form submission

            const formData = new FormData(form);  // Collect form data

            // Start polling for progress updates
            const downloadLocation = formData.get('download-location');

            // Start the download_and_convert task
            fetch('/start_download', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                // Now you can access data.status
                console.log('Data:', data);
                console.log(data.status);
                if (data.status === 'SUCCESS') {
                    task_id = data.task_id;
                    console.log(data.status);
                } else if (data.status === 'ERROR') {
                    throw new Error(data.message);
                }
                // clear the form
                form.reset();
            })
            .catch(error => {
                // update error div and print to console
                errorDiv.textContent = 'An error occurred. Please try again.';
                console.error('Error:', error);
            });
        };
    });
});
updateAllTasks();