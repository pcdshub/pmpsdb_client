"""
CLI entry points to the various tools for moving files around.
"""
import argparse
import logging
import os.path
from typing import Optional

from ..export_data import ExportFile, get_latest_exported_files
from ..plc_data import (compare_file, download_file_text, list_file_info,
                        upload_filename)

logger = logging.getLogger(__name__)


def cli_list_files(args: argparse.Namespace) -> int:
    """Show all files uploaded to a PLC."""
    return _list_files(hostname=args.hostname)


def _list_files(hostname: str) -> int:
    infos = list_file_info(hostname=hostname)
    for data in infos:
        print(
            f'{data.filename} uploaded at {data.last_changed.ctime()} '
            f'({data.size} bytes)'
        )
    if not infos:
        logger.warning('No files found')
    return 0


def cli_upload_file(args: argparse.Namespace) -> int:
    return _upload_file(
        hostname=args.hostname,
        local_file=args.local_file,
        plc_filename=args.plc_filename,
    )


def _upload_file(
    hostname: str,
    local_file: Optional[str] = None,
    plc_filename: Optional[str] = None,
) -> int:
    """
    Upload a database export file to a PLC.

    Parameters
    ----------
    hostname : str
        PLC hostname to upload to
    local_file : str, optional
        Full path to the local file you want to upload.
        If omitted, we will upload the latest database export.
    plc_filename : str, optional
        Name of the file on the PLC end.
        If omitted, this will be the standard export name
        if we can figure it out from the local filename,
        or the default name the PLC loads the database from otherwise.
    """
    local_file, plc_filename = default_upload_naming(
        hostname=hostname,
        local_file=local_file,
        plc_filename=plc_filename,
    )
    logger.info('Uploading %s to %s as %s', local_file, hostname, plc_filename)
    upload_filename(
        hostname=hostname,
        filename=local_file,
        dest_filename=plc_filename,
    )
    logger.info('Checking PLC files')
    return _list_files(hostname=hostname)


def cli_download_file(args: argparse.Namespace) -> int:
    return _download_file(
        hostname=args.hostname,
        local_file=args.local_file,
        plc_filename=args.plc_filename,
    )


def _download_file(
    hostname: str,
    local_file: Optional[str] = None,
    plc_filename: Optional[str] = None,
) -> int:
    """
    Download a database file previously exported to a PLC.

    Parameters
    ----------
    hostname : str
        PLC hostname to download from.
    local_file : str, optional
        Full path to save locally. If omitted, download to stdout.
    plc_filename : str, optional
        Name of the file on the PLC end.
        If omitted, this will be the default name the PLC loads the database from.
    """
    plc_filename = plc_filename or default_load_name(hostname)
    text = download_file_text(hostname=hostname, filename=plc_filename)
    if local_file is None:
        print(text)
    else:
        with open(local_file, 'w') as fd:
            fd.write(text)
    return 0


def cli_compare_file(args: argparse.Namespace) -> int:
    return _compare(
        hostname=args.hostname,
        local_file=args.local_file,
        plc_filename=args.plc_filename,
    )


def _compare(
    hostname: str,
    local_file: Optional[str] = None,
    plc_filename: Optional[str] = None,
) -> int:
    """
    Compare files beteween the local exports and the PLC.

    Parameters
    ----------
    hostname : str
        PLC hostname to upload to
    local_file : str, optional
        Full path to the local file you want to compare.
        If omitted, we will use the latest database export.
    plc_filename : str, optional
        Name of the file on the PLC end.
        If omitted, this will be the standard export name
        if we can figure it out from the local filename,
        or the default name the PLC loads the database from otherwise.
    """
    local_file, plc_filename = default_upload_naming(
        hostname=hostname,
        local_file=local_file,
        plc_filename=plc_filename,
    )
    same = compare_file(
        hostname=hostname,
        local_filename=local_file,
        plc_filename=plc_filename,
    )
    if same:
        logger.info(
            'Local file %s matches PLC file %s',
            local_file,
            plc_filename,
        )
    else:
        logger.error(
            'Local file %s does not match PLC file %s',
            local_file,
            plc_filename,
        )
    return int(same)


def default_upload_naming(
    hostname: str,
    local_file: Optional[str],
    plc_filename: Optional[str],
) -> tuple[str, str]:
    """
    Given standard args for upload or compare, get the correct filenames to use.

    Parameters
    ----------
    hostname : str
        PLC hostname
    local_file : str or None
        Full path to the local file.
        If None, we will use the latest database export.
    plc_filename : str or None
        Name of the file on the PLC end.
        If None, this will be the standard export name
        if we can figure it out from the local filename,
        or the default name the PLC loads the database from otherwise.

    Returns
    -------
    local_file, plc_filename : tuple of str
        The filenames as used in the other functions.
    """
    if local_file is None:
        latest_files = get_latest_exported_files()
        try:
            export = latest_files[hostname]
        except KeyError:
            raise RuntimeError(f'No files exported for {hostname}.')
        local_file = export.full_path
    else:
        export = None
    if plc_filename is None:
        if export is None:
            try:
                export = ExportFile.from_filename(os.path.basename(local_file))
            except ValueError:
                logger.warning('Filename %s does not follow normal export formatting', local_file)
                plc_filename = default_load_name(hostname)
            else:
                plc_filename = export.get_plc_filename()
        else:
            plc_filename = export.get_plc_filename()
    return local_file, plc_filename


def default_load_name(hostname: str) -> str:
    return f'{hostname}.json'
