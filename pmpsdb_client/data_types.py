"""
This module defines important data structures centrally.

This helps us compare the same kinds of data to each other,
even when this data comes from different sources.

Note that all the dataclasses are frozen: editing these data
structures is not in scope for this library, it is only intended
to move these files around and compare them to each other.
"""
import dataclasses
import datetime


@dataclasses.dataclass(frozen=True)
class FileInfo:
    """
    Generalized file info.

    Only contains fields available to both ftp and ssh.

    This class has no constructor helpers here.
    Each data source will need to implement a unique
    constructor for this.
    """
    filename: str
    size: int
    last_changed: datetime.datetime
