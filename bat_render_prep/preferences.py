# SPDX-License-Identifier: GPL-3.0-or-later
"""Add-on preferences: BAT version pin and install/uninstall buttons."""

from __future__ import annotations

import bpy
from bpy.props import StringProperty
from bpy.types import AddonPreferences

from . import deps


class BAT_AddonPreferences(AddonPreferences):
    bl_idname = __package__

    version_spec: StringProperty(  # type: ignore[valid-type]
        name="Version",
        description=(
            "Version of the blender-asset-tracer package to install. "
            "Examples: '2.0.5' (exact), '==2.0.5', '>=2.0.5,<3' (range), "
            "or leave empty for the latest release. "
            "The default pins to the v2 line."
        ),
        default=deps.DEFAULT_VERSION_SPEC,
    )

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

        box = layout.box()
        box.label(text="Blender Asset Tracer (BAT v2)", icon="PACKAGE")

        installed = deps.installed_version()
        row = box.row()
        if installed:
            row.label(text=f"Installed: {installed}", icon="CHECKMARK")
        else:
            row.label(text="Not installed", icon="ERROR")

        col = box.column(align=True)
        col.prop(self, "version_spec")
        hint = box.column()
        hint.scale_y = 0.85
        hint.label(
            text="Examples: 2.0.5 • ==2.0.5 • >=2.0.5,<3 • (empty = latest)",
            icon="INFO",
        )

        row = box.row(align=True)
        row.operator(
            "bat_pack.install_dependency",
            text="Install / Update BAT",
            icon="IMPORT",
        )
        op = row.operator(
            "bat_pack.uninstall_dependency",
            text="Uninstall",
            icon="TRASH",
        )
        row = box.row()
        row.operator(
            "bat_pack.open_install_folder",
            text="Open Install Folder",
            icon="FILE_FOLDER",
        )

        info = box.column()
        info.scale_y = 0.85
        info.label(
            text="BAT is installed into a per-user folder, no admin rights needed.",
            icon="INFO",
        )
        info.label(
            text=f"Target: {deps.user_site_dir()}",
        )
