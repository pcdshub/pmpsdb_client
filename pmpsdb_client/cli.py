"""
Module to define the command-line interface for pmpsdb database management.

Once installed, this can be invoked simply by using the ``pmpsdb`` command.
It can also be run via ``python -m pmpsdb`` from the repository root if you
have not or cannot install it.
"""
import argparse
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def entrypoint() -> Optional[int]:
    """
    This is the function called when you run ``pmpsdb``
    """
    return main(create_parser().parse_args())


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
    subparsers = parser.add_subparsers(dest='subparser')
    gui = subparsers.add_parser(
        'gui',
        help='Open the pmpsdb gui.',
    )
    gui.add_argument(
        '--config', '--cfg',
        default=None,
        help=(
            'Configuration file that maps hostnames to IOC PREFIX'
        ),
    )
    plc = subparsers.add_parser(
        'plc',
        help='Read db from or write db to the plc harddrives.',
    )
    plc.add_argument('hostname', help='The plc to connect to.')
    plc.add_argument(
        '--list', '-l',
        action='store_true',
        help='List the plc pmps db files and their info.',
    )
    plc.add_argument(
        '--download', '-d',
        action='store',
        help='PLC filename to download to stdout.',
    )
    plc.add_argument(
        '--upload', '-u',
        action='store',
        help='Local filename to upload to the PLC.',
    )
    plc.add_argument(
        '--compare', '-c',
        action='store',
        help='Filename on both PLC and local to compare.',
    )
    return parser


def main(args: argparse.Namespace) -> Optional[int]:
    """
    Given some arguments, run the command-line program.

    This outer function exists only to handle uncaught exceptions.
    """
    try:
        return _main(args)
    except Exception as exc:
        if args.verbose:
            raise
        print(exc)
        return 1


def _main(args: argparse.Namespace) -> Optional[int]:
    """
    Given some arguments, run the command-line program.

    This inner function does some setup and then defers to the more specific
    helper function as needed.
    """
    if args.version:
        from .version import version
        print(version)
        return
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    if args.subparser == 'gui':
        return gui(args)
    if args.subparser == 'plc':
        return plc(args)


def gui(args: argparse.Namespace) -> int:
    """
    Run the gui application.

    This shows a PLC database diagnostics and allows us to deploy database
    updates to the PLCs.
    """
    # Late import for startup speed
    from qtpy.QtWidgets import QApplication

    from .gui import PMPSManagerGui

    app = QApplication([])
    gui = PMPSManagerGui(config=args.config)
    gui.show()
    return app.exec()


def plc(args: argparse.Namespace) -> None:
    """
    Run one or more file operations on a plc.
    """
    # Late import for startup speed
    from .ftp_data import (compare_file, download_file_text, list_file_info,
                           upload_filename)
    hostname = args.hostname
    if args.download:
        print(download_file_text(hostname=hostname, filename=args.download))
    if args.upload:
        logger.info(f'Uploading {args.upload}')
        upload_filename(hostname=hostname, filename=args.upload)
    if args.compare:
        ok = compare_file(hostname=hostname, filename=args.compare)
        if ok:
            logger.info(f'{args.compare} is the same locally and on the PLC')
        else:
            logger.info(f'{args.compare} is different on the PLC!')
    if args.list:
        infos = list_file_info(hostname=hostname)
        for data in infos:
            print(
                f'{data.filename} uploaded at {data.create_time.ctime()} '
                f'({data.size} bytes)'
            )
        if not infos:
            logger.warning('No files found')
