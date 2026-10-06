"""Regular local file reads with host-supported nonblocking and binary flags."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from io import BufferedReader
from pathlib import Path


@contextmanager
def open_regular_file(path: Path) -> Iterator[BufferedReader]:
    """Allow regular symlinks, rejecting special inputs before and after open."""
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("experiment inputs must be regular files")
    # Nonblocking protects a FIFO replacement race on platforms supporting it.
    # Binary mode preserves exact bytes on Windows. Independently recheck the
    # opened descriptor instead of trusting the pathname's earlier stat.
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("experiment inputs must be regular files")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            if not isinstance(stream, BufferedReader):
                raise ValueError("experiment inputs require a buffered binary file")
            yield stream
    finally:
        os.close(descriptor)
