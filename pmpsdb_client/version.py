"""
Experimental version handling.

1. Pick the version for use in __init__.py and cli.py without polluting the namespace.
2. Defer evaluation of the version until it is checked to save 0.3s on import
3. Use the git version in a git checkout and _version otherwise.
"""
from collections import UserString
from pathlib import Path


class VersionProxy(UserString):
    def __init__(self):
        ...

    @property
    def data(self):
        global _VERSION
        if _VERSION is None:
            # Checking for directory is faster than failing out of get_version
            if (Path(__file__).parent.parent / '.git').exists():
                try:
                    # Git checkout
                    from setuptools_scm import get_version
                    _VERSION = get_version(root="..", relative_to=__file__)
                    return _VERSION
                except (ImportError, LookupError):
                    ...
            # Check this second because it can exist in a git repo if we've
            # done a build at least once.
            from ._version import __version__  # noqa: F401
            _VERSION = __version__
        return _VERSION


_VERSION = None
VERSION = VersionProxy()
