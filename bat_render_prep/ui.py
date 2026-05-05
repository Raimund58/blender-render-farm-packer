# SPDX-License-Identifier: GPL-3.0-or-later
"""UI panels in the Output Properties tab."""

from __future__ import annotations

import bpy
from bpy.types import Panel, UIList

from . import deps


class RENDER_PT_bat_pack(Panel):
    """Top-level panel: status + main actions."""

    bl_label = "BAT Render Farm Packer"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        props = scene.bat_pack

        # ---- Status ---------------------------------------------------------
        installed = deps.installed_version()
        status_box = layout.box()
        row = status_box.row()
        if installed:
            row.label(text=f"BAT v{installed}", icon="CHECKMARK")
        else:
            row.label(text="BAT not installed", icon="ERROR")
            row = status_box.row()
            row.label(
                text="Open Preferences > Add-ons > BAT Render Farm Packer to install.",
                icon="INFO",
            )

        if not bpy.data.filepath:
            row = status_box.row()
            row.label(text="Save the .blend file before packing.", icon="ERROR")

        # ---- Paths ----------------------------------------------------------
        col = layout.column(align=True)
        col.prop(props, "project_root")
        col.prop(props, "pack_target")

        # ---- Actions --------------------------------------------------------
        col = layout.column(align=True)
        col.enabled = bool(installed) and not props.is_running

        row = col.row(align=True)
        row.scale_y = 1.3
        row.operator("bat_pack.pack", icon="PACKAGE")

        row = col.row(align=True)
        row.operator("bat_pack.list_deps", icon="FILE_TEXT")

        # ---- Running state --------------------------------------------------
        if props.is_running:
            run_box = layout.box()
            run_box.label(text="Packing…", icon="PLAY")
            sub = run_box.column(align=True)
            sub.prop(props, "progress", text="Progress", slider=True)
            sub.label(
                text=f"{props.progress_done} / {props.progress_total} files"
            )
            if props.status_text:
                sub.label(text=props.status_text)
            run_box.operator("bat_pack.cancel", icon="CANCEL")

        elif props.status_text:
            done_box = layout.box()
            icon = "CHECKMARK" if props.last_error_count == 0 else "ERROR"
            done_box.label(text=props.status_text, icon=icon)


class RENDER_PT_bat_pack_options(Panel):
    """Sub-panel: BAT options that map to file_usage.Options."""

    bl_label = "Options"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"
    bl_parent_id = "RENDER_PT_bat_pack"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        props = context.scene.bat_pack

        col = layout.column(align=True)
        col.prop(props, "use_relative_only")
        col.prop(props, "relocated_root")
        col.prop(props, "save_before_pack")
        col.prop(props, "post_action")
        col.prop(props, "log_level")


class RENDER_PT_bat_pack_excludes(Panel):
    """Sub-panel: exclude glob patterns (Options.ignore_globs)."""

    bl_label = "Exclude Patterns"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "output"
    bl_parent_id = "RENDER_PT_bat_pack"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        props = context.scene.bat_pack

        layout.label(
            text="Glob patterns matched against filenames (not full paths).",
            icon="INFO",
        )

        if not props.exclude_globs:
            layout.label(text="No exclude patterns. Click + to add one.")

        for i, item in enumerate(props.exclude_globs):
            row = layout.row(align=True)
            row.prop(item, "pattern", text="")
            op = row.operator("bat_pack.glob_remove", text="", icon="X")
            op.index = i

        row = layout.row(align=True)
        row.operator("bat_pack.glob_add", text="Add Pattern", icon="ADD")
