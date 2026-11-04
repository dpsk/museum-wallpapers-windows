"""Exclusive file locks that work across processes and threads, on Windows
(msvcrt) and POSIX (fcntl).

Each call opens its own handle, so two threads of one process exclude each
other just like two processes do: flock locks belong to the open file
description and Windows byte-range locks to the handle.
"""

import sys
import time
from pathlib import Path

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

POLL = 0.1


class FileLock:
    def __init__(self, handle):
        self._handle = handle

    def close(self):
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            if sys.platform == "win32":
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        finally:
            handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def __del__(self):
        self.close()


def _try_lock(handle):
    try:
        if sys.platform == "win32":
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (BlockingIOError, PermissionError):
        return False
    except OSError as exc:
        # msvcrt reports a held lock as EACCES or EDEADLOCK.
        if sys.platform == "win32" and exc.errno in (13, 36):
            return False
        raise


def acquire(path, wait=True, timeout=None):
    """Lock `path` exclusively; returns a FileLock (a context manager), or
    None when wait=False (or the timeout passed) and another holder has it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    deadline = None if timeout is None else time.monotonic() + timeout
    while not _try_lock(handle):
        if not wait or (deadline is not None and time.monotonic() >= deadline):
            handle.close()
            return None
        time.sleep(POLL)
    return FileLock(handle)
