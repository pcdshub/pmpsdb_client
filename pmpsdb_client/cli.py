import argparse
import logging

logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
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
            'Configuration file that maps hostnames to IOC PREFIX',
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


def main(args: argparse.Namespace):
    try:
        _main(args)
    except Exception as exc:
        if args.verbose:
            raise
        print(exc)


def _main(args: argparse.Namespace):
    if args.version:
        try:
            # Installed package
            from ._version import __version__ as version
        except ImportError:
            # Git checkout (late import for startup speed)
            from setuptools_scm import get_version
            version = get_version(root="..", relative_to=__file__)
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


def gui(args: argparse.Namespace):
    # Late import for startup speed
    from qtpy.QtWidgets import QApplication

    from .gui import PMPSManagerGui
    app = QApplication([])
    gui = PMPSManagerGui(config=args.config)
    gui.show()
    return app.exec()


def plc(args: argparse.Namespace):
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
