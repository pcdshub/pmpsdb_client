import argparse

from .ftp_data import (list_file_info, upload_filename, download_file_text,
                       compare_file)
from .gui import PMPSManagerGui


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='pmps_manager',
        description='Manage pmps database deployment.',
    )
    parser.add_argument('hostname', help='The plc to connect to.')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show tracebacks',
    )
    parser.add_argument(
        '-l', '--list',
        action='store_true',
        help='List the plc pmps db files and their info.',
    )
    parser.add_argument(
        '-d', '--download',
        action='store',
        help='PLC filename to download to stdout.',
    )
    parser.add_argument(
        '-u', '--upload',
        action='store',
        help='Local filename to upload to the PLC.',
    )
    parser.add_argument(
        '-c', '--compare',
        action='store',
        help='Filename on both PLC and local to compare.',
    )
    parser.add_argument(
        '-g', '--gui',
        action='store_true',
        help='Ignore other options and open the gui.'
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
    if args.gui:
        return PMPSManagerGui(plc_hostnames=['plc-tst-motion'])
    hostname = args.hostname
    if args.download:
        print(download_file_text(hostname=hostname, filename=args.download))
    if args.upload:
        print(f'Uploading {args.upload}')
        upload_filename(hostname=hostname, filename=args.upload)
    if args.compare:
        ok = compare_file(hostname=hostname, filename=args.compare)
        if ok:
            print(f'{args.compare} is the same locally and on the PLC')
        else:
            print(f'{args.compare} is different on the PLC!')
    if args.list:
        infos = list_file_info(hostname=hostname)
        for data in infos:
            print(
                f'{data.filename} uploaded at {data.create_time.ctime()} '
                f'({data.size} bytes)'
            )
        if not infos:
            print('No files found')
