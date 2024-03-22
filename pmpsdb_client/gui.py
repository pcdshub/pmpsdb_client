"""
Module to definte the graphical user interface for pmpsdb.

This is the locally run interface that allows us to communicate
with both the database and the PLCs, showing useful diagnostic
information and allowing file transfers.
"""
import copy
import datetime
import enum
import logging
import os
import os.path
import socket
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import yaml
from ophyd.utils.epics_pvs import AlarmSeverity
from pcdscalc.pmps import get_bitmask_desc
from pcdsutils.qt import DesignerDisplay
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (QAction, QDialog, QFileDialog, QInputDialog,
                            QLabel, QListWidget, QListWidgetItem, QMainWindow,
                            QMessageBox, QStatusBar, QTableWidget,
                            QTableWidgetItem, QWidget)

from .beam_class import summarize_beam_class_bitmask
from .export_data import ExportFile, get_export_dir, get_latest_exported_files
from .ioc_data import AllStateBP, PLCDBControls
from .plc_data import (download_file_json_dict, download_file_text,
                       list_file_info, upload_filename)

logger = logging.getLogger(__name__)

PARAMETER_HEADER_ORDER = [
    'name',
    'id',
    'nRate',
    'nBeamClassRange',
    'neVRange',
    'nTran',
    'ap_name',
    'ap_xgap',
    'ap_xcenter',
    'ap_ygap',
    'ap_ycenter',
    'damage_limit',
    'pulse_energy',
    'reactive_temp',
    'reactive_pressure',
    'notes',
    'special',
]


class PMPSManagerGui(QMainWindow):
    """
    The main GUI window for pmpsdb_client.

    This defines the file actions menu and creates the SummaryTables widget.

    Parameters
    ----------
    configs : list of str, optional
        The path to the configuration files. Configuration files are
        expected to be a yaml mapping from plc name to IOC prefix PV.
        The configuration file may be expanded in the future.
    expert_dir : str, optional
        The directory that contains the exported database files.
    """
    def __init__(self, configs: list[str]):
        super().__init__()
        self.setWindowTitle('PMPSDB Client GUI')
        if not configs:
            configs = select_default_config()
        self.plc_config = {}
        for config in configs:
            with open(config, 'r') as fd:
                self.plc_config.update(yaml.full_load(fd))
        self.plc_hostnames = list(self.plc_config)
        self.tables = SummaryTables(plc_config=self.plc_config)
        self.setCentralWidget(self.tables)
        self.setup_menu_options()
        self.setup_status_bar()
        self.device_map = None
        logger.info('pmpsdb client gui loaded')

    def setup_menu_options(self):
        """
        Create entries and actions in the menu for all configured PLCs.
        """
        menu = self.menuBar()

        file_menu = menu.addMenu('&File')
        upload_latest_menu = file_menu.addMenu('Upload &Latest to')
        upload_menu = file_menu.addMenu('&Upload to')
        download_menu = file_menu.addMenu('&Download from')
        reload_menu = file_menu.addMenu('&Reload Params')
        # Actions will be garbage collected if we drop this reference
        self.actions = []
        for plc in self.plc_hostnames:
            upload_latest_action = QAction()
            upload_latest_action.setText(plc)
            upload_latest_menu.addAction(upload_latest_action)
            upload_action = QAction()
            upload_action.setText(plc)
            upload_menu.addAction(upload_action)
            download_action = QAction(plc)
            download_action.setText(plc)
            download_menu.addAction(download_action)
            reload_action = QAction(plc)
            reload_action.setText(plc)
            reload_menu.addAction(reload_action)
            self.actions.append(upload_latest_action)
            self.actions.append(upload_action)
            self.actions.append(download_action)
            self.actions.append(reload_action)
        upload_latest_menu.triggered.connect(self.upload_latest)
        upload_menu.triggered.connect(self.upload_to)
        download_menu.triggered.connect(self.download_from)
        reload_menu.triggered.connect(self.reload_params)

        device_menu = menu.addMenu('&Device')
        find_plc_action = device_menu.addAction('&Find Device PLC')
        find_plc_action.triggered.connect(self.find_plc)

        self.setMenuWidget(menu)

    def setup_status_bar(self) -> None:
        """
        Set up the status bar to show log messages INFO and higher.
        """
        status_bar = self.statusBar()
        status_bar.setContentsMargins(0, 0, 0, 3)
        handler = StatusBarHandler(status_bar)
        formatter = logging.Formatter('%(message)s')
        handler.setFormatter(formatter)
        our_logger = logging.getLogger('pmpsdb_client')
        our_logger.addHandler(handler)

    def upload_latest(self, action: QAction) -> None:
        """
        Upload the latest database export to a plc.
        """
        hostname = action.text()

        reply = QMessageBox.question(
            self,
            'Confirm upload',
            (
                f'Are you sure you want to upload the latest parameters to {hostname}? '
                'Note that this will affect ongoing experiments on next reload.'
            ),
        )
        if reply != QMessageBox.Yes:
            return

        latest_exports = get_latest_exported_files()
        try:
            this_plc_latest = latest_exports[hostname]
        except KeyError:
            logger.error('No exports found for plc %s', hostname)
            return
        try:
            upload_filename(
                hostname=hostname,
                filename=this_plc_latest.full_path,
                dest_filename=this_plc_latest.get_plc_filename(),
            )
        except Exception:
            logger.error('Failed to upload %s to %s', this_plc_latest.filename, hostname)
            logger.debug('', exc_info=True)
        else:
            logger.info('Uploaded latest database file to %s', hostname)
        self.tables.on_file_upload(hostname)

    def upload_to(self, action: QAction) -> None:
        """
        Upload a file from the local filesystem to a plc.
        """
        hostname = action.text()
        logger.debug('%s upload action', hostname)
        # Show file browser on local host
        filename, _ = QFileDialog.getOpenFileName(
            self,
            'Select file',
            get_export_dir(),
            "(*.json)",
        )
        if not filename or not os.path.exists(filename):
            logger.error('%s does not exist, aborting.', filename)
            return

        reply = QMessageBox.question(
            self,
            'Confirm upload',
            (
                f'Are you sure you want to upload {os.path.basename(filename)} to {hostname}? '
                'Note that this will affect ongoing experiments on next reload.'
            ),
        )
        if reply != QMessageBox.Yes:
            return

        try:
            exported_file = ExportFile.from_filename(filename=os.path.basename(filename))
        except ValueError:
            # Does not match the exported file regex
            dest_filename = os.path.basename(filename)
        else:
            dest_filename = exported_file.get_plc_filename()

        logger.debug('Uploading %s to %s as %s', filename, hostname, dest_filename)
        try:
            upload_filename(
                hostname=hostname,
                filename=filename,
                dest_filename=dest_filename,
            )
        except Exception:
            logger.error('Failed to upload %s to %s', filename, hostname)
            logger.debug('', exc_info=True)
        else:
            logger.info('Uploaded file to %s', hostname)
        self.tables.on_file_upload(hostname)

    def download_from(self, action: QAction) -> None:
        """
        Download a file from a plc to the local filesystem.
        """
        hostname = action.text()
        logger.debug('%s download action', hostname)
        # Check the available files
        try:
            file_info = list_file_info(hostname=hostname)
        except Exception:
            logger.error('Unable to read files from %s', hostname)
            logger.debug('', exc_info=True)
            return
        if not file_info:
            logger.error('No PMPS files on  %s', hostname)
            return
        # Show the user and let the user select one file
        filename, ok = QInputDialog.getItem(
            self,
            'Filenames',
            'Please select which file to download',
            [data.filename for data in file_info],
        )
        if not ok:
            return
        # Download the file
        try:
            text = download_file_text(
                hostname=hostname,
                filename=filename,
            )
        except Exception:
            logger.error('Error downloading %s from %s', filename, hostname)
            logger.debug('', exc_info=True)
            return
        # Let the user select a place to save the file
        save_filename, _ = QFileDialog.getSaveFileName(
            self,
            'Save file',
            os.getcwd(),
            '(*.json)',
        )
        if not save_filename:
            return
        try:
            with open(save_filename, 'w') as fd:
                fd.write(text)
        except Exception as exc:
            logger.error('Error writing file: %s', exc)
            logger.debug('', exc_info=True)
        else:
            logger.info(
                'Downloaded file %s from %s to %s',
                filename,
                hostname,
                save_filename,
            )

    def reload_params(self, action: QAction) -> None:
        """
        Command a PLC to reload its PMPS parameters from the database file.
        """
        hostname = action.text()
        logger.debug('%s reload action', hostname)
        # Confirmation dialog, this is kind of bad to do accidentally
        reply = QMessageBox.question(
            self,
            'Confirm reload',
            (
                'Are you sure you want to reload the '
                f'parameters on {hostname}? '
                'Note that this will apply to and affect ongoing experiments.'
            ),
        )
        if reply != QMessageBox.Yes:
            return
        # Just put to the pv
        try:
            self.tables.db_controls[hostname].refresh.put(1)
        except Exception as exc:
            logger.error('Error starting param reload for %s: %s', hostname, exc)
            logger.debug('', exc_info=True)
        else:
            logger.info('Reloaded params for %s', hostname)

    def find_plc(self, *args, **kwargs):
        """Show the DeviceMap dialog."""
        if self.device_map is None:
            self.device_map = DeviceMap()
        self.device_map.update_data(self.plc_hostnames)
        self.device_map.raise_()
        self.device_map.show()


def select_default_config() -> list[str]:
    """
    Select the most likely correct config based on the hostname.
    """
    hostname = socket.gethostname()
    if 'kfe' in hostname:
        configs = ['kfe']
    elif 'tmo' in hostname:
        configs = ['kfe', 'tmo']
    elif 'rix' in hostname:
        configs = ['kfe', 'rix']
    elif 'lfe' in hostname:
        configs = ['lfe']
    elif 'xpp' in hostname:
        configs = ['lfe']
    elif 'xcs' in hostname:
        configs = ['lfe']
    elif 'mfx' in hostname:
        configs = ['lfe']
    elif 'cxi' in hostname:
        configs = ['lfe']
    elif 'mec' in hostname:
        configs = ['lfe']
    else:
        configs = ['tst']
    return [str(Path(__file__).parent / f'pmpsdb_{cfg}.yml') for cfg in configs]


class DeviceMap(DesignerDisplay, QDialog):
    """
    Dialog that shows the mapping between device and plc
    """
    filename = Path(__file__).parent / 'device_map.ui'

    table: QTableWidget

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Device to PLC Map')

    def update_data(self, plc_hostnames):
        exports = get_latest_exported_files()
        data = {}
        for plc_name, export_file in exports.items():
            if plc_name not in plc_hostnames:
                continue
            try:
                device_data = export_file.get_data()[plc_name]
            except Exception:
                logger.error('Error reading export file data for %s', plc_name)
                logger.debug('', exc_info=True)
            else:
                for device_name in device_data:
                    if device_name in data:
                        logger.error(
                            'Device %s is in both %s and %s',
                            device_name,
                            plc_name,
                            data[device_name]
                        )
                    else:
                        data[device_name] = plc_name

        self.table.clearContents()
        self.table.setRowCount(0)
        for row_num, (device_name, plc_name) in enumerate(sorted(data.items())):
            self.table.insertRow(row_num)
            self.table.setItem(
                row_num,
                0,
                QTableWidgetItem(device_name),
            )
            self.table.setItem(
                row_num,
                1,
                QTableWidgetItem(plc_name),
            )
        self.table.resizeColumnsToContents()


class PLCTableColumns(enum.IntEnum):
    """
    Column assignments for the PLC table.
    """
    NAME = 0
    STATUS = 1
    EXPORT = 2
    UPLOAD = 3
    RELOAD = 4


class LoadedTableRows(enum.IntEnum):
    """
    Row assignments for the loaded table.
    """
    PLC_NAME = 0
    IOC_STATUS = 1
    HAS_LATEST_EXPORT = 2


class LoadedTableColumns(enum.IntEnum):
    """
    Column assignments for the loaded table.
    """
    EMOJI = 0
    TEXT = 1


class SummaryTables(DesignerDisplay, QWidget):
    """
    Widget that contains tables of information about deployed PLC databases.

    Parameters
    ----------
    plc_config : dict[str, str]
        The loaded configuration file. The configuration file is
        expected to be a yaml mapping from plc name to IOC prefix PV.
        The configuration file may be expanded in the future.
    expert_dir : str
        The directory that contains the exported database files.
    """
    filename = Path(__file__).parent / 'tables.ui'

    title_label: QLabel
    plc_label: QLabel
    plc_table: QTableWidget
    loaded_label: QLabel
    loaded_table: QTableWidget
    device_label: QLabel
    device_list: QListWidget
    param_label: QLabel
    param_table: QTableWidget
    ioc_label: QLabel
    ioc_table: QTableWidget

    # Human readable column headers
    plc_columns: ClassVar[dict[int, str]] = {
        PLCTableColumns.NAME: 'plc name',
        PLCTableColumns.STATUS: 'status',
        PLCTableColumns.EXPORT: 'file last exported',
        PLCTableColumns.UPLOAD: 'file last uploaded',
        PLCTableColumns.RELOAD: 'params last loaded',
    }
    # Human readable row headers
    loaded_rows: ClassVar[dict[int, str]] = {
        LoadedTableRows.PLC_NAME: 'plc name',
        LoadedTableRows.IOC_STATUS: 'ioc connect',
        LoadedTableRows.HAS_LATEST_EXPORT: 'has latest',
    }
    # Human readable column headers
    loaded_columns: ClassVar[dict[int, str]] = {
        LoadedTableColumns.EMOJI: 'Ok',
        LoadedTableColumns.TEXT: 'Status',
    }
    cached_db: dict[str: dict[str, dict[str, Any]]]
    param_dict: dict[str, dict[str, Any]]
    plc_row_map: dict[str, int]
    ok_rows: dict[int, bool]
    line: str

    def __init__(self, plc_config: dict[str, str]):
        super().__init__()
        self.ok_rows = {}
        self.db_controls = {
            name: PLCDBControls(prefix=prefix + ':', name=name)
            for name, prefix in plc_config.items()
        }
        self.setup_table_columns()
        self.plc_row_map = {}
        self.line = 'l'
        self._test_mode = False
        for hostname in plc_config:
            if '-tst-' in hostname:
                self._test_mode = True
            self.add_plc(hostname)
        self.update_export_times()
        self.plc_table.resizeColumnsToContents()
        self.plc_table.cellActivated.connect(self.plc_selected)
        self.device_list.itemActivated.connect(self.device_selected)

    def setup_table_columns(self) -> None:
        """
        Set the column headers on the plc and loaded tables.
        """
        self.plc_table.setColumnCount(len(self.plc_columns))
        headers = [self.plc_columns[index] for index in sorted(self.plc_columns)]
        self.plc_table.setHorizontalHeaderLabels(headers)
        self.loaded_table.setColumnCount(len(self.loaded_columns))
        headers = [self.loaded_columns[index] for index in sorted(self.loaded_columns)]
        self.loaded_table.setHorizontalHeaderLabels(headers)
        self.loaded_table.setRowCount(len(self.loaded_rows))
        # Vertical (row) header skipped here: looks better without it
        self.clear_loaded_table()

    def add_plc(self, hostname: str) -> None:
        """
        Add a PLC row to the table on the left.
        """
        logger.debug('add_plc(%s)', hostname)
        row = self.plc_table.rowCount()
        self.plc_table.insertRow(row)
        name_item = QTableWidgetItem(hostname)
        status_item = QTableWidgetItem()
        export_time_item = QTableWidgetItem()
        upload_time_item = QTableWidgetItem()
        param_load_time = QTableWidgetItem()
        self.plc_table.setItem(row, PLCTableColumns.NAME, name_item)
        self.plc_table.setItem(row, PLCTableColumns.STATUS, status_item)
        self.plc_table.setItem(row, PLCTableColumns.EXPORT, export_time_item)
        self.plc_table.setItem(row, PLCTableColumns.UPLOAD, upload_time_item)
        self.plc_table.setItem(row, PLCTableColumns.RELOAD, param_load_time)
        self.update_plc_row(row, update_export=False)
        self.plc_row_map[hostname] = row

        def on_refresh(value, **kwargs):
            param_load_time.setText(
                datetime.datetime.fromtimestamp(value).ctime()
            )

        last_refresh_signal = self.db_controls[hostname].last_refresh
        param_load_time.setText(f'No connect: {last_refresh_signal.pvname}')
        last_refresh_signal.subscribe(on_refresh)

    def update_plc_row(self, row: int, update_export: bool = True) -> None:
        """
        Update the status information in the PLC table for one row.

        This is limited to the file read actions. We'll do this once on
        startup and again when the row is selected.
        Data source from PVs will be updated on monitor outside the scope
        of this method.
        """
        logger.debug('update_plc_row(%d)', row)
        hostname = self.plc_table.item(row, PLCTableColumns.NAME).text()
        logger.debug('row %d is %s', row, hostname)
        if check_server_online(hostname):
            text = 'online'
        else:
            text = 'offline'
        self.plc_table.item(row, PLCTableColumns.STATUS).setText(text)
        info = []
        try:
            info = list_file_info(hostname)
        except Exception as exc:
            logger.error('Error reading file list from %s: %s', hostname, exc)
            logger.debug('list_file_info(%s) failed', hostname, exc_info=True)
            text = str(exc)
            if '] ' in text and text.startswith('[Errno'):
                text = text.split('] ')[1]
            text = text.capitalize()
            self.ok_rows[row] = False
        else:
            logger.debug('%s found file info %s', hostname, info)
            text = 'No upload found'
            self.ok_rows[row] = True
        filename = hostname_to_filename(hostname)
        for file_info in info:
            if file_info.filename == filename:
                text = file_info.last_changed.ctime()
                break
        self.plc_table.item(row, PLCTableColumns.UPLOAD).setText(text)
        if update_export:
            self.update_export_times()

    def update_plc_row_by_hostname(self, hostname: str) -> None:
        """
        Update the status information in the PLC table for one hostname.
        """
        return self.update_plc_row(self.plc_row_map[hostname])

    def update_export_times(self) -> None:
        """
        For all table rows, update the timestamp of the latest export file.
        """
        latest_exports = get_latest_exported_files()
        for row in range(self.plc_table.rowCount()):
            plc_name = self.plc_table.item(row, PLCTableColumns.NAME).text()
            export_item = self.plc_table.item(row, PLCTableColumns.EXPORT)
            try:
                plc_export = latest_exports[plc_name]
            except KeyError:
                export_item.setText('No exports found')
            else:
                export_item.setText(plc_export.export_time.ctime())

    def get_cached_db(self, hostname: str) -> bool:
        """
        Download and cache the full contents of the database file.

        Returns True if successful and False otherwise.
        """
        self.cached_db = None
        filename = hostname_to_filename(hostname)
        try:
            self.cached_db = download_file_json_dict(
                hostname=hostname,
                filename=filename,
            )
            logger.debug('%s found db info %s', hostname, self.cached_db)
        except Exception:
            logger.error(
                'Could not download %s from %s',
                filename,
                hostname,
            )
            logger.debug(
                'download_file_json_dict(%s, %s) failed',
                hostname,
                filename,
                exc_info=True,
            )
            return False
        return True

    def clear_loaded_table(self) -> None:
        """
        Empty the loaded table and replace it with stock not-loaded info.
        """
        self.loaded_table.clearContents()
        self.loaded_table.setCellWidget(
            LoadedTableRows.PLC_NAME,
            LoadedTableColumns.EMOJI,
            not_ok_label(),
        )
        self.loaded_table.setItem(
            LoadedTableRows.PLC_NAME,
            LoadedTableColumns.TEXT,
            QTableWidgetItem('No plc loaded'),
        )
        self.loaded_table.resizeColumnsToContents()

    def fill_loaded_table(self, hostname: str) -> None:
        """
        Assemble information for the "loaded" table.

        Requires a valid cached database from get_cached_db
        """
        self.clear_loaded_table()
        self.loaded_table.setCellWidget(
            LoadedTableRows.PLC_NAME,
            LoadedTableColumns.EMOJI,
            ok_label(),
        )
        self.loaded_table.setItem(
            LoadedTableRows.PLC_NAME,
            LoadedTableColumns.TEXT,
            QTableWidgetItem(hostname),
        )
        if self.db_controls[hostname].connected:
            sev = self.db_controls[hostname].last_refresh.alarm_severity
            if sev == AlarmSeverity.NO_ALARM:
                ioc_emoji = ok_label()
                ioc_status = 'Connected'
            elif sev is None:
                ioc_emoji = not_ok_label()
                ioc_status = 'Disconnected'
            else:
                ioc_emoji = not_ok_label()
                ioc_status = AlarmSeverity(int(sev)).name.title()
        else:
            ioc_emoji = not_ok_label()
            ioc_status = 'Disconnected'
        self.loaded_table.setCellWidget(
            LoadedTableRows.IOC_STATUS,
            LoadedTableColumns.EMOJI,
            ioc_emoji,
        )
        self.loaded_table.setItem(
            LoadedTableRows.IOC_STATUS,
            LoadedTableColumns.TEXT,
            QTableWidgetItem(ioc_status),
        )
        # Open the latest file and compare it to the cached db
        try:
            all_files = get_latest_exported_files()
        except Exception:
            logger.error('Error checking file system for exports')
            logger.debug('', exc_info=True)
            file_info = None
        else:
            file_info = all_files.get(hostname, None)
        if file_info is None:
            latest_emoji = not_ok_label()
            latest_text = 'No export files'
        else:
            try:
                file_data = file_info.get_data()
            except Exception:
                logger.error('Error reading export file data')
                logger.debug('', exc_info=True)
                latest_emoji = not_ok_label()
                latest_text = 'Bad file read'
            else:
                if file_data == self.cached_db:
                    latest_emoji = ok_label()
                    latest_text = "Latest file"
                else:
                    latest_emoji = not_ok_label()
                    latest_text = "Old file"
        self.loaded_table.setCellWidget(
            LoadedTableRows.HAS_LATEST_EXPORT,
            LoadedTableColumns.EMOJI,
            latest_emoji,
        )
        self.loaded_table.setItem(
            LoadedTableRows.HAS_LATEST_EXPORT,
            LoadedTableColumns.TEXT,
            QTableWidgetItem(latest_text),
        )
        self.loaded_table.resizeColumnsToContents()

    def fill_device_list(self, hostname: str) -> None:
        """
        Populate the device list.

        Requires a valid cached database from get_cached_db
        """
        self.device_list.clear()
        self.param_table.clear()
        key = hostname_to_key(hostname)
        try:
            self.param_dict = self.cached_db[key]
        except KeyError:
            logger.error('Did not find required entry %s', key)
            return
        for device_name in self.param_dict:
            self.device_list.addItem(device_name)
        logger.info(
            'Found %d devices in %s local database',
            len(self.param_dict),
            hostname,
        )

    def fill_parameter_table(self, device_name: str) -> None:
        """
        Use the cached db to show a single device's parameters in the table.
        """
        self.param_table.clear()
        self.param_table.setRowCount(0)
        self.param_table.setColumnCount(0)
        prefix = device_name.lower().split('-')[0]
        # Find the last letter in prefix
        for char in reversed(prefix):
            if char in ('l', 'k'):
                self.line = char
                break
        try:
            device_params = self.param_dict[device_name]
        except KeyError:
            logger.error('Did not find device %s in db', device_name)
            logger.debug(
                '%s not found in json info',
                device_name,
                exc_info=True,
            )
            return

        # Lock in the header
        header_from_file = list(list(device_params.values())[0])
        header = copy.copy(PARAMETER_HEADER_ORDER)
        for elem in header_from_file:
            if elem not in header:
                header.append(elem)
        self.param_table.setColumnCount(len(header))
        self.param_table.setHorizontalHeaderLabels(header)
        self._fill_params(
            table=self.param_table,
            header=header,
            params=device_params,
        )
        logger.info(
            'Found %d states for %s in plc database',
            len(device_params),
            device_name,
        )

        self.ioc_table.clear()
        self.ioc_table.setRowCount(0)
        self.ioc_table.setColumnCount(0)

        prefixes = self.get_states_prefixes(device_name)
        all_states = [AllStateBP(prefix, name=prefix) for prefix in prefixes]
        ioc_params = {}
        for states in all_states:
            try:
                ioc_params.update(states.get_table_data())
            except TimeoutError as exc:
                logger.error('Did not find values for device %s in ioc', device_name)
                logger.debug('', exc_info=True)
                # Get an example PV that didn't connect for the table
                self.ioc_table.setColumnCount(1)
                self.ioc_table.setRowCount(1)
                self.ioc_table.setHorizontalHeaderLabels([''])
                self.ioc_table.setItem(0, 0, QTableWidgetItem(str(exc)))
                return

        ioc_header = list(list(ioc_params.values())[0])
        self.ioc_table.setColumnCount(len(ioc_header))
        self.ioc_table.setHorizontalHeaderLabels(ioc_header)

        self._fill_params(
            table=self.ioc_table,
            header=ioc_header,
            params=ioc_params,
        )
        logger.info(
            'Found %d states for %s in IOC',
            len(ioc_params),
            device_name,
        )

    def _fill_params(self, table, header, params) -> None:
        for state_info in params.values():
            row = table.rowCount()
            table.insertRow(row)
            for key, value in state_info.items():
                col = header.index(key)
                value = str(value)
                item = QTableWidgetItem(value)
                self.set_param_cell_tooltip(item, key, value)
                table.setItem(row, col, item)
        table.resizeColumnsToContents()

    def get_states_prefixes(self, device_name: str) -> list[str]:
        """
        Get the PV prefixes that corresponds to the device name.
        """
        if 'GAS_MAA' in device_name:
            # Gas attenuator apertures
            return [
                device_name.replace('-', ':') + ':Y:STATE:',
                device_name.replace('-', ':') + ':X:STATE:'
            ]
        elif 'SOMS' in device_name or 'KBO' in device_name:
            # Mirror coatings
            return [device_name.replace('-', ':') + ':COATING:STATE:']
        else:
            # PPM, XPIM, WFS, others?
            return [device_name.replace('-', ':') + ':MMS:STATE:']

    def set_param_cell_tooltip(
        self,
        item: QTableWidgetItem,
        key: str,
        value: str,
    ) -> None:
        """
        Set a tooltip to help out with a single cell in the parameters table.
        """
        if key == 'nBeamClassRange':
            bitmask = int(value, base=2)
            text = summarize_beam_class_bitmask(bitmask)
        elif key == 'neVRange':
            bitmask = int(value, base=2)
            lines = get_bitmask_desc(
                bitmask=bitmask,
                line=self.line,
            )
            text = '\n'.join(lines)
        else:
            # Have not handled this case yet
            return
        item.setToolTip('<pre>' + text + '</pre>')

    def plc_selected(self, row: int, col: int) -> None:
        """
        When a plc is selected, reset ioc/param tables and seed the device list.
        """
        hostname = self.plc_table.item(row, 0).text()
        logger.info('Selecting %s', hostname)
        self.param_table.clear()
        self.param_table.setRowCount(0)
        self.param_table.setColumnCount(0)
        self.ioc_table.clear()
        self.ioc_table.setRowCount(0)
        self.ioc_table.setColumnCount(0)
        self.clear_loaded_table()
        self.device_list.clear()
        self.update_plc_row(row)
        if self.ok_rows.get(row, False):
            if self.get_cached_db(hostname):
                self.fill_loaded_table(hostname)
                self.fill_device_list(hostname)

    def device_selected(self, item: QListWidgetItem) -> None:
        """
        When a device is selected, reset and seed the parameter list.
        """
        logger.info('Selecting %s', item.text())
        self.fill_parameter_table(item.text())

    def on_file_upload(self, hostname: str) -> None:
        """
        This should be ran when a file is uploaded by the user in this gui session.

        This will select the corresponding PLC in the GUI in order to reload and
        show the pertinent information for that PLC.
        """
        for plc_row in range(self.plc_table.rowCount()):
            if self.plc_table.item(plc_row, PLCTableColumns.NAME).text() == hostname:
                # Visual selection, doesn't "activate" (double-click) the cell
                self.plc_table.setCurrentCell(plc_row, PLCTableColumns.NAME)
                # Manually run the "activate" slot
                self.plc_selected(plc_row, PLCTableColumns.NAME)
                break


class StatusBarHandler(logging.Handler):
    """
    Logging handler for sending log messages to a QStatusBar.
    """
    colors = {
        logging.CRITICAL: "crimson",
        logging.ERROR: "darkred",
        logging.WARNING: "darkorange",
        logging.INFO: "black",
        logging.DEBUG: "darkgreen",
    }

    def __init__(self, status_bar: QStatusBar, level: int = logging.NOTSET) -> None:
        super().__init__(level=level)
        self.status_bar = status_bar
        self.label = None

    def emit(self, record: logging.LogRecord):
        if self.label is not None:
            self.status_bar.removeWidget(self.label)
        self.label = QLabel(self.format(record))
        self.label.setIndent(10)
        self.label.setStyleSheet(
            f"QLabel {{ color: {self.colors.get(record.levelno, 'black')} }}"
        )
        self.status_bar.addWidget(self.label)


def check_server_online(hostname: str) -> bool:
    """
    Ping a hostname to determine if it is network accessible or not.
    """
    try:
        subprocess.run(
            ['ping', '-c', '1', hostname],
            capture_output=True,
        )
        return True
    except Exception:
        logger.debug('%s ping failed', hostname, exc_info=True)
        return False


def hostname_to_key(hostname: str) -> str:
    """
    Given a hostname, get the database key associated with it.
    """
    return hostname


def hostname_to_filename(hostname: str) -> str:
    """
    Given a hostname, get the filename associated with it.
    """
    return hostname_to_key(hostname) + '.json'


def rich_color(text: str, color: str) -> str:
    """
    Adds html color tags to input text.
    """
    return f'<span style="color: {color};">{text}</span>'


def emoji_label(emoji: str, color: str) -> QLabel:
    """
    Create a suitable QLabel to display an emoji symbol.
    """
    label = QLabel(rich_color(emoji, color))
    label.setAlignment(Qt.AlignCenter)
    return label


def ok_label() -> QLabel:
    """
    Build a QLabel widget that shows a green checkmark.
    """
    return emoji_label("✔", "green")


def not_ok_label() -> QLabel:
    """
    Build a QLabel widget that shows a red checkmark.
    """
    return emoji_label("❌", "red")
