"""
Get file info from, upload files to, and download files from the PLCs.

This calls methods from ssh_data and ftp_data as appropriate.
When the system is configured correctly, exactly one of these submodules
should work for getting data from the PLC.
"""
from __future__ import annotations

import enum
import json
import logging
from typing import Any

from . import ftp_data, ssh_data
from .data_types import FileInfo

logger = logging.getLogger(__name__)
plc_mapping: dict[str, DataMethod] = {}


class DataMethod(enum.Enum):
    ssh = enum.auto()
    ftp = enum.auto()
    unk = enum.auto()


def get_data_method(hostname: str, directory: str | None = None) -> DataMethod:
    """
    For functions other than list_file_info: pick the data method from the cache,
    or by calling list_file_info.
    """
    try:
        return plc_mapping[hostname]
    except KeyError:
        list_file_info(hostname=hostname, directory=directory)
    return plc_mapping[hostname]


def list_file_info(
    hostname: str,
    directory: str | None = None,
) -> list[FileInfo]:
    """
    Get information about the files that are currently saved on the PLC.

    Parameters
    ----------
    hostname : str
        The plc hostname to check.
    directory : str, optional
        The diretory to read and write from.
        A default directory is used if this argument is omitted,
        which depends on the PLC OS.

    Returns
    -------
    filenames : list of FileInfo
        Information about all the files in the PLC's pmps folder.
    """
    try:
        data_method = plc_mapping[hostname]
    except KeyError:
        data_method = DataMethod.unk

    if data_method == DataMethod.ssh:
        logger.debug("Using cached ssh method to list files for %s", hostname)
        return ssh_data.list_file_info(hostname=hostname, directory=directory)
    elif data_method == DataMethod.ftp:
        logger.debug("Using cached ftp method to list files for %s", hostname)
        return ftp_data.list_file_info(hostname=hostname, directory=directory)
    elif data_method == DataMethod.unk:
        logger.debug("Connection method unknown, check if ssh method works for %s", hostname)
        try:
            file_info = ssh_data.list_file_info(hostname=hostname, directory=directory)
        except Exception:
            logger.debug("ssh failed, check if ftp method works for %s", hostname)
            try:
                file_info = ftp_data.list_file_info(hostname=hostname, directory=directory)
            except Exception:
                logger.debug("ftp failed too, maybe %s is offline or not set up", hostname)
                raise RuntimeError(f"Cannot connect to {hostname}")
            else:
                logger.debug("Cache %s method as ftp", hostname)
                plc_mapping[hostname] = DataMethod.ftp
                return file_info
        else:
            logger.debug("Cache %s method as ssh", hostname)
            plc_mapping[hostname] = DataMethod.ssh
            return file_info
    else:
        raise RuntimeError(f"Unhandled data method {data_method}")


def upload_filename(
    hostname: str,
    filename: str,
    dest_filename: str | None = None,
    directory: str | None = None,
) -> None:
    """
    Open and upload a file on your filesystem to a PLC.

    Parameters
    ----------
    hostname : str
        The plc hostname to upload to.
    filename : str
        The name of the file on your filesystem.
    dest_filename : str, optional
        The name of the file on the PLC. If omitted, same as filename.
    directory : str, optional
        The subdirectory to read and write from
        A default directory is used if this argument is omitted,
        which depends on the PLC OS.
    """
    data_method = get_data_method(hostname=hostname, directory=directory)
    if data_method == DataMethod.ssh:
        return ssh_data.upload_filename(
            hostname=hostname,
            filename=filename,
            dest_filename=dest_filename,
            directory=directory,
        )
    elif data_method == DataMethod.ftp:
        return ftp_data.upload_filename(
            hostname=hostname,
            filename=filename,
            dest_filename=dest_filename,
            directory=directory,
        )
    else:
        raise RuntimeError(f"Unhandled data method {data_method}")


def download_file_text(
    hostname: str,
    filename: str,
    directory: str | None = None,
) -> str:
    """
    Download a file from the PLC to use in Python.

    The result is a single string, suitable for operations like
    json.loads

    Parameters
    ----------
    hostname : str
        The plc hostname to download from.
    filename : str
        The name of the file on the PLC.
    directory : str, optional
        The subdirectory to read and write from
        A default directory is used if this argument is omitted,
        which depends on the PLC OS.

    Returns
    -------
    text: str
        The contents from the file.
    """
    data_method = get_data_method(hostname=hostname, directory=directory)
    if data_method == DataMethod.ssh:
        return ssh_data.download_file_text(
            hostname=hostname,
            filename=filename,
            directory=directory,
        )
    elif data_method == DataMethod.ftp:
        return ftp_data.download_file_text(
            hostname=hostname,
            filename=filename,
            directory=directory,
        )
    else:
        raise RuntimeError(f"Unhandled data method {data_method}")


def download_file_json_dict(
    hostname: str,
    filename: str,
    directory: str | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Download a file from the PLC and interpret it as a json dictionary.

    The result is suitable for comparing to json blobs exported from the
    pmps database.

    Parameters
    ----------
    hostname : str
        The plc hostname to download from.
    filename : str
        The name of the file on the PLC.
    directory : str, optional
        The subdirectory to read and write from
        A default directory is used if this argument is omitted,
        which depends on the PLC OS.

    Returns
    -------
    data : dict
        The dictionary data from the file stored on the plc.
    """
    logger.debug(
        'download_file_json_dict(%s, %s, %s)',
        hostname,
        filename,
        directory,
    )
    return json.loads(
        download_file_text(
            hostname=hostname,
            filename=filename,
            directory=directory,
        )
    )


def local_file_json_dict(filename: str) -> dict[str, dict[str, Any]]:
    """
    Return the json dict from a local file.

    Suitable for comparisons to files from the database or from the plc.

    Parameters
    ----------
    filename : str
        The name of the file on the local filesystem.

    Returns
    -------
    data : dict
        The dictionary data from the file stored on the local drive.
    """
    logger.debug('local_file_json_dict(%s)', filename)
    with open(filename, 'r') as fd:
        return json.load(fd)


def compare_file(
    hostname: str,
    local_filename: str,
    plc_filename: str | None = None,
    directory: str | None = None,
) -> bool:
    """
    Compare a file saved locally to one on the PLC.

    Parameters
    ----------
    hostname : str
        The plc hostname to download from.
    local_filename: str
        The full path the local file to compare with.
    plc_filename: str, optional
        The filename as saved on the PLC. If omitted, the local_filename's
        basename will be used.
    directory : str, optional
        The subdirectory to read and write from
        A default directory is used if this argument is omitted,
        which depends on the PLC OS.

    Returns
    -------
    same_file : bool
        True if the contents of these two files are the same.
    """
    logger.debug(
        'compare_file(%s, %s, %s, %s)',
        hostname,
        local_filename,
        plc_filename,
        directory,
    )
    local_data = local_file_json_dict(filename=local_filename)
    plc_data = download_file_json_dict(
        hostname=hostname,
        filename=plc_filename,
        directory=directory,
    )
    return local_data == plc_data
