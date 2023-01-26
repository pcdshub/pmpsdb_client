"""
CLI entry points that involve EPICS
"""
import argparse
import logging
import re
import threading
import time
from pathlib import Path

import yaml

from ..ioc_data import PLCDBControls

logger = logging.getLogger(__name__)
CONFIG_RE = re.compile(r'^pmpsdb_.*.yml$')


def cli_reload_parameters(args: argparse.Namespace) -> int:
    hostname = args.hostname
    configs = load_all_configs()
    try:
        prefix = configs[hostname]
    except KeyError:
        logger.error('No entry for %s in config', hostname)
        return 1
    controls = PLCDBControls(prefix, name=hostname)
    try:
        controls.wait_for_connection()
    except Exception:
        logger.error(
            'Could not connect to refresh PVs %s and %s',
            controls.refresh.pvname,
            controls.last_refresh.pvname,
        )
        return 1
    logger.info(
        'Last file reload was at: %s',
        time.ctime(controls.last_refresh.get())
    )

    if not args.no_wait:
        ev = threading.Event()

        def set_flag(*args, **kwargs):
            ev.set()

        controls.last_refresh.subscribe(set_flag)

    try:
        controls.refresh.put(1)
    except Exception:
        logger.error(
            'Unable to write to %s',
            controls.refresh.pvname,
        )
        return 1

    if not args.no_wait:
        try:
            ev.wait(5.0)
        except Exception:
            logger.error(
                'Timeout while waiting for %s to refresh',
                hostname,
            )
            return 1
        else:
            logger.info(
                'This file reloaded at: %s',
                time.ctime(controls.last_refresh.get())
            )
    return 0


def load_all_configs() -> dict[str, str]:
    """
    Check all the built-in configs to gather all of the PV prefixes.
    """
    configs = {}
    root_dir = Path(__file__).parent.parent
    for filename in root_dir.iterdir():
        if CONFIG_RE.match(filename) is not None:
            with open(filename) as fd:
                configs.update(yaml.load(fd))
    return configs
