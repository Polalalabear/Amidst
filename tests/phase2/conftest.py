"""Probe optional host capabilities without weakening integration assertions."""

import errno
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def node_with_typescript(tmp_path_factory: pytest.TempPathFactory) -> str:
    executable = shutil.which("node")
    if executable is None:
        pytest.skip("Node with native TypeScript imports is required")
    probe = tmp_path_factory.mktemp("node_typescript") / "capability.ts"
    probe.write_text("export const value: number = 1;\n", encoding="utf-8")
    script = ("const m=await import(" + json.dumps(probe.as_uri())
              + ");if(m.value!==1)process.exit(1);")
    try:
        result = subprocess.run(
            [executable, "--input-type=module", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        pytest.skip("Node native TypeScript import capability is unavailable")
    if result.returncode:
        pytest.skip("Installed Node does not support native TypeScript imports")
    return executable


@pytest.fixture
def symlink_file() -> Callable[[Path, Path], None]:
    def create(source: Path, link: Path) -> None:
        try:
            link.symlink_to(source)
        except NotImplementedError:
            pytest.skip("Host does not implement file symlinks")
        except OSError as error:
            if error.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
                pytest.skip("Host/filesystem does not permit file symlinks")
            raise
    return create
