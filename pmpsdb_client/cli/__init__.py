"""
Module to define the command-line interface for pmpsdb database management.

Once installed, this can be invoked simply by using the ``pmpsdb`` command.
It can also be run via ``python -m pmpsdb`` from the repository root if you
have not or cannot install it.
"""
import argparse
import logging

from .parser import create_parser

logger = logging.getLogger(__name__)


def entrypoint() -> int:
    """
    This is the function called when you run ``pmpsdb``
    """
    return main(create_parser().parse_args())


def main(args: argparse.Namespace) -> int:
    """
    Given some arguments, run the command-line program.

    This outer function exists only to handle uncaught exceptions.
    """
    try:
        return _main(args)
    except Exception as exc:
        if args.verbose:
            raise
        print(exc)
        return 1


def _main(args: argparse.Namespace) -> int:
    """
    Given some arguments, run the command-line program.

    This inner function does some setup and then defers to the more specific
    helper function as needed.
    """
    if args.version:
        from ..version import version
        print(version)
        return 0
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)s: %(name)s %(message)s",
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(levelname)s: %(message)s',
        )
        # Noisy log messages from ssh transport layer
        for module in ("fabric", "paramiko", "intake"):
            logging.getLogger(module).setLevel(logging.WARNING)
    if args.export_dir:
        from ..export_data import set_export_dir
        set_export_dir(args.export_dir)
    if args.subparser == 'gui':
        from .run_gui import run_gui
        return run_gui(args)
    if args.subparser == 'list-files':
        from .transfer_tools import cli_list_files
        return cli_list_files(args)
    if args.subparser == 'upload-to':
        from .transfer_tools import cli_upload_file
        return cli_upload_file(args)
    if args.subparser == 'download-from':
        from .transfer_tools import cli_download_file
        return cli_download_file(args)
    if args.subparser == 'compare':
        from .transfer_tools import cli_compare_file
        return cli_compare_file(args)
    if args.subparser == 'reload':
        from .epics_tools import cli_reload_parameters
        return cli_reload_parameters(args)
    return 1
