#!/usr/bin/env python

import daemonocle
import json
import logging
import os.path as path
import subprocess
import sys
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


SETTINGS_FILE = '~/.watchsync.json'

SETTINGS_DEFAULT = {
    'paths': [
        {
        'sudo_as': '',
        'local_path': '',
        'remote_path': ''
        }
    ]
}


observers = {}
rsync_path = ''

def read_settings():
    settings_file_path = path.expanduser(SETTINGS_FILE)

    if not path.exists(settings_file_path):
        print "Settings file not found."

        try:
            with open(settings_file_path, 'w') as settings_file:
                json.dump(
                    obj=SETTINGS_DEFAULT,
                    fp=settings_file,
                    indent=4,
                    sort_keys=True
                    )

                print "Wrote new default settings file to \"{path}\"".format(
                    path=settings_file_path
                    )

            sys.exit(1)
        except Exception:
            print "Could not write a new default settings file to \"{path}\"".format(
                path=settings_file_path
                )

            sys.exit(1)
    else:
        try:
            with open(settings_file_path, 'r') as settings_file:
                settings = json.load(settings_file)

            return settings
        except Exception:
            print "Could not read settings file from \"{path}\"".format(
                path=settings_file_path
                )

            sys.exit(1)


class RemoteSyncer(FileSystemEventHandler):
    def __init__(self, watch):
        self.watch = watch

        self.remote_path = watch.get('remote_path', '')


    def on_any_event(self, event):
        logging.debug("on_any_event")
        sudo_as = ['sudo', '-u', self.watch.get('sudo_as')]

        local_path = path.expanduser(self.watch.get('local_path'))
        remote_path = path.expanduser(self.watch.get('remote_path'))

        command_args = [rsync_path, '-vaz', local_path, remote_path]

        process = subprocess.Popen(command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while process.poll() == None:
            line = process.stdout.readline().strip()

            logging.debug(line)

def start():
    logging.basicConfig(
        filename='watchsync.log',
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(message)s',
        )

    settings = read_settings()

    for watch in settings.get('paths', []):
        local = path.expanduser(watch.get('local_path', ''))
        remote = watch.get('remote_path', '')

        if not path.exists(local):
            continue

        observer = Observer()
        observer.schedule(RemoteSyncer(watch), local, recursive=True)
        observer.start()

        observers[local] = observer

    while True:
        time.sleep(10)


def stop():
    for local, observer in observers.iteritems():
        observer.stop()


if __name__ == "__main__":
    rsync_path = subprocess.check_output(['/usr/bin/which', 'rsync']).strip()

    if not len(rsync_path):
        print "rsync executable not found."
        sys.exit()

    if len(sys.argv) > 1:
        daemon = daemonocle.Daemon(
            worker=start,
            shutdown_callback=stop,
            pidfile='/tmp/watchsync.pid',
            )

        daemon.do_action(sys.argv[1])
    else:
        start()
