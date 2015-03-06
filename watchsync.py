#!/usr/bin/env python

import json
import logging
import os.path as path
import subprocess
import sys
import time

try:
    import daemonocle
except ImportError:
    logging.critical("watchsync requires the daemonocle module to be installed.")

    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    logging.critical("watchsync requires the watchdog module to be installed.")

    sys.exit(1)


SETTINGS_FILE = '/etc/watchsync.json'

SETTINGS_DEFAULT = {
    'pidfile': '/var/run/watchsync.pid',
    'logfile': '/var/log/watchsync.log',
    'paths': [
        {
        'sudo_as': '',
        'local_path': '',
        'remote_path': '',
        'rsync_params': ['-vazq', '--executability', '--delete'],
        }
    ]
}

observers = {}
rsync_path = ''

def read_settings():
    settings_file_path = path.expanduser(SETTINGS_FILE)

    if not path.exists(settings_file_path):
        logging.warn("Settings file not found.")

        try:
            with open(settings_file_path, 'w') as settings_file:
                json.dump(
                    obj=SETTINGS_DEFAULT,
                    fp=settings_file,
                    indent=4,
                    sort_keys=True
                    )

                logging.critical(
                    "Wrote new default settings file to \"{path}\"".format(
                        path=settings_file_path
                        )
                    )

            sys.exit(1)
        except Exception:
            logging.critical(
                "Could not write a new default settings file to \"{path}\"".format(
                    path=settings_file_path
                    )
                )

            sys.exit(1)
    else:
        try:
            with open(settings_file_path, 'r') as settings_file:
                settings = json.load(settings_file)

            return settings
        except Exception:
            logging.critical(
                "Could not read settings file from \"{path}\"".format(
                    path=settings_file_path
                    )
                )

            sys.exit(1)

settings = read_settings()

class RemoteSyncer(FileSystemEventHandler):
    def __init__(self, watch):
        self.watch = watch

        self.remote_path = watch.get('remote_path', '')


    def on_any_event(self, event):
        sudo_as = []

        if self.watch.get('sudo_as', None):
            sudo_as = ['/usr/bin/sudo', '-H', '-u', str(self.watch.get('sudo_as'))]

        local_path = path.expanduser(self.watch.get('local_path'))
        remote_path = path.expanduser(self.watch.get('remote_path'))
        rsync_params = settings.get('rsync_params', ['-vazq', '--executability', '--delete'])

        command_args = sudo_as + [rsync_path] + rsync_params + [local_path+'/', remote_path]

        process = subprocess.Popen(command_args)

        stdout, stderr = process.communicate()

        while process.poll() == None:
            line = stdout.readline().strip()

            logging.debug(line)

def start():
    logging.basicConfig(
        filename=settings.get('logfile', '/var/log/watchsync.log'),
        level=logging.WARN,
        format='%(asctime)s [%(levelname)s] %(message)s',
        )

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

    if not rsync_path:
        logging.critical("rsync executable not found.")

        sys.exit(1)

    if len(sys.argv) > 1:
        daemon = daemonocle.Daemon(
            worker=start,
            shutdown_callback=stop,
            pidfile=settings.get('pidfile', '/var/run/watchsync.pid')
            )

        daemon.do_action(sys.argv[1])
    else:
        start()
