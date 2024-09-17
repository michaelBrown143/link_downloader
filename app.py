from flask import Flask, render_template, request, send_file, jsonify, g, abort
import os
import yt_dlp
from ffmpeg_progress_yield import FfmpegProgress
import uuid
import sched
import time
import shutil
import threading
import re
from celery import Celery
from celery.utils.log import get_task_logger
from celery import states
from datetime import datetime, timedelta
from werkzeug.exceptions import BadRequest

SECRET_KEY = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', False)
DEFAULT_DOWNLOAD_PATH = './downloads'
APPLE_MUSIC_AUTO_ADD_PATH = '/Users/michael/Music/iTunes/iTunes Media/Automatically Add to Music.localized/'
if SECRET_KEY:
    APPLE_MUSIC_AUTO_ADD_PATH = '/auto_add_folder/Automatically Add to Music.localized/'
    DEFAULT_DOWNLOAD_PATH = './downloads'
    print('I am running in a Docker container')

# Create a scheduler object
s = sched.scheduler(time.time, time.sleep)

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Required for Flask session


# Set a default download directory

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    return celery


app.config['CELERY_BROKER_URL'] = 'redis://redis:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://redis:6379/0'

celery = make_celery(app)
# Ensure the default download path exists
if not os.path.exists(DEFAULT_DOWNLOAD_PATH):
    os.makedirs(DEFAULT_DOWNLOAD_PATH)
# Store download progress
task_progress = {}

logger = get_task_logger(__name__)

active_ids = []
on_server_tasks = []
available_for_download = []


@celery.task(bind=True)
def download_and_convert(self, link, artist, album, title, download_location='default'):
    logger.info('Downloading and converting...')
    logger.info('ID: ' + self.request.id)
    start_time = datetime.now()

    def progress_hook(d):
        if d['status'] == 'downloading':
            percentage = re.sub("\\x1b\[[0-9;]*m ?", '', d['_percent_str'])
            self.update_state(state='PROGRESS', meta={'title': title,
                                                      'download_progress': percentage,
                                                      'conversion_progress': '0%',
                                                      'start_time': start_time.isoformat(),
                                                      'location': download_location})
            logger.info('Progress: ' + percentage)
        elif d['status'] == 'finished':
            self.update_state(state='PROGRESS', meta={'title': title, 'download_progress': '100%',
                                                      'conversion_progress': '0%',
                                                      'start_time': start_time.isoformat(),
                                                      'location': download_location})

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DEFAULT_DOWNLOAD_PATH, '%(title)s.%(ext)s'),  # Save as title.extension
        'quiet': True,
        'noplaylist': True,  # Only download a single video (not a playlist)
        'progress_hooks': [progress_hook],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(link, download=True)
        audio_file = ydl.prepare_filename(info_dict)

    cmd = [
        'ffmpeg', '-y', '-i', audio_file,
        '-metadata', f'artist={artist}',
        '-metadata', f'album={album}',
        '-metadata', f'title={title}',
        os.path.join(DEFAULT_DOWNLOAD_PATH, title + '.m4a')
    ]
    # check if file exists


    print(os.path.join(DEFAULT_DOWNLOAD_PATH, title + '.m4a'))
    ff = FfmpegProgress(cmd)
    for newProgr in ff.run_command_with_progress():
        self.update_state(state='PROGRESS', meta={'title': title,
                                                  'download_progress': '100%',
                                                  'conversion_progress': str(newProgr) + '%',
                                                  'start_time': start_time.isoformat(),
                                                  'location': download_location})
    self.update_state(state='SUCCESS', meta={'title': title,
                                             'download_progress': '100%',
                                             'conversion_progress': '100%',
                                             'file_name': title + '.m4a',
                                             'start_time': start_time.isoformat(),
                                             'location': download_location, })
    # delete original file
    print("deleting" + audio_file)
    #os.remove(audio_file)
    logger.info('Download and conversion complete!')
    return title + '.m4a'


def delete_directory(path):
    """Delete a directory."""
    shutil.rmtree(path, ignore_errors=True)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')


@app.route('/start_download', methods=['POST', 'GET'])
def start_download():
    print('start_download')
    print(request.get_json())
    try:
        data = request.get_json()
        link = data.get('link')
        artist = data.get('artist')
        album = data.get('album')
        title = data.get('title')
        location = data.get('download_location', 'default')
        # Call the download_and_convert function
        task = download_and_convert.delay(link, artist, album, title, location)
        task_id = task.id
        active_ids.append(task_id)
        print('task_id: ' + task_id)
        return jsonify({'status': 'SUCCESS', 'task_id': task_id})
    except Exception as e:
        return jsonify({'status': 'ERROR', 'error': str(e)})


@app.route('/update_all_tasks', methods=['GET'])
def update_all_tasks():
    # create a dict of all tasks from their meta
    try:
        still_processing = []
        # iterate through task ids and add to the list if they are from the last 48 hours
        for task_id in active_ids:
            task = celery.AsyncResult(task_id)
            # if complete and device, add to available_for_download
            if task.state == 'SUCCESS':
                if task.result['location'] == 'device':
                    available_for_download.append(task.result)
                    # schedule the file for deletion after 48 hours
                    s.enter(48 * 60 * 60, 1, delete_directory, argument=(task.result['file_name'],))
                elif task.result['location'] == 'default':
                    # move the file to the auto add folder
                    print('moving file: ' + os.path.join(DEFAULT_DOWNLOAD_PATH, task.result['file_name']))
                    print('to: ' + os.path.join(APPLE_MUSIC_AUTO_ADD_PATH, task.result['file_name']))
                    shutil.move(os.path.join(DEFAULT_DOWNLOAD_PATH, task.result['file_name']),
                                os.path.join(APPLE_MUSIC_AUTO_ADD_PATH, task.result['file_name']))
                    on_server_tasks.append(task.result)
                active_ids.remove(task_id)
            elif task.state == 'PROGRESS':
                still_processing.append(task.result)
        # go through on_server_tasks and remove any that are older than 48 hours
        for task in on_server_tasks:
            start_time = datetime.fromisoformat(task['start_time'])
            if datetime.now() - start_time > timedelta(hours=48):
                on_server_tasks.remove(task)
        # go through available_for_download and remove any that are older than 48 hours
        for task in available_for_download:
            start_time = datetime.fromisoformat(task['start_time'])
            if datetime.now() - start_time > timedelta(hours=48):
                available_for_download.remove(task)
                # delete the file
                os.remove(DEFAULT_DOWNLOAD_PATH + task['file_name'])
        print({'in_progress': still_processing, 'on_server': on_server_tasks,
               'available_for_download': available_for_download})
        # return a JSON array of all task metas
        return jsonify({'in_progress': still_processing, 'on_server': on_server_tasks,
                        'available_for_download': available_for_download})
    except Exception as e:
        return jsonify({'status': 'ERROR', 'error': str(e)})


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        file_path = os.path.join(DEFAULT_DOWNLOAD_PATH, filename)

        # Check if the file exists
        if not os.path.isfile(file_path):
            abort(404)  # If file is not found, return 404 error

        # Send the file as an attachment (download)
        return send_file(file_path, as_attachment=True)

    except Exception as e:
        return jsonify({'status': 'ERROR', 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5555, debug=False)
