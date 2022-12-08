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
        self._version = None

    @property
    def data(self):
        if self._version is None:
            # Checking for directory is faster than failing out of get_version
            if (Path(__file__).parent.parent / '.git').exists():
                try:
                    # Git checkout
                    from setuptools_scm import get_version
                    self._version = get_version(root="..", relative_to=__file__)
                    return self._version
                except (ImportError, LookupError):
                    ...
            # Check this second because it can exist in a git repo if we've
            # done a build at least once.
            try:
                from ._version import version  # noqa: F401
                self._version = version
            except ImportError:
                # I don't know how this can happen but let's be prepared
                self._version = '0.0.unknown'
        return self._version


__version__ = version = VersionProxy()
