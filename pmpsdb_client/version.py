"""
Pick the version for use in __init__.py without polluting the namespace.

This is also useful in cli.py
"""
try:
    # Git checkout
    from setuptools_scm import get_version
    __version__ = get_version(root="..", relative_to=__file__)
except (ImportError, LookupError):
    # Installed package: check second as this might exist in checkout
    # This should be first if there is ever a non-hacky way to avoid
    # _version from being created in a dev checkout.
    from ._version import __version__  # noqa: F401
