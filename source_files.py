"""Detect changed or unavailable inputs before reusing reviewed page settings."""
from pathlib import Path
import stat


class SourceFileError(ValueError):
    pass


def checked_version(path, expected=None):
    try:
        info = Path(path).stat()
        if not stat.S_ISREG(info.st_mode):
            raise SourceFileError("Choose a file, not a folder.")
    except FileNotFoundError:
        raise SourceFileError("File is missing or moved. Select it again.") from None
    except OSError:
        raise SourceFileError("Cannot access this file. Check its location and permissions.") from None
    version = (info.st_size, info.st_mtime_ns, info.st_ino)
    if expected is not None and tuple(expected) != version:
        raise SourceFileError(
            "This file changed. Use Replace to select it again and review its new contents."
        )
    return version


def source_errors(files, versions):
    errors = {}
    for index, path in enumerate(files):
        try:
            checked_version(path, versions.get(path))
        except SourceFileError as error:
            errors[index] = str(error)
    return errors
