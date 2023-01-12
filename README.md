# pmpsdb_client

## Overview
Client-side application for the PMPS database

This is a cli/gui application and library for managing the deployment and
inspection of PMPS database files on production PLCs at LCLS.
It provides tools to make deployment and verification of deployment seamless and easy.

## Usage
Once installed, this application can be invoked via `pmpsdb`. For example, here is
the current output of `pmpsdb --help`:

```
usage: pmpsdb [-h] [--version] [--verbose] {gui,plc} ...

PMPS database deployment helpers

positional arguments:
  {gui,plc}
    gui          Open the pmpsdb gui.
    plc          Read db from or write db to the plc harddrives.

optional arguments:
  -h, --help     show this help message and exit
  --version      Show version information and exit
  --verbose, -v  Show tracebacks and debug statements
```

From a git clone, you can invoke the same script without needing to install the
package. This is done from the root directory here by calling
`python -m pmpsdb --help`, for example.

This package can be installed using recent versions of `pip` that support
the `pyproject.toml` format. To install, you can either clone this repo and run
the following from the root directory: `pip install .`, or you can install
directly from github via:
`pip install 'pmpsdb_client @ git+https://github.com/pcdshub/pmpsdb_client@v1.0.0'`
for example, to install version v1.0.0.

## PLC Configuration
The PLC must have the following configuration:

- ftp enabled, with either the default logins or anonymous uploads enabled
- firewall TCP ports 20-21 allowed

These are both editable in the CX Configuration Tool.
Enabling the ftp server will require a PLC restart, updating the firewall will not.
