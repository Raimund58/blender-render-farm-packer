# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators that install / uninstall the BAT package."""

from __future__ import annotations

import logging
import subprocess
import sys

import bpy
from bpy.types import Operator

from . import deps

log = logging.getLogger(__name__)


def _addon_prefs(context: bpy.types.Context):
    return context.preferences.addons[__package__].preferences


def _redraw_all() -> None:
    """Force a redraw of editors that show our status.

    The preferences window draws ``BAT_AddonPreferences`` and the
    Properties editor draws our Output panel. Without an explicit
    ``tag_redraw`` they keep showing the previous state until the user
    interacts with them again, which makes Install / Uninstall feel
    broken.
    """
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type in {"PREFERENCES", "PROPERTIES"}:
                    area.tag_redraw()
    except Exception:
        pass


class BAT_OT_install_dependency(Operator):
    """Install or update the blender-asset-tracer package from PyPI."""

    bl_idname = "bat_pack.install_dependency"
    bl_label = "Install / Update BAT"
    bl_description = (
        "Download the blender-asset-tracer package from PyPI and install it "
        "into the per-user site directory. Requires network access"
    )
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        prefs = _addon_prefs(context)
        spec = (prefs.version_spec or "").strip()
        pretty = deps.format_install_target(spec)
        self.report({"INFO"}, f"Installing {pretty}\u2026")

        success, output = deps.install(spec, upgrade=True)

        for line in output.splitlines()[-12:]:
            log.info("pip: %s", line)

        if not success:
            self.report({"ERROR"}, "BAT install failed \u2014 see system console")
            print("---- pip output (BAT install) ----")
            print(output)
            print("---- end pip output ----")
            return {"CANCELLED"}

        version = deps.installed_version(force_reload=True) or "unknown"
        self.report({"INFO"}, f"BAT {version} installed")
        _redraw_all()
        return {"FINISHED"}


class BAT_OT_uninstall_dependency(Operator):
    """Remove the per-user BAT installation."""

    bl_idname = "bat_pack.uninstall_dependency"
    bl_label = "Uninstall BAT"
    bl_description = "Remove the blender-asset-tracer package from the per-user site directory"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        success, output = deps.uninstall()
        for line in output.splitlines():
            log.info("uninstall: %s", line)
        if not success:
            self.report({"ERROR"}, "Uninstall failed \u2014 see system console")
            _redraw_all()
            return {"CANCELLED"}
        self.report({"INFO"}, "BAT uninstalled")
        _redraw_all()
        return {"FINISHED"}


class BAT_OT_open_install_folder(Operator):
    """Open the per-user BAT install folder in the system file browser."""

    bl_idname = "bat_pack.open_install_folder"
    bl_label = "Open Install Folder"
    bl_description = "Open the directory where BAT is installed"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        path = str(deps.user_site_dir())
        try:
            if sys.platform.startswith("win"):
                import os

                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as ex:
            self.report({"ERROR"}, f"Could not open folder: {ex}")
            return {"CANCELLED"}
        return {"FINISHED"}
