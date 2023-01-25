"""
Module to define the command-line interface for pmpsdb database management.

Once installed, this can be invoked simply by using the ``pmpsdb`` command.
It can also be run via ``python -m pmpsdb`` from the repository root if you
have not or cannot install it.
"""
import argparse
import logging
from pathlib import Path
from typing import Optional

from .export_data import set_export_dir

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
            'If no configurations are picked, tst is the default.'
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
            'This will include the lfe config and any relevant hutch configs.'
        )
    )
    gui.add_argument(
        '--lfe',
        action='store_true',
        help='Load the included lfe PLCs configuration file.',
    )
    gui.add_argument(
        '--kfe-all',
        action='store_true',
        help=(
            'Load all kfe-side non-test PLC configuration files. '
            'This will include the kfe config and any relevant hutch configs.'
        )
    )
    gui.add_argument(
        '--kfe',
        action='store_true',
        help='Load the included kfe PLCs configuration file.',
    )
    gui.add_argument(
        '--tmo',
        action='store_true',
        help='Load the included kfe and tmo PLCs configuration files.',
    )
    gui.add_argument(
        '--rix',
        action='store_true',
        help='Load the included kfe and rix PLCs configuration files.',
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
    if args.export_dir:
        set_export_dir(args.export_dir)
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

    configs = args.config or []
    if args.tst:
        configs.append(get_included_config('tst'))
    if any((args.lfe, args.lfe_all, args.all_prod)):
        configs.append(get_included_config('lfe'))
    if any((args.kfe, args.tmo, args.rix, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('kfe'))
    if any((args.tmo, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('tmo'))
    if any((args.rix, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('rix'))
    app = QApplication([])
    gui = PMPSManagerGui(configs=configs)
    gui.show()
    return app.exec()


def get_included_config(name: str) -> str:
    return str(Path(__file__).parent / f'pmpsdb_{name}.yml')


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
