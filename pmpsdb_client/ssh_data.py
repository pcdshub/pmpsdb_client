"""
Module to define the scp transfer interface for the TCBSD PLCs.

This is how we upload database files to and download database files from the
PLCs.
"""
from __future__ import annotations

import datetime
import logging
import typing
from contextlib import contextmanager
from dataclasses import dataclass

from fabric import Connection

logger = logging.getLogger(__name__)

DEFAULT_PW = (
    ("Administrator", "1"),
)
DIRECTORY = "/Hard Disk/ftp/pmps"

T = typing.TypeVar("T")


@contextmanager
def ssh(
    hostname: str,
    directory: typing.Optional[str] = None,
) -> Connection:
    """
    Context manager to handle a single ssh connection.

    Within one connection we can do any number of remote operations on the
    TCBSD PLC.
    """
    directory = directory or DIRECTORY
    connected = False
    excs = []

    for user, pw in DEFAULT_PW:
        with Connection(
            host=hostname,
            user=user,
            connect_kwargs={"password": pw}
        ) as conn:
            try:
                conn.open()
            except Exception as exc:
                excs.append(exc)
                continue
            connected = True
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
class FileInfo:
    """
    File information from *nix systems.
    """
    is_directory: bool
    permissions: str
    links: int
    user: str
    group: str
    size: int
    last_changed: datetime.datetime
    filename: str

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
    directory: typing.Optional[str] = None,
) -> list[FileInfo]:
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
    filenames : list of str
        The filenames on the PLC.
    """
    logger.debug("list_filenames(%s, %s)", hostname, directory)
    with ssh(hostname=hostname, directory=directory) as conn:
        output = FileInfo.get_output_lines(conn)
    return FileInfo.from_all_output_lines(output)
