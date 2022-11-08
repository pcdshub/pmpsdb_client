import argparse
import logging

from qtpy.QtWidgets import QApplication

from .ftp_data import (list_file_info, upload_filename, download_file_text,
                       compare_file)
from .gui import PMPSManagerGui


logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='pmpsdb',
        description='PMPS database deployment helpers',
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show tracebacks and debug statements',
    )
    subparsers = parser.add_subparsers(dest='subparser')
    gui = subparsers.add_parser(
        'gui',
        help='Open the pmpsdb gui.',
    )
    gui.add_argument(
        'hostnames',
        nargs='*',
        help=(
            'List the PLCs to include in the gui. '
            'If omitted, defaults to all production PLCs.'
        ),
    )
    plc = subparsers.add_parser(
        'plc',
        help='Read db from or write db to the plc harddrives.',
    )
    plc.add_argument('hostname', help='The plc to connect to.')
    plc.add_argument(
        '-l', '--list',
        action='store_true',
        help='List the plc pmps db files and their info.',
    )
    plc.add_argument(
        '-d', '--download',
        action='store',
        help='PLC filename to download to stdout.',
    )
    plc.add_argument(
        '-u', '--upload',
        action='store',
        help='Local filename to upload to the PLC.',
    )
    plc.add_argument(
        '-c', '--compare',
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
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    if args.subparser == 'gui':
        return gui(args)
    if args.subparser == 'plc':
        return plc(args)


def gui(args: argparse.Namespace):
    app = QApplication([])
    gui = PMPSManagerGui(plc_hostnames=args.hostnames)
    gui.show()
    return app.exec()


def plc(args: argparse.Namespace):
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

