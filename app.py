from flask import Flask, render_template, request, send_file, jsonify, g
import os
import yt_dlp
from ffmpeg_progress_yield import FfmpegProgress
import uuid
import sched
import time
import shutil
import threading
import re


# Create a scheduler object
s = sched.scheduler(time.time, time.sleep)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for Flask session
# Set a default download directory
DEFAULT_DOWNLOAD_PATH = '/downloads'
APPLE_MUSIC_AUTO_ADD_PATH = '/auto_add_folder/Automatically Add to Music.localized/'

# Ensure the default download path exists
if not os.path.exists(DEFAULT_DOWNLOAD_PATH):
    os.makedirs(DEFAULT_DOWNLOAD_PATH)
# Store download progress
download_progress = {}


def delete_directory(path):
    """Delete a directory."""
    shutil.rmtree(path, ignore_errors=True)


# Progress hook function
def progress_hook(d):
    print(d['status'])
    if d['status'] == 'downloading':
        print(d['_percent_str'])
        percentage = re.sub("\\x1b\[[0-9;]*m ?", '', d['_percent_str'])
        download_progress['progress'] = percentage  # Store progress in session
    elif d['status'] == 'finished':
        download_progress['progress'] = '100%'  # Download complete


def add_metadata(file_path, artist, album, title, download_path):
    # Construct the ffmpeg command to add metadata
    cmd = [
        'ffmpeg', '-i', file_path,
        '-metadata', f'artist={artist}',
        '-metadata', f'album={album}',
        '-metadata', f'title={title}',
        os.path.join(download_path, title + '.m4a')
    ]
    ff = FfmpegProgress(cmd)
    for newProgr in ff.run_command_with_progress():
        download_progress['conversion_progress'] = str(newProgr) + '%'
    print('Download and conversion complete!')
    return title + '.m4a'


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        link = request.form['link'].strip()
        artist = request.form.get('artist', '')
        album = request.form.get('album', '')
        title = request.form.get('title', '')
        download_location = request.form['download-location']

        # For now, just print the link to the console
        download_path = DEFAULT_DOWNLOAD_PATH
        try:
            # create a uuid for the download
            new_uuid = uuid.uuid4()
            download_path = os.path.join(download_path, str(new_uuid))
            # Reset progress in session
            # reset the progress
            download_progress['progress'] = '0%'
            download_progress['conversion_progress'] = '0%'

            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),  # Save as title.extension
                'quiet': True,
                'noplaylist': True,  # Only download a single video (not a playlist)
                'progress_hooks': [progress_hook],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(link, download=True)
                audio_file = ydl.prepare_filename(info_dict)

            file_name = add_metadata(audio_file, artist, album, title, download_path)
            # After download, redirect to success page or trigger download
            if download_location == 'device':
                # Send the file for download
                print('Sending file for download')
                response = send_file(os.path.abspath(os.path.join(download_path, file_name)), as_attachment=True)

                # Schedule the directory to be deleted after a delay
                s.enter(3000, 1, delete_directory, argument=(download_path,))  # Delete after 60 seconds
                threading.Thread(target=s.run).start()
                return response
            elif download_location == 'default':
                shutil.move(os.path.join(download_path, file_name),
                            os.path.join(APPLE_MUSIC_AUTO_ADD_PATH, file_name))
                # delete the download directory
                s.enter(30, 1, delete_directory, argument=(download_path,))  # Delete after 60 seconds
                threading.Thread(target=s.run).start()
                return jsonify({'status': 'Complete! File Saved to Server.'})

        except Exception as e:
            print("Failed to download: " + str(e))
            return jsonify({'error': f"Failed to download: {str(e)}"})
    return render_template('index.html')


@app.route('/progress', methods=['GET'])
def progress():
    # Send current progress to the frontend
    print('Download Progress: ' + download_progress.get('progress', '0%') + ' Conversion Progress: ' +
          download_progress.get('conversion_progress', '0%'))
    return jsonify(progress=download_progress.get('progress', '0%'),
                   conversion_progress=download_progress.get('conversion_progress', '0%'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=False)
