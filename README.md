# sync-dbx-nxc

Script that synchronizes Dropbox and Nextcloud.  
Compatible with Python 3.6+

## Usage

The script keeps track of changes in both cloud-systems with the help
of a local state file. This should be created once by starting the
script with the *--create-state* command-line-option.

It should also made sure that both clouds already have the same files 
on it once, by calling with the *--apply-state* command-line-option,
which copies over missing files in both direction.

Both steps can be done in one go.

```
python3 sync-dbx-nxc.py <drobox_root> <nextcloud_root> --nextcloud-server <nextcloud-server> --nextcloud-user <nextcloud-user> --nextcloud-password <nextcloud-password> --dropbox-token <dropbox-token> --create-state --apply-state
```

Afterwards every call of the script uses the state file to synchronize
and automatically updates it afterwards.

## Command Line Options

```
usage: sync-dbx-nxc.py [-h] --nextcloud-server NEXTCLOUD_SERVER
                                 --nextcloud-user NEXTCLOUD_USER
                                 --nextcloud-password NEXTCLOUD_PASSWORD
                                 --dropbox-token DROPBOX_TOKEN
                                 [--ignore-folder IGNORE_FOLDER [IGNORE_FOLDER ...]]
                                 [--create-state] [--apply-state] [--simulate]
                                 [--verbose] [--version] [--license]
                                 [dropbox_root] [nextcloud_root]

sync-dbx-nxc - A script that synchronizes Dropbox and NextCloud

positional arguments:
  dropbox_root          Folder name in your Dropbox
  nextcloud_root        Folder name in your NextCloud

optional arguments:
  -h, --help            show this help message and exit
  --nextcloud-server NEXTCLOUD_SERVER
                        Your NextCloud server root (required)
  --nextcloud-user NEXTCLOUD_USER
                        NextCloud user used for synchronization (required)
  --nextcloud-password NEXTCLOUD_PASSWORD
                        Password of your NextCloud user (required)
  --dropbox-token DROPBOX_TOKEN
                        Access token (required)
                        (see https://www.dropbox.com/developers/apps)
  --ignore-folder IGNORE_FOLDER [IGNORE_FOLDER ...]
                        Ignore folders
  --create-state        Only create the state file (overwrites if already
                        existent)
  --apply-state         Copy over non-existent files in both directions
  --simulate            Simulate the synchronization
  --verbose             Verbose output of events
  --version, -v         Show version of application
  --license, -l         Show license of application
```

## Dependencies

This script depends on
- Python SDK for Dropbox API v2: https://github.com/dropbox/dropbox-sdk-python
- NextCloud OCS API for Python: https://github.com/EnterpriseyIntranet/nextcloud-API

They're also linked in the dependencies-folder. Make sure to correctly setup them for your python-installation.

## Nice Additions

This is in the state of *working* and *usable*. There would still be certain additions to make it somehow *beautiful*.
- Also use OAuth for NextCloud (Currently not supported by *NextCloud OCS API for Python*)
- Add Timestamp to logs / more log-file kind of logging.
- Catch certain exceptions, log errors and continue if possible.
- Unit-Tests and better code-documentation, to simlify maintenance and modifications by others
- *If you can think of further improvements, just let me know!*

## License

sync-dbx-nxc - A script that synchronizes Dropbox and NextCloud.

Copyright (C) 2019  Philipp M. Wittershagen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
