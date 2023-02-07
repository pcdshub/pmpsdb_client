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
import subprocess
from pathlib import Path
from typing import Any, ClassVar

import yaml
from pcdscalc.pmps import get_bitmask_desc
from pcdsutils.qt import DesignerDisplay
from qtpy.QtWidgets import (QAction, QFileDialog, QInputDialog, QLabel,
                            QListWidget, QListWidgetItem, QMainWindow,
                            QMessageBox, QTableWidget, QTableWidgetItem,
                            QWidget)

from .beam_class import summarize_beam_class_bitmask
from .export_data import ExportFile, get_export_dir, get_latest_exported_files
from .ftp_data import (download_file_json_dict, download_file_text,
                       list_file_info, upload_filename)
from .ioc_data import AllStateBP, PLCDBControls

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
        if not configs:
            configs = [str(Path(__file__).parent / 'pmpsdb_tst.yml')]
        self.plc_config = {}
        for config in configs:
            with open(config, 'r') as fd:
                self.plc_config.update(yaml.full_load(fd))
        self.plc_hostnames = list(self.plc_config)
        self.tables = SummaryTables(plc_config=self.plc_config)
        self.setCentralWidget(self.tables)
        self.setup_menu_options()

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
        self.setMenuWidget(menu)

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
        self.tables.update_plc_row_by_hostname(hostname)

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
        self.tables.update_plc_row_by_hostname(hostname)

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


class PLCTableColumns(enum.IntEnum):
    """
    Column assignments for the PLC table.
    """
    NAME = 0
    STATUS = 1
    EXPORT = 2
    UPLOAD = 3
    RELOAD = 4


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
    device_label: QLabel
    device_list: QListWidget
    param_label: QLabel
    param_table: QTableWidget
    ioc_label: QLabel
    ioc_table: QTableWidget

    # Human readable colum headers
    plc_columns: ClassVar[dict[int, str]] = {
        PLCTableColumns.NAME: 'plc name',
        PLCTableColumns.STATUS: 'status',
        PLCTableColumns.EXPORT: 'file last exported',
        PLCTableColumns.UPLOAD: 'file last uploaded',
        PLCTableColumns.RELOAD: 'params last loaded',
    }
    param_dict: dict[str, dict[str, Any]]
    plc_row_map: dict[str, int]
    line: str

    def __init__(self, plc_config: dict[str, str]):
        super().__init__()
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
        Set the column headers on the plc and parameter tables.
        """
        self.plc_table.setColumnCount(len(self.plc_columns))
        headers = [self.plc_columns[index] for index in sorted(self.plc_columns)]
        self.plc_table.setHorizontalHeaderLabels(headers)

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

        param_load_time.setText('No PV connect')
        self.db_controls[hostname].last_refresh.subscribe(on_refresh)

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
        else:
            logger.debug('%s found file info %s', hostname, info)
            text = 'No upload found'
        filename = hostname_to_filename(hostname)
        for file_info in info:
            if file_info.filename == filename:
                text = file_info.create_time.ctime()
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

    def fill_device_list(self, hostname: str) -> None:
        """
        Cache the PLC's saved db and populate the device list.
        """
        self.device_list.clear()
        self.param_table.clear()
        filename = hostname_to_filename(hostname)
        try:
            json_info = download_file_json_dict(
                hostname=hostname,
                filename=filename,
            )
            logger.debug('%s found json info %s', hostname, json_info)
        except Exception:
            json_info = {}
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
        key = hostname_to_key(hostname)
        try:
            self.param_dict = json_info[key]
        except KeyError:
            self.param_dict = {}
            logger.error('Did not find required entry %s', key)
        for device_name in self.param_dict:
            self.device_list.addItem(device_name)

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
        self.update_plc_row(row)
        hostname = self.plc_table.item(row, 0).text()
        self.fill_device_list(hostname)
        self.param_table.clear()
        self.param_table.setRowCount(0)
        self.param_table.setColumnCount(0)
        self.ioc_table.clear()
        self.ioc_table.setRowCount(0)
        self.ioc_table.setColumnCount(0)

    def device_selected(self, item: QListWidgetItem) -> None:
        """
        When a device is selected, reset and seed the parameter list.
        """
        self.fill_parameter_table(item.text())


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
