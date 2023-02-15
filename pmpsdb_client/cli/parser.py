import argparse


def create_parser() -> argparse.ArgumentParser:
    """
    Create the parser used to process command-line input.
    """
    parser = argparse.ArgumentParser(
        prog='pmpsdb',
        description='PMPS database deployment helpers',
    )
    parser.add_argument(
        '--version',
        action='store_true',
        help='Show version information and exit'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show tracebacks and debug statements',
    )
    parser.add_argument(
        '--export-dir', '-e',
        action='store',
        help='The directory that contains database file exports.',
    )

    subparsers = parser.add_subparsers(dest='subparser')

    gui = subparsers.add_parser(
        'gui',
        help='Open the pmpsdb gui.',
    )
    gui.add_argument(
        '--config', '--cfg',
        action='append',
        help=(
            'Add a configuration file that maps hostnames to IOC PREFIX.'
        ),
    )
    gui.add_argument(
        '--tst',
        action='store_true',
        help=(
            'Load the included test PLCs configuration file. '
            'If no configurations are picked, and we are on a test machine, '
            'tst is the default.'
        ),
    )
    gui.add_argument(
        '--all-prod', '--all',
        action='store_true',
        help='Load all included non-test PLC configuration files.'
    )
    gui.add_argument(
        '--lfe-all',
        action='store_true',
        help=(
            'Load all lfe-side non-test PLC configuration files. '
            'This will include the lfe config and any relevant hutch configs. '
        )
    )
    gui.add_argument(
        '--lfe',
        action='store_true',
        help=(
            'Load the included lfe PLCs configuration file. '
            'This is the default if we are on lfe-console. '
        ),
    )
    gui.add_argument(
        '--kfe-all',
        action='store_true',
        help=(
            'Load all kfe-side non-test PLC configuration files. '
            'This will include the kfe config and any relevant hutch configs. '
        )
    )
    gui.add_argument(
        '--kfe',
        action='store_true',
        help=(
            'Load the included kfe PLCs configuration file. '
            'This is the default if we are on kfe-console. '
        ),
    )
    gui.add_argument(
        '--tmo',
        action='store_true',
        help=(
            'Load the included kfe and tmo PLCs configuration files. '
            'This is the default if we are on a tmo operator console.'
        ),
    )
    gui.add_argument(
        '--rix',
        action='store_true',
        help=(
            'Load the included kfe and rix PLCs configuration files. '
            'This is the default if we are on a rix operator console.'
        ),
    )

    list_files = subparsers.add_parser(
        'list-files',
        help='Show all files uploaded to a PLC.',
    )
    list_files.add_argument(
        'hostname',
        help='PLC hostname to check.'
    )

    upload = subparsers.add_parser(
        'upload-to',
        help='Upload a database export file to a PLC.'
    )
    upload.add_argument(
        'hostname',
        help='PLC hostname to upload to.'
    )
    upload.add_argument(
        '--local-file',
        help=(
            'Full path to the local file you want to upload. '
            'If omitted, we will upload the latest database export.'
        ),
    )
    upload.add_argument(
        '--plc-filename',
        help=(
            'Name of the file on the PLC end. '
            'If omitted, this will be the standard export name '
            'if we can figure it out from the local filename, '
            'or the default name the PLC loads the database from otherwise.'
        ),
    )

    download = subparsers.add_parser(
        'download-from',
        help='Download a database file previously exported to a PLC.'
    )
    download.add_argument(
        'hostname',
        help='PLC hostname to download from.'
    )
    download.add_argument(
        '--plc-filename',
        help=(
            'Name of the file on the PLC end. '
            'If omitted, this will be the default name the PLC loads the database from.'
        ),
    )
    download.add_argument(
        '--local-file',
        help=(
            'Full path to save locally. If omitted, download to stdout.'
        ),
    )

    compare = subparsers.add_parser(
        'compare',
        help='Compare files beteween the local exports and the PLC.'
    )
    compare.add_argument(
        'hostname',
        help='PLC hostname to compare with.'
    )
    compare.add_argument(
        '--local-file',
        help=(
            'Full path to the local file you want to compare. '
            'If omitted, we will use the latest database export.'
        ),
    )
    compare.add_argument(
        '--plc-filename',
        help=(
            'Name of the file on the PLC end. '
            'If omitted, this will be the standard export name '
            'if we can figure it out from the local filename, '
            'or the default name the PLC loads the database from otherwise.'
        ),
    )

    reload = subparsers.add_parser(
        'reload',
        help='Force the PLC to re-read the database export while running.'
    )
    reload.add_argument(
        'hostname',
        help='PLC hostname to reload parameters for.'
    )
    reload.add_argument(
        '--no-wait',
        action='store_true',
        help='Do not wait for confirmation',
    )

    return parser
