# pmpsdb_client

## Overview
This is a gui and cli application for managing the deployment and inspection of
PMPS database files on production PLCs at LCLS.
It provides tools to make deployment and verification of deployment seamless and easy.


## Usage
Once installed, this application can be invoked via `pmpsdb`. For example, here is
the current output of `pmpsdb --help`:

```
usage: pmpsdb [-h] [--version] [--verbose] [--export-dir EXPORT_DIR] {gui,list-files,upload-to,download-from,compare,reload} ...

PMPS database deployment helpers

positional arguments:
  {gui,list-files,upload-to,download-from,compare,reload}
    gui                 Open the pmpsdb gui.
    list-files          Show all files uploaded to a PLC.
    upload-to           Upload a database export file to a PLC.
    download-from       Download a database file previously exported to a PLC.
    compare             Compare files beteween the local exports and the PLC.
    reload              Force the PLC to re-read the database export while running.

optional arguments:
  -h, --help            show this help message and exit
  --version             Show version information and exit
  --verbose, -v         Show tracebacks and debug statements
  --export-dir EXPORT_DIR, -e EXPORT_DIR
                        The directory that contains database file exports.
```

From a git clone, you can invoke the same script without needing to install the
package. This is done from the root directory here by calling
`python -m pmpsdb --help`, for example.

This application will not work unless you have access to the LCLS controls networks.
It is designed to run on an endstation's operator consoles.

The most common usage will be to open the gui from an operator console as simply `pmpsdb gui`.


## Installation
This package can be installed using recent versions of `pip` that support
the `pyproject.toml` format.

To install, you can choose one of the following:
- `pip install pmpsdb_client` to install from pypi
- clone this repo, check out the desired tag, and run the following from the root directory: `pip install .`
- install directly from github via: `pip install 'pmpsdb_client @ git+https://github.com/pcdshub/pmpsdb_client@v1.1.2'` for example, to install version v1.1.2.


## PLC Configuration
The PLC must have the following configuration:

- ftp enabled, with either the default logins or anonymous uploads enabled
- firewall TCP ports 20-21 allowed

These are both editable in the CX Configuration Tool.
Enabling the ftp server will require a PLC restart, updating the firewall will not.
