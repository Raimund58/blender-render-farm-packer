# SPDX-License-Identifier: GPL-3.0-or-later
"""Dependency management: install / locate the `blender-asset-tracer` package.

We do **not** vendor BAT. Instead we install it from PyPI into a per-user
site directory under Blender's user-resource scripts folder. Two reasons:

1. BAT moves quickly; pinning a version in the add-on is hostile to users.
2. Installing into Blender's bundled site-packages would require admin
   permissions on most systems and would be wiped on Blender update.

The directory we use is::

    <user scripts>/bat_site

We add that to ``sys.path`` via ``site.addsitedir`` so that ``import
blender_asset_tracer`` works.
"""

from __future__ import annotations

import logging
import re
import site
import subprocess
import sys
from pathlib import Path

import bpy

log = logging.getLogger(__name__)

# Default version specifier. BAT 2.0.5 is the first published v2 release.
# We allow patch and minor updates within the v2 line.
DEFAULT_VERSION_SPEC = ">=2.0.5,<3"

PACKAGE_NAME = "blender-asset-tracer"
IMPORT_NAME = "blender_asset_tracer"


def user_site_dir() -> Path:
    """Return the per-user directory we install BAT into."""
    base = Path(bpy.utils.user_resource("SCRIPTS", create=True))
    site_dir = base / "bat_site"
    site_dir.mkdir(parents=True, exist_ok=True)
    return site_dir


def add_user_site_to_path() -> None:
    """Make our user-site dir importable by Blender's Python."""
    site_dir = str(user_site_dir())
    if site_dir not in sys.path:
        site.addsitedir(site_dir)


def is_installed() -> bool:
    add_user_site_to_path()
    try:
        import importlib

        importlib.invalidate_caches()
        importlib.import_module(IMPORT_NAME)
    except Exception:
        return False
    return True


def installed_version() -> str | None:
    """Return the installed BAT version string, or None."""
    add_user_site_to_path()
    try:
        import importlib

        importlib.invalidate_caches()
        mod = importlib.import_module(IMPORT_NAME)
        return getattr(mod, "__version__", None)
    except Exception:
        return None


def python_executable() -> str:
    """Return the Python interpreter Blender is currently running.

    On Blender 5.x this is the bundled Python 3.13.
    """
    # sys.executable inside Blender is the Blender executable itself.
    # bpy.app.binary_path_python was removed long ago. Use sys._base_executable
    # if available, otherwise fall back to looking up python in Blender's
    # python folder.
    py = getattr(sys, "_base_executable", None)
    if py and Path(py).exists() and "python" in Path(py).name.lower():
        return py

    # Fall back: look for Blender's bundled python next to sys.prefix.
    prefix = Path(sys.prefix)
    candidates = [
        prefix / "bin" / "python3.13",
        prefix / "bin" / "python3",
        prefix / "bin" / "python",
        prefix / "python.exe",
        prefix / "bin" / "python.exe",
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # Last resort: rely on sys.executable which may be the Blender binary.
    # The `-m pip` invocation will still work because Blender forwards -m to
    # its bundled Python in recent versions, but this is fragile.
    return sys.executable


def _run_pip(args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [python_executable(), "-m", "pip", *args]
    log.info("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )


def install(version_spec: str = DEFAULT_VERSION_SPEC, *, upgrade: bool = True) -> tuple[bool, str]:
    """Install or upgrade BAT into the user-site dir.

    Returns (success, log_text).
    """
    if not _valid_version_spec(version_spec):
        return False, f"Invalid version specifier: {version_spec!r}"

    target = str(user_site_dir())
    args = [
        "install",
        "--target",
        target,
        "--no-warn-script-location",
        "--disable-pip-version-check",
    ]
    if upgrade:
        args.append("--upgrade")
    args.append(f"{PACKAGE_NAME}{version_spec}")

    proc = _run_pip(args)
    output = (proc.stdout or "") + (proc.stderr or "")
    success = proc.returncode == 0
    if success:
        # Refresh import path & caches so a subsequent import sees the
        # freshly installed package.
        add_user_site_to_path()
        try:
            import importlib

            importlib.invalidate_caches()
            if IMPORT_NAME in sys.modules:
                del sys.modules[IMPORT_NAME]
        except Exception:
            pass
    return success, output


def uninstall() -> tuple[bool, str]:
    """Remove BAT from the user-site dir.

    pip uninstall does not work with --target installs, so we just delete
    the directory contents.
    """
    import shutil

    site_dir = user_site_dir()
    output_lines = []
    if not site_dir.exists():
        return True, "Nothing to remove."

    for child in site_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            output_lines.append(f"Removed {child.name}")
        except Exception as ex:
            output_lines.append(f"Failed to remove {child.name}: {ex}")

    # Drop cached module so the next import re-resolves.
    if IMPORT_NAME in sys.modules:
        del sys.modules[IMPORT_NAME]

    return True, "\n".join(output_lines) or "Cleared install directory."


_VERSION_SPEC_RE = re.compile(
    r"^\s*(==|>=|<=|>|<|~=|!=)?\s*\d+(\.\d+){0,2}([a-zA-Z0-9.+-]*)\s*"
    r"(,\s*(==|>=|<=|>|<|~=|!=)\s*\d+(\.\d+){0,2}([a-zA-Z0-9.+-]*)\s*)*$"
)


def _valid_version_spec(spec: str) -> bool:
    if not spec:
        # Empty means "latest".
        return True
    return bool(_VERSION_SPEC_RE.match(spec))
