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


def _drop_cached_modules() -> None:
    """Remove every cached blender_asset_tracer.* module from sys.modules.

    A previous install/uninstall may have left submodules cached. Without
    this, ``importlib.import_module`` re-uses the stale top-level package
    object and reports the *old* ``__version__`` even after a successful
    upgrade.
    """
    prefix = IMPORT_NAME
    for name in [m for m in list(sys.modules) if m == prefix or m.startswith(prefix + ".")]:
        sys.modules.pop(name, None)


def is_installed() -> bool:
    """Return whether BAT is installed in our per-user site directory.

    Uses the disk check (presence of the package directory or its
    dist-info) instead of attempting an import, so it stays correct right
    after install/uninstall, where import caches may still lag.
    """
    site_dir = user_site_dir()
    if not site_dir.exists():
        return False
    if (site_dir / IMPORT_NAME).is_dir():
        return True
    if any(site_dir.glob("blender_asset_tracer-*.dist-info")):
        return True
    if any(site_dir.glob("blender-asset-tracer-*.dist-info")):
        return True
    return False


def installed_version(*, force_reload: bool = False) -> str | None:
    """Return the installed BAT version string, or None if not installed.

    The version is read directly from the on-disk ``*.dist-info/METADATA``
    file in the per-user site directory. We deliberately do NOT import the
    package, because Blender keeps several import-machinery caches alive
    across an in-session pip install/upgrade, which makes the imported
    module's ``__version__`` lag behind what is actually on disk.

    The ``force_reload`` flag is accepted for API compatibility; with the
    metadata-based lookup it is a no-op (we always read fresh from disk).
    """
    del force_reload  # always fresh
    return _read_disk_version() or _read_imported_version()


def _read_disk_version() -> str | None:
    """Read BAT's version from the dist-info metadata in user_site_dir()."""
    site_dir = user_site_dir()
    if not site_dir.exists():
        return None

    # Pip writes ``<package>-<version>.dist-info`` (or .egg-info) when
    # installing with --target. The package distribution name is
    # ``blender_asset_tracer`` (underscores) per PEP 503 normalisation,
    # but pip preserves either form on disk depending on version. Match
    # both to be safe.
    candidates = list(site_dir.glob("blender_asset_tracer-*.dist-info")) + list(
        site_dir.glob("blender-asset-tracer-*.dist-info")
    )
    if not candidates:
        return None

    # If multiple are present (shouldn't be after --upgrade, but defensive)
    # take the one with the most recent mtime.
    dist_info = max(candidates, key=lambda p: p.stat().st_mtime)
    metadata = dist_info / "METADATA"
    if not metadata.is_file():
        return None

    try:
        with metadata.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if line.startswith("Version:"):
                    return line.split(":", 1)[1].strip()
                if not line.strip():
                    # End of header block.
                    break
    except OSError:
        return None
    return None


def _read_imported_version() -> str | None:
    """Last-resort fallback: import the package and read __version__."""
    add_user_site_to_path()
    try:
        import importlib

        _drop_cached_modules()
        importlib.invalidate_caches()
        mod = importlib.import_module(IMPORT_NAME)
        return getattr(mod, "__version__", None)
    except Exception:
        return None


def format_install_target(spec: str) -> str:
    """Render a user-friendly description of what we're about to install.

    Examples::

        ''             -> 'blender-asset-tracer (latest)'
        '2.0.1'        -> 'blender-asset-tracer 2.0.1'
        '==2.0.1'      -> 'blender-asset-tracer ==2.0.1'
        '>=2.0.5,<3'   -> 'blender-asset-tracer >=2.0.5,<3'
    """
    spec = (spec or "").strip()
    if not spec:
        return f"{PACKAGE_NAME} (latest)"
    return f"{PACKAGE_NAME} {spec}"


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

    `version_spec` may be:
      * empty           -> latest release
      * a bare version  -> e.g. ``2.0.1`` (treated as ``==2.0.1``)
      * a PEP 440 spec  -> e.g. ``>=2.0.5,<3``, ``==2.0.*``

    Returns (success, log_text).
    """
    spec = (version_spec or "").strip()
    normalised = _normalise_version_spec(spec)
    if normalised is None:
        return False, (
            f"Invalid version specifier: {spec!r}.\n"
            "Examples: '2.0.5', '==2.0.5', '>=2.0.5,<3', or empty for the latest release."
        )

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
    args.append(f"{PACKAGE_NAME}{normalised}")

    proc = _run_pip(args)
    output = (proc.stdout or "") + (proc.stderr or "")
    success = proc.returncode == 0
    if success:
        # Refresh import path & caches so a subsequent import sees the
        # freshly installed package. We must drop EVERY cached submodule;
        # otherwise the previously-imported top-level package keeps its
        # old __version__ even after the new wheel landed on disk.
        add_user_site_to_path()
        try:
            import importlib

            _drop_cached_modules()
            importlib.invalidate_caches()
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

    any_failed = False
    for child in site_dir.iterdir():
        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            output_lines.append(f"Removed {child.name}")
        except Exception as ex:
            any_failed = True
            output_lines.append(f"Failed to remove {child.name}: {ex}")

    # Drop cached modules so the next import re-resolves.
    _drop_cached_modules()

    log_text = "\n".join(output_lines) or "Cleared install directory."
    return (not any_failed), log_text


# PEP 440 comparison operators that may legally start a specifier.
_SPEC_OPERATORS = ("==", "!=", "~=", ">=", "<=", ">", "<", "===")


def _normalise_version_spec(spec: str) -> str | None:
    """Validate and normalise a user-supplied version spec for pip.

    Returns the normalised spec (e.g. ``''``, ``'==2.0.1'``, ``'>=2.0.5,<3'``)
    or None if the input is not a recognisable PEP 440 specifier.
    """
    spec = (spec or "").strip()
    if not spec:
        return ""

    # If the user typed a bare version like ``2.0.1`` (no operator),
    # interpret it as an exact pin. This is the common-case mistake.
    if not spec.startswith(_SPEC_OPERATORS) and spec[0].isdigit():
        spec = f"=={spec}"

    # Prefer the standard `packaging` library when available (Blender 5.x
    # bundles it via pip's vendored copy at minimum, and it is widely
    # installed). Fall back to a permissive structural check.
    try:
        from packaging.specifiers import SpecifierSet  # type: ignore[import-not-found]
    except Exception:
        # Fallback: accept any string that begins with a known operator.
        if spec.startswith(_SPEC_OPERATORS):
            return spec
        return None

    # Validate the spec directly via SpecifierSet. We do NOT prepend the
    # package name and parse as a Requirement, because Requirement happily
    # absorbs garbage suffixes (e.g. ``blender-asset-tracerbanana``) into
    # the project name and returns an empty specifier set, masking errors.
    try:
        sset = SpecifierSet(spec)
    except Exception:
        return None
    if not list(sset):
        # No specifiers parsed out -> input was not actually a spec.
        return None
    return str(sset)
