"""Privately replay the two recorded user-owned Node auth flows after reboot.

No credential/argv output, cloud registration changes, or broad startup service.
Requires the fresh checkpoint's root-only mcp-recovery records.
"""
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import subprocess
import time


def listening(port):
    with socket.socket() as connection:
        connection.settimeout(2)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def restore():
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    ports = [3500, 3502]
    if any(listening(port) for port in ports):
        if all(listening(port) for port in ports):
            print(json.dumps({'listeners': ports, 'already_running': True}))
            return
        raise RuntimeError('Partial MCP state requires manual review')
    source = Path('/var/backups/homelab-upgrade/mcp-recovery')
    prior_logs = list(source.glob('restored-listener-*.log'))
    if len(prior_logs) == 2 and all('Authentication successful.' in p.read_text()
                                  for p in prior_logs):
        print(json.dumps({'saved_authentication_validated': True, 'uid': 1000,
                          'callback_listeners_required': False,
                          'note': 'Recorded auth commands successfully validate saved tokens and exit'}))
        return
    processes = [row for row in json.loads((source / 'processes.json').read_text())
                 if Path(row['argv'][0]).name == 'node']
    if len(processes) != 2:
        raise RuntimeError('Unexpected MCP listener process count')
    started = []
    children = []
    os.umask(0o077)
    for index, row in enumerate(processes):
        user = pwd.getpwuid(row['uid'])
        if row['uid'] == 0 or row['uid'] != 1000:
            raise RuntimeError('Unexpected original MCP user')
        directory = Path(user.pw_dir) / '.config/homelab-upgrade'
        directory.mkdir(mode=0o700, exist_ok=True)
        os.chown(str(directory), row['uid'], row['gid'])
        credential = directory / 'gcp-oauth.keys.json'
        if credential.exists():
            if credential.read_bytes() != (source / credential.name).read_bytes():
                raise RuntimeError('Refusing to overwrite differing durable credential')
        else:
            shutil.copyfile(str(source / credential.name), str(credential))
        credential.chmod(0o600)
        os.chown(str(credential), row['uid'], row['gid'])
        if not Path(row['argv'][1]).is_file():
            raise RuntimeError('Recorded Node package entrypoint missing')
        environment = dict(HOME=user.pw_dir, USER=user.pw_name, LOGNAME=user.pw_name,
                           PATH='/usr/local/bin:/usr/bin:/bin', LANG='C.UTF-8')
        environment.update(row['environment'])
        environment['GOOGLE_OAUTH_CREDENTIALS'] = str(credential)
        def user_identity():
            os.initgroups(user.pw_name, row['gid'])
            os.setgid(row['gid'])
            os.setuid(row['uid'])
        logpath = source / ('restored-listener-%d.log' % index)
        with logpath.open('xb') as log:
            process = subprocess.Popen(row['argv'], env=environment, cwd=row['cwd'],
                                       stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                       start_new_session=True, preexec_fn=user_identity)
        started.append(process.pid)
        children.append((process, logpath))
        time.sleep(4)
        if process.poll() is not None and process.returncode != 0:
            raise RuntimeError('Recorded MCP process exited; inspect private log')
    for attempt in range(15):
        if all(process.poll() == 0 and 'Authentication successful.' in log.read_text()
               for process, log in children):
            print(json.dumps({'saved_authentication_validated': True, 'uid': 1000,
                              'callback_listeners_required': False,
                              'automatic_boot_service_created': False}))
            return
        if all(listening(port) for port in ports):
            print(json.dumps({'listeners': ports, 'uid': 1000, 'started_pids': started,
                              'credentials_durable_mode': '0600',
                              'automatic_boot_service_created': False}))
            return
        time.sleep(2)
    raise RuntimeError('Expected MCP ports unavailable; inspect private logs')


if __name__ == '__main__':
    restore()
