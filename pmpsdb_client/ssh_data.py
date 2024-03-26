"""
Module to define the scp transfer interface for the TCBSD PLCs.

This is how we upload database files to and download database files from the
PLCs.
"""
from __future__ import annotations

import datetime
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterator, TypeVar

from fabric import Connection
from fabric.config import Config
from paramiko.config import SSHConfig

from .data_types import FileInfo

DEFAULT_PW = (
    ("ecs-user", "1"),
)
DIRECTORY = "/home/{user}/pmpsdb"
SSH_CONFIG = """
Host *
    ForwardAgent no
    ForwardX11 no
    ForwardX11Trusted no
    PreferredAuthentications=password
"""

T = TypeVar("T")

logger = logging.getLogger(__name__)


@contextmanager
def ssh(
    hostname: str,
    directory: str | None = None,
) -> Iterator[Connection]:
    """
    Context manager to handle a single ssh connection.

    Within one connection we can do any number of remote operations on the
    TCBSD PLC.
    """
    connected = False
    excs = []

    for user, pw in DEFAULT_PW:
        with Connection(
            host=hostname,
            user=user,
            config=Config(ssh_config=SSHConfig.from_text(SSH_CONFIG)),
            connect_timeout=1,
            connect_kwargs={
                "password": pw,
                "allow_agent": False,
            },
        ) as conn:
            try:
                conn.open()
            except Exception as exc:
                excs.append(exc)
                continue
            connected = True
            directory = directory or DIRECTORY.format(user=user)
            result = conn.run(f"mkdir -p {directory}")
            if result.exited != 0:
                raise RuntimeError(f"Failed to create directory {directory}")
            # Note: conn.cd only affects calls to conn.run, not conn.get or conn.put
            # Use conn.cwd property to check this live
            with conn.cd(directory):
                yield conn
    if not connected:
        if len(excs) > 1:
            raise RuntimeError(excs)
        elif excs:
            raise excs[0]
        else:
            raise RuntimeError("Unable to connect to PLC")


@dataclass(frozen=True)
class SSHFileInfo(FileInfo):
    """
    File information from *nix systems.

    Adds extra detail not available through ftp.
    """
    is_directory: bool
    permissions: str
    links: int
    user: str
    group: str

    @staticmethod
    def get_output_lines(conn: Connection) -> str:
        return conn.run("ls -l -D %s", hide=True).stdout

    @classmethod
    def from_all_output_lines(cls: type[T], output_lines) -> list[T]:
        return [cls.from_output_line(line) for line in output_lines.strip().split("\n")[1:]]

    @classmethod
    def from_output_line(cls: type[T], output: str) -> T:
        type_perms, links, user, group, size, date, filename = output.strip().split()

        return cls(
            is_directory=type_perms[0] == "d",
            permissions=type_perms[1:],
            links=int(links),
            user=user,
            group=group,
            size=int(size),
            last_changed=datetime.datetime.fromtimestamp(int(date)),
            filename=filename,
        )


def list_file_info(
    hostname: str,
    directory: str | None = None,
) -> list[SSHFileInfo]:
    """
    Get information about the files that are currently saved on the PLC.

    Parameters
    ----------
    hostname : str
        The plc hostname to check.
    directory : str, optional
        The diretory to read and write from.
        A default directory pmps is used if this argument is omitted.

    Returns
    -------
    filenames : list of FileInfo
        Information about all the files in the PLC's pmps folder.
    """
    logger.debug("list_file_info(%s, %s)", hostname, directory)
    with ssh(hostname=hostname, directory=directory) as conn:
        output = SSHFileInfo.get_output_lines(conn)
    return SSHFileInfo.from_all_output_lines(output)


def upload_filename(
    hostname: str,
    filename: str,
    dest_filename: str | None = None,
    directory: str | None = None,
):
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
        The ssh subdirectory to read and write from
        A default directory /home/ecs-user/pmpsdb is used if this argument is omitted.
    """
    logger.debug("upload_filename(%s, %s, %s, %s)", hostname, filename, dest_filename, directory)
    if dest_filename is None:
        dest_filename = filename
    with ssh(hostname=hostname, directory=directory) as conn:
        if directory is None:
            directory = conn.cwd
        conn.put(local=filename, remote=str(Path(directory) / dest_filename))


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
        The ssh subdirectory to read and write from
        A default directory /home/ecs-user/pmpsdb is used if this argument is omitted.

    Returns
    -------
    text: str
        The contents from the file.
    """
    logger.debug("download_file_text(%s, %s, %s)", hostname, filename, directory)
    bytesio = BytesIO()
    with ssh(hostname=hostname, directory=directory) as conn:
        if directory is None:
            directory = conn.cwd
        conn.get(remote=str(Path(directory) / filename), local=bytesio)
    return bytesio.getvalue().decode(encoding="utf-8")
