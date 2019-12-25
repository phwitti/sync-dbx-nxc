# Copyright (C) 2019  Philipp M. Wittershagen
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Synchronize your Dropbox with your NextCloud"""

import argparse
import dropbox
import hashlib
import json
import nextcloud
import os
import urllib.parse
from datetime import datetime


# globals

TIME_NOW_STR = datetime.utcnow().strftime("%Y%m%d%H%M%S")

DROPBOX_SYNC_ROOT = '/'
NEXTCLOUD_USER = '<nextcloud_user>'
NEXTCLOUD_SYNC_ROOT = '/'
NEXTCLOUD_SYNC_ROOT_TEXT = '/remote.php/dav/files/' + NEXTCLOUD_USER + NEXTCLOUD_SYNC_ROOT

SIMULATE = False
VERBOSE = False

VERSION = '1.0'
LICENSE = '''sync-dbx-nxc ''' + VERSION + ''' - A script that synchronizes Dropbox and NextCloud.
Copyright (C) 2019  Philipp M. Wittershagen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.'''


# command-line-interface

parser = argparse.ArgumentParser(
    description='sync-dbx-nxc - A script that synchronizes Dropbox and NextCloud',
    formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('dropbox_root', nargs='?', default='/',
                    help='Folder name in your Dropbox')
parser.add_argument('nextcloud_root', nargs='?', default='/',
                    help='Folder name in your NextCloud')
parser.add_argument('--nextcloud-server', required=True,
                    help='Your NextCloud server root (required)')
parser.add_argument('--nextcloud-user',  required=True,
                    help='NextCloud user used for synchronization (required)')
parser.add_argument('--nextcloud-password', required=True,
                    help='Password of your NextCloud user (required)')
parser.add_argument('--dropbox-token', required=True,
                    help='Access token (required)'
                    '(see https://www.dropbox.com/developers/apps)')
parser.add_argument("--ignore-folder", nargs="+", type=str,
                    help='Ignore folders')
parser.add_argument("--create-state", action='store_true',
                    help='Only create the state file (overwrites if already existent)')
parser.add_argument("--apply-state", action='store_true',
                    help='Copy over non-existent files in both directions')
parser.add_argument('--simulate', action='store_true',
                    help='Simulate the synchronization')
parser.add_argument('--verbose', action='store_true',
                    help='Verbose output of events')
parser.add_argument('--version', '-v', action='version', 
                    version=LICENSE,
                    help='Show version of application')
parser.add_argument('--license', '-l', action='version',
                    version=LICENSE,
                    help='Show license of application')


# application

def main():
    global SIMULATE
    global VERBOSE
    global DROPBOX_SYNC_ROOT
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    global NEXTCLOUD_SYNC_ROOT_TEXT

    args = parser.parse_args()

    ignore_folders = []
    if args.ignore_folder != None:
        ignore_folders = args.ignore_folder

    if args.create_state and args.simulate:
        print('Warning: Creation of state file cannot be simulated. This might do nothing.')
    
    NEXTCLOUD_USER = args.nextcloud_user
    NEXTCLOUD_SYNC_ROOT = args.nextcloud_root
    NEXTCLOUD_SYNC_ROOT_TEXT = '/remote.php/dav/files/' + NEXTCLOUD_USER + NEXTCLOUD_SYNC_ROOT
    DROPBOX_SYNC_ROOT = args.dropbox_root

    SIMULATE = args.simulate
    VERBOSE = args.verbose

    dbx = dropbox.Dropbox(args.dropbox_token)
    nxc = nextcloud.NextCloud(args.nextcloud_server, NEXTCLOUD_USER, args.nextcloud_password)

    if args.create_state or args.apply_state:
        if args.create_state and not SIMULATE:
            state_curr = get_state(dbx, nxc)
            write_state(state_curr)
        if args.apply_state:
            state_curr = read_state()
            apply_state(state_curr, dbx, nxc, ignore_folders)
            state_curr = get_state(dbx, nxc)
            write_state(state_curr)
    else:
        state_prev = read_state()
        state_curr = get_state(dbx, nxc)
        sync_state(state_prev, state_curr, dbx, nxc, ignore_folders)
        state_curr = get_state(dbx, nxc)
        write_state(state_curr)


# helper functions

def get_empty_state_entry(_name, _path):
    return { 
        'dbx': {
            'existent': False,
            'time': None
        }, 
        'nxc': {
            'existent': False,
            'time': None
        }, 
        'name': _name,
        'path': _path
    }


def fill_state_dbx(_dbx, _state):
    global DROPBOX_SYNC_ROOT
    list_folder_result = _dbx.files_list_folder(DROPBOX_SYNC_ROOT, recursive=True, include_non_downloadable_files=False)
    while list_folder_result.has_more:
        list_folder_result = _dbx.files_list_folder_continue(list_folder_result.cursor)
        for entry in list_folder_result.entries:
            key = entry.path_lower[len(DROPBOX_SYNC_ROOT):]
            if isinstance(entry, dropbox.files.FolderMetadata):
                key = key + '/'
                if not key in _state:
                    _state[key] = get_empty_state_entry(entry.name, (entry.path_display + '/')[len(DROPBOX_SYNC_ROOT):])
                _state[key]['dbx'] = {
                    'existent': True,
                    'time': TIME_NOW_STR
                }
            elif isinstance(entry, dropbox.files.FileMetadata):
                if not key in _state:
                    _state[key] = get_empty_state_entry(entry.name, entry.path_display[len(DROPBOX_SYNC_ROOT):])
                _state[key]['dbx'] = {
                    'existent': True,
                    'time': entry.client_modified.strftime("%Y%m%d%H%M%S")
                }

def fill_state_nxc(_nxc, _state):
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    global NEXTCLOUD_SYNC_ROOT_TEXT
    list_folder_result = _nxc.list_folders(NEXTCLOUD_USER, NEXTCLOUD_SYNC_ROOT, depth=128)
    if list_folder_result.is_ok:
        for entry in list_folder_result.data:
            path_display = urllib.parse.unquote(entry['href'])[len(NEXTCLOUD_SYNC_ROOT_TEXT):]
            name = path_display.rstrip('/')
            name = name[name.rfind('/')+1:]
            key = path_display.lower()
            if key == '':
                continue
            if not key in _state:
                _state[key] = get_empty_state_entry(name, path_display)
            _state[key]['nxc'] = {
                'existent': True,
                'time': datetime
                    .strptime(entry['last_modified'], "%a, %d %b %Y %H:%M:%S %Z")
                    .strftime("%Y%m%d%H%M%S") 
            }
            
def get_state(_dbx, _nxc):
    state = {}
    fill_state_dbx(_dbx, state)
    fill_state_nxc(_nxc, state)
    return state

def normalize_states(_state_a, _state_b):
    # Make sure both databases have same keys.
    for key,value in _state_a.items():
        if not key in _state_b:
            _state_b[key] = get_empty_state_entry(value['name'], value['path'])
    for key,value in _state_b.items():
        if not key in _state_a:
            _state_a[key] = get_empty_state_entry(value['name'], value['path'])

def is_folder(_path):
    return _path.endswith('/')

def has_changed(_path_lower, _state_prev, _state_curr, _cloud_type):
    if _state_prev[_path_lower][_cloud_type]['existent'] != _state_curr[_path_lower][_cloud_type]['existent']:
        return True
    elif is_folder(_path_lower):
        return False
    else:
        return _state_prev[_path_lower][_cloud_type]['time'] != _state_curr[_path_lower][_cloud_type]['time']

def has_been_created(_path_lower, _state_prev, _state_curr, _cloud_type):
    return not _state_prev[_path_lower][_cloud_type]['existent'] and _state_curr[_path_lower][_cloud_type]['existent']

def has_been_changed(_path_lower, _state_prev, _state_curr, _cloud_type):
    if is_folder(_path_lower):
        return False
    return _state_prev[_path_lower][_cloud_type]['time'] != _state_curr[_path_lower][_cloud_type]['time']

def has_been_deleted(_path_lower, _state_prev, _state_curr, _cloud_type):
    return _state_prev[_path_lower][_cloud_type]['existent'] and not _state_curr[_path_lower][_cloud_type]['existent']

def create_folder_dbx(_dbx, _path):
    global SIMULATE
    global VERBOSE
    global DROPBOX_SYNC_ROOT
    _path = _path.rstrip('/')
    if SIMULATE or VERBOSE:
        print('create_folder_dbx(' + DROPBOX_SYNC_ROOT + _path + ')')
    if not SIMULATE:
        _dbx.files_create_folder(DROPBOX_SYNC_ROOT + _path)

def create_folder_nxc(_nxc, _path):
    global SIMULATE
    global VERBOSE
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    if SIMULATE or VERBOSE:
        print('create_folder_nxc(' + NEXTCLOUD_SYNC_ROOT + _path + ')')
    if not SIMULATE:
        _nxc.create_folder(NEXTCLOUD_USER, NEXTCLOUD_SYNC_ROOT + _path)

def move_nxc(_nxc, _path, _destination_path):
    global SIMULATE
    global VERBOSE
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    if SIMULATE or VERBOSE:
        print('move_nxc(' + NEXTCLOUD_SYNC_ROOT + _path + ', ' + NEXTCLOUD_SYNC_ROOT + _destination_path + ')')
    if not SIMULATE:
        _nxc.move_path(NEXTCLOUD_USER, NEXTCLOUD_SYNC_ROOT + _path, NEXTCLOUD_SYNC_ROOT + _destination_path, overwrite=True)

def download_file_dbx(_dbx, _path):
    global SIMULATE
    global VERBOSE
    global DROPBOX_SYNC_ROOT
    filename = _path[_path.rfind('/')+1:]
    if SIMULATE or VERBOSE:
        print('download_file_dbx(' + DROPBOX_SYNC_ROOT + _path + '), [also exeuted if --simulate]')
    _dbx.files_download_to_file(filename, DROPBOX_SYNC_ROOT + _path)
    return filename

def download_file_nxc(_nxc, _path):
    global SIMULATE
    global VERBOSE
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    filename = _path[_path.rfind('/')+1:]
    if SIMULATE or VERBOSE:
        print('download_file_nxc(' + NEXTCLOUD_SYNC_ROOT + _path + '), [also exeuted if --simulate]')
    _nxc.download_file(NEXTCLOUD_USER, NEXTCLOUD_SYNC_ROOT + _path)
    return filename

def get_hash(_local_filepath):
    with open(full_path, 'rb') as file:
        return hashlib.sha1(file.read()).hexdigest()

def get_hash_dbx(_dbx, _path):
    global SIMULATE
    global VERBOSE
    tmp_filepath = download_file_dbx(_dbx, _path)
    file_hash = get_hash(_local_filepath)
    os.remove(tmp_filepath)
    if SIMULATE or VERBOSE:
        print('get_hash_dbx(' + _path + ') -> ' + file_hash)
    return file_hash

def get_hash_nxc(_nxc, _path):
    global SIMULATE
    global VERBOSE
    tmp_filepath = download_file_nxc(_nxc, _path)
    file_hash = get_hash(_local_filepath)
    os.remove(tmp_filepath)
    if SIMULATE or VERBOSE:
        print('get_hash_nxc(' + _path + ') -> ' + file_hash)
    return file_hash

def upload_file_dbx(_dbx, _path, _local_filepath):
    global SIMULATE
    global VERBOSE
    global DROPBOX_SYNC_ROOT
    if SIMULATE or VERBOSE:
        print('upload_file_dbx(' + DROPBOX_SYNC_ROOT + _path + ', ' + _local_filepath + ')')
    if not SIMULATE:
        with open(_local_filepath, "rb") as file:
            _dbx.files_upload(file.read(), DROPBOX_SYNC_ROOT + _path, dropbox.files.WriteMode.overwrite)

def upload_file_nxc(_nxc, _path, _local_filepath):
    global SIMULATE
    global VERBOSE
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    if SIMULATE or VERBOSE:
        print('upload_file_nxc(' + NEXTCLOUD_SYNC_ROOT + _path + ', ' + _local_filepath + ')')
    if not SIMULATE:
        _nxc.upload_file(NEXTCLOUD_USER, _local_filepath, NEXTCLOUD_SYNC_ROOT + _path)

def delete_on_dbx(_dbx, _path):
    global SIMULATE
    global VERBOSE
    global DROPBOX_SYNC_ROOT
    _path = _path.rstrip('/')
    if SIMULATE or VERBOSE:
        print('delete_on_dbx(' + DROPBOX_SYNC_ROOT + _path + ')')
    if not SIMULATE:
        _dbx.files_delete(DROPBOX_SYNC_ROOT + _path)

def delete_on_nxc(_nxc, _path):
    global SIMULATE
    global VERBOSE
    global NEXTCLOUD_USER
    global NEXTCLOUD_SYNC_ROOT
    if SIMULATE or VERBOSE:
        print('delete_on_nxc(' + NEXTCLOUD_SYNC_ROOT + _path + ')')
    if not SIMULATE:
        _nxc.delete_path(NEXTCLOUD_USER, NEXTCLOUD_SYNC_ROOT + _path)

def copy_to_dbx(_dbx, _nxc, _path):
    global SIMULATE
    global VERBOSE
    if SIMULATE or VERBOSE:
        print('copy_to_dbx(' + _path + ')')
    if is_folder(_path):
        create_folder_dbx(_dbx, _path)
    else:
        tmp_filepath = download_file_nxc(_nxc, _path)
        upload_file_dbx(_dbx, _path, tmp_filepath)
        os.remove(tmp_filepath)

def copy_to_nxc(_dbx, _nxc, _path):
    global SIMULATE
    global VERBOSE
    if SIMULATE or VERBOSE:
        print('copy_to_nxc(' + _path + ')')
    if is_folder(_path):
        create_folder_nxc(_nxc, _path)
    else:
        tmp_filepath = download_file_dbx(_dbx, _path)
        upload_file_nxc(_nxc, _path, tmp_filepath)
        os.remove(tmp_filepath)

def write_state(_state):
    with open('state.json', 'w') as outfile:
        json.dump(_state, outfile, indent=4)

def read_state():
    with open('state.json') as infile:
        return json.loads(infile.read())

def apply_state(_state, _dbx, _nxc, _ignore_folders):
    for key,value in _state.items():
        existent_in_dbx = value['dbx']['existent']
        existent_in_nxc = value['nxc']['existent']
        ignore = False
        if key == '' or key == '/':
            ignore = True
        elif existent_in_dbx  == existent_in_nxc:
            ignore = True
        else:
            for ignore_folder in _ignore_folders:
                if key.startswith(ignore_folder):
                    ignore = True
        if ignore:
            continue
        if not existent_in_dbx:
            copy_to_dbx(_dbx, _nxc, value['path'])
        elif not existent_in_nxc:
            copy_to_nxc(_dbx, _nxc, value['path'])

def sync_state(_state_prev, _state_curr, _dbx, _nxc, _ignore_folders):

    normalize_states(_state_prev, _state_curr)

    for key,value in _state_curr.items():

        ignore = False
        if key == '' or key == '/':
            ignore = True
        else:
            for ignore_folder in _ignore_folders:
                if key.startswith(ignore_folder):
                    ignore = True
        if ignore:
            continue

        path = value['path']
        has_changed_dbx = has_changed(key, _state_prev, _state_curr, 'dbx')
        has_changed_nxc = has_changed(key, _state_prev, _state_curr, 'nxc')
        has_been_created_dbx = has_been_created(key, _state_prev, _state_curr, 'dbx')
        has_been_created_nxc = has_been_created(key, _state_prev, _state_curr, 'nxc')
        has_been_changed_dbx = has_been_changed(key, _state_prev, _state_curr, 'dbx')
        has_been_changed_nxc = has_been_changed(key, _state_prev, _state_curr, 'nxc')
        has_been_deleted_dbx = has_been_deleted(key, _state_prev, _state_curr, 'dbx')
        has_been_deleted_nxc = has_been_deleted(key, _state_prev, _state_curr, 'nxc')
        
        if (SIMULATE or VERBOSE) and (has_changed_dbx or has_changed_nxc):
            print('===')
            print(path)
            print('has_changed_dbx: ' + str(has_changed_dbx))
            print('has_changed_nxc: ' + str(has_changed_nxc))
            print('has_been_created_dbx: ' + str(has_been_created_dbx))
            print('has_been_created_nxc: ' + str(has_been_created_nxc))
            print('has_been_changed_dbx: ' + str(has_been_changed_dbx))
            print('has_been_changed_nxc: ' + str(has_been_changed_nxc))
            print('has_been_deleted_dbx: ' + str(has_been_deleted_dbx))
            print('has_been_deleted_nxc: ' + str(has_been_deleted_nxc))
            print('---')
        
        if has_changed_dbx and not has_changed_nxc:
            if has_been_created_dbx:
                copy_to_nxc(_dbx, _nxc, path)
            elif has_been_deleted_dbx:
                delete_on_nxc(_nxc, path)
            elif has_been_changed_dbx:
                copy_to_nxc(_dbx, _nxc, path)
        elif not has_changed_dbx and has_changed_nxc:
            if has_been_created_nxc:
                copy_to_dbx(_dbx, _nxc, path)
            elif has_been_deleted_nxc:
                delete_on_dbx(_dbx, path)
            elif has_been_changed_nxc:
                copy_to_dbx(_dbx, _nxc, path)
        elif has_changed_dbx and has_changed_nxc:
            if has_been_created_dbx and has_been_created_nxc:
                if get_hash_dbx(_dbx, path) != get_hash_nxc(_nxc, path):
                    nxc_path = path + ' (NextCloud - ' + value['nxc']['time'] + ')'
                    move_nxc(_nxc, path, nxc_path)
                    copy_to_nxc(_dbx, _nxc, path)
                    copy_to_dbx(_dbx, _nxc, nxc_path)
            elif has_been_changed_dbx and has_been_deleted_nxc:
                copy_to_nxc(_dbx, _nxc, path)
            elif has_been_deleted_dbx and has_been_changed_nxc:
                copy_to_dbx(_dbx, _nxc, path)
            elif has_been_changed_dbx and has_been_changed_nxc:
                if get_hash_dbx(_dbx, path) != get_hash_nxc(_nxc, path):
                    nxc_path = path + ' (NextCloud - ' + value['nxc']['time'] + ')'
                    move_nxc(_nxc, path, nxc_path)
                    copy_to_nxc(_dbx, _nxc, path)
                    copy_to_dbx(_dbx, _nxc, nxc_path)

if __name__ == '__main__':
    main()
