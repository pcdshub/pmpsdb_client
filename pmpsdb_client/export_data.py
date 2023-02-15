"""
Module to define standard paths and file formats for finding database exports.
"""
from __future__ import annotations

import collections
import dataclasses
import datetime
import json
import logging
import os
import os.path
import re

logger = logging.getLogger(__name__)

DEFAULT_EXPORT_DIR = "/cds/group/pcds/pyps/apps/pmpsdb_server/pmps-db/export"
# Example filename: exported_plc-kfe-gatt-2023-01-19T16:22:00.673108.json
FILE_FORMAT_RE = re.compile(r"^exported_(.*)-(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})\.(\d{6}).json$")
_export_dir = None


def get_export_dir() -> str:
    return _export_dir or DEFAULT_EXPORT_DIR


def set_export_dir(directory: str) -> None:
    global _export_dir
    _export_dir = str(directory)


@dataclasses.dataclass(frozen=True)
class ExportFile:
    plc_name: str
    export_time: datetime.datetime
    filename: str
    full_path: str

    @classmethod
    def from_filename(cls, filename: str) -> ExportFile:
        match = FILE_FORMAT_RE.match(filename)
        if not match:
            raise ValueError(f'Invalid export filename {filename}')
        plc_name, year, month, day, hour, minute, second, micro = match.groups()
        return cls(
            plc_name=plc_name,
            export_time=datetime.datetime(
                year=int(year),
                month=int(month),
                day=int(day),
                hour=int(hour),
                minute=int(minute),
                second=int(second),
                microsecond=int(micro),
            ),
            filename=filename,
            full_path=os.path.join(get_export_dir(), filename),
        )

    def get_plc_filename(self) -> str:
        return f'{self.plc_name}.json'

    def get_data(self) -> dict:
        with open(self.full_path) as fd:
            return json.load(fd)


def get_exported_files() -> list[ExportFile]:
    """The full contents of the export directory."""
    all_filenames = os.listdir(get_export_dir())
    all_exports = []
    for filename in all_filenames:
        try:
            export = ExportFile.from_filename(filename)
        except ValueError as exc:
            logger.debug(exc)
        except Exception:
            logger.error(f'Unknown error checking {filename}')
            logger.debug('', exc_info=True)
        else:
            all_exports.append(export)
    return all_exports


def select_latest_exported_files(all_exports: list[ExportFile]) -> dict[str, ExportFile]:
    """Get the latest file for each PLC, given a list of exports."""
    null_file = ExportFile(plc_name='', export_time=datetime.datetime(datetime.MINYEAR, 1, 1), filename='', full_path='')
    latest_exports = collections.defaultdict(lambda: null_file)
    for export in all_exports:
        if latest_exports[export.plc_name].export_time < export.export_time:
            latest_exports[export.plc_name] = export
    return dict(latest_exports)


def get_latest_exported_files() -> dict[str, ExportFile]:
    """Get the latest file for each PLC."""
    return select_latest_exported_files(get_exported_files())
