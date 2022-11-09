import logging
import os
import os.path
import subprocess
from pathlib import Path
from typing import Any, ClassVar

from pcdsutils.qt import DesignerDisplay
from qtpy.QtWidgets import (QAction, QFileDialog, QLabel, QListWidget,
                            QListWidgetItem, QMainWindow, QTableWidget,
                            QTableWidgetItem, QWidget)

from .ftp_data import download_file_json_dict, list_file_info, upload_filename

DEFAULT_HOSTNAMES = [
    'plc-tst-motion',
    'plc-tst-pmps-subsystem-a',
    'plc-tst-pmps-subsystem-b',
]
logger = logging.getLogger(__name__)


class PMPSManagerGui(QMainWindow):
    def __init__(self, plc_hostnames: list[str]):
        super().__init__()
        if not plc_hostnames:
            plc_hostnames = DEFAULT_HOSTNAMES
        self.plc_hostnames = plc_hostnames
        self.tables = SummaryTables(plc_hostnames=plc_hostnames)
        self.setCentralWidget(self.tables)
        self.setup_menu_options()

    def setup_menu_options(self):
        menu = self.menuBar()
        file_menu = menu.addMenu('&File')
        upload_menu = file_menu.addMenu('&Upload to')
        download_menu = file_menu.addMenu('&Download from')
        # Actions will be garbage collected if we drop this reference
        self.actions = []
        for plc in self.plc_hostnames:
            upload_action = QAction()
            upload_action.setText(plc)
            upload_menu.addAction(upload_action)
            download_action = QAction(plc)
            download_action.setText(plc)
            download_menu.addAction(download_action)
            self.actions.append(upload_action)
            self.actions.append(download_action)
        upload_menu.triggered.connect(self.upload_to)
        download_menu.triggered.connect(self.download_from)
        self.setMenuWidget(menu)

    def upload_to(self, action: QAction):
        hostname = action.text()
        logger.debug('%s upload action', hostname)
        # Show file browser on local host
        filename, _ = QFileDialog.getOpenFileName(
            self,
            'Select file',
            os.getcwd(),
            "(*.json)",
        )
        if not filename or not os.path.exists(filename):
            logger.error('%s does not exist, aborting.', filename)
            return
        logger.debug('Uploading %s to %s', filename, hostname)
        try:
            upload_filename(
                hostname=hostname,
                filename=filename,
            )
        except Exception:
            logger.error('Failed to upload %s to %s', filename, hostname)
            logger.debug('', exc_info=True)
        self.tables.update_plc_row_by_hostname(hostname)

    def download_from(self, action: QAction):
        hostname = action.text()
        logger.debug('%s download action', hostname)


class SummaryTables(DesignerDisplay, QWidget):
    filename = Path(__file__).parent / 'tables.ui'

    title_label: QLabel
    plc_label: QLabel
    plc_table: QTableWidget
    device_label: QLabel
    device_list: QListWidget
    param_label: QLabel
    param_table: QTableWidget

    plc_columns: ClassVar[list[str]] = [
        'plc name',
        'status',
        'file last uploaded',
    ]
    param_dict: dict[str, dict[str, Any]]
    plc_row_map: dict[str, int]

    def __init__(self, plc_hostnames: list[str]):
        super().__init__()
        self.setup_table_columns()
        self.plc_row_map = {}
        for hostname in plc_hostnames:
            logger.debug('Adding %s', hostname)
            self.add_plc(hostname)
        self.plc_table.resizeColumnsToContents()
        self.plc_table.setFixedWidth(
            self.plc_table.horizontalHeader().length()
        )
        self.plc_table.cellActivated.connect(self.plc_selected)
        self.device_list.itemActivated.connect(self.device_selected)

    def setup_table_columns(self):
        """
        Set the column headers on the plc and parameter tables.
        """
        self.plc_table.setColumnCount(len(self.plc_columns))
        self.plc_table.setHorizontalHeaderLabels(self.plc_columns)

    def add_plc(self, hostname: str):
        """
        Add a PLC row in the table on the left.
        """
        row = self.plc_table.rowCount()
        self.plc_table.insertRow(row)
        name_item = QTableWidgetItem(hostname)
        status_item = QTableWidgetItem()
        upload_time_item = QTableWidgetItem()
        self.plc_table.setItem(row, 0, name_item)
        self.plc_table.setItem(row, 1, status_item)
        self.plc_table.setItem(row, 2, upload_time_item)
        self.update_plc_row(row)
        self.plc_row_map[hostname] = row

    def update_plc_row(self, row: int):
        """
        Update the status information in the PLC table for one row.
        """
        hostname = self.plc_table.item(row, 0).text()
        if check_server_online(hostname):
            text = 'online'
        else:
            text = 'offline'
        self.plc_table.item(row, 1).setText(text)
        try:
            info = list_file_info(hostname)
            logger.debug('%s found file info %s', hostname, info)
        except Exception:
            info = []
            logger.error('Could not read file list from %s', hostname)
            logger.debug('list_file_info(%s) failed', hostname, exc_info=True)
        text = 'no file found'
        filename = hostname_to_filename(hostname)
        for file_info in info:
            if file_info.filename == filename:
                text = file_info.create_time.ctime()
                break
        self.plc_table.item(row, 2).setText(text)

    def update_plc_row_by_hostname(self, hostname: str):
        """
        Update the status information in the PLC table for one hostname.
        """
        return self.update_plc_row(self.plc_row_map[hostname])

    def fill_device_list(self, hostname: str):
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

    def fill_parameter_table(self, device_name: str):
        """
        Use the cached db to show a single device's parameters in the table.
        """
        self.param_table.clear()
        self.param_table.setRowCount(0)
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
        first_values = list(device_params.values())[0]
        header = sorted(list(first_values))
        header.remove('name')
        header.insert(0, 'name')
        self.param_table.setColumnCount(len(header))
        self.param_table.setHorizontalHeaderLabels(header)

        for state_info in device_params.values():
            row = self.param_table.rowCount()
            self.param_table.insertRow(row)
            for key, value in state_info.items():
                col = header.index(key)
                item = QTableWidgetItem(value)
                self.param_table.setItem(row, col, item)
        self.param_table.resizeColumnsToContents()

    def plc_selected(self, row: int, col: int):
        """
        When a plc is selected, reset and seed the device list.
        """
        self.update_plc_row(row)
        hostname = self.plc_table.item(row, 0).text()
        self.fill_device_list(hostname)

    def device_selected(self, item: QListWidgetItem):
        """
        When a device is selected, reset and seed the parameter list.
        """
        self.fill_parameter_table(item.text())


def check_server_online(hostname: str):
    try:
        subprocess.run(
            ['ping', '-c', '1', hostname],
            capture_output=True,
        )
        return True
    except Exception:
        logger.debug('%s ping failed', hostname, exc_info=True)
        return False


def hostname_to_key(hostname: str):
    if hostname.startswith('plc-'):
        return hostname[4:]
    else:
        return hostname


def hostname_to_filename(hostname: str):
    return hostname_to_key(hostname) + '.json'
