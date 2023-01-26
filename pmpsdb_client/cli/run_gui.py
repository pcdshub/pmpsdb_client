"""
Module for running the included GUI in a QApplication
"""
import argparse
from pathlib import Path

from qtpy.QtWidgets import QApplication

from ..gui import PMPSManagerGui


def run_gui(args: argparse.Namespace) -> int:
    """
    Run the gui application.

    This shows a PLC database diagnostics and allows us to deploy database
    updates to the PLCs.
    """
    configs = args.config or []
    if args.tst:
        configs.append(get_included_config('tst'))
    if any((args.lfe, args.lfe_all, args.all_prod)):
        configs.append(get_included_config('lfe'))
    if any((args.kfe, args.tmo, args.rix, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('kfe'))
    if any((args.tmo, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('tmo'))
    if any((args.rix, args.kfe_all, args.all_prod)):
        configs.append(get_included_config('rix'))
    app = QApplication([])
    gui = PMPSManagerGui(configs=configs)
    gui.show()
    return app.exec()


def get_included_config(name: str) -> str:
    return str(Path(__file__).parent.parent / f'pmpsdb_{name}.yml')
