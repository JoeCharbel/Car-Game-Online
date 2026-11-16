"""
Path helpers that work both from source and from a frozen PyInstaller build.

Assets (images) ship inside the build and are read-only, so they live in the
bundle. Anything the game writes (the score file) has to sit next to the exe
where the user can see it, not in the temporary extraction folder.
"""

import os
import sys

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _bundle_dir():
    """Folder holding the files that ship with the game."""
    # PyInstaller unpacks bundled data into _MEIPASS.
    return getattr(sys, "_MEIPASS", _BASE_DIR)


def _writable_dir():
    """Folder the game may write to."""
    if getattr(sys, "frozen", False):
        # In a frozen build __file__ points inside the bundle, so use the exe.
        return os.path.dirname(os.path.abspath(sys.executable))
    return _BASE_DIR


def resource_path(name):
    """Absolute path to a read-only asset (image, data file)."""
    return os.path.join(_bundle_dir(), name)


def writable_path(name):
    """Absolute path to a file the game saves at runtime."""
    return os.path.join(_writable_dir(), name)
