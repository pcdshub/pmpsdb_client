"""
Module to define the scp transfer interface for the TCBSD PLCs.

This is how we upload database files to and download database files from the
PLCs.
"""
from __future__ import annotations

import logging
import typing
from contextlib import contextmanager

from fabric import Connection

logger = logging.getLogger(__name__)

DEFAULT_PW = (
    ("Administrator", "1"),
)
DIRECTORY = "/Hard Disk/ftp/pmps"


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


def list_filenames(
    hostname: str,
    directory: typing.Optional[str] = None,
) -> list[str]:
    """
    List the filenames that are currently saved on the PLC.

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
        output = conn.run("ls", hide=True).stdout
    return output.strip().split("\n")
