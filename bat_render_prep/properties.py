# SPDX-License-Identifier: GPL-3.0-or-later
"""Property definitions exposed in the UI and consumed by the operators."""

from __future__ import annotations

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    IntProperty,
    StringProperty,
)
from bpy.types import PropertyGroup


class BAT_ExcludeGlob(PropertyGroup):
    """A single glob pattern used to exclude files (e.g. '*.abc')."""

    pattern: StringProperty(  # type: ignore[valid-type]
        name="Pattern",
        description="Glob pattern matched against filenames (not full paths). "
        "Examples: *.abc, *.bphys",
        default="",
    )


_POST_ACTION_ITEMS = (
    ("NOTHING", "Do Nothing", "Leave the pack folder as-is"),
    ("OPEN", "Open Folder", "Open the pack folder in the system file browser"),
    ("ZIP", "Create Zip Archive", "Zip the pack folder next to itself"),
)

_LOG_LEVEL_ITEMS = (
    ("WARNING", "Warning", "Only warnings and errors"),
    ("INFO", "Info", "Informational messages"),
    ("DEBUG", "Debug", "Verbose debug logging"),
)


class BAT_PackProperties(PropertyGroup):
    """Settings attached to the Scene as `scene.bat_pack`."""

    # ---- Paths -------------------------------------------------------------
    project_root: StringProperty(  # type: ignore[valid-type]
        name="Project Root",
        description="Root directory of the project. Files outside this root "
        "are relocated under the 'Relocated Root' inside the pack. "
        "Leave empty to use the folder of the current .blend file",
        default="",
        subtype="DIR_PATH",
    )

    pack_target: StringProperty(  # type: ignore[valid-type]
        name="Pack Target",
        description="Destination directory for the BAT pack",
        default="",
        subtype="DIR_PATH",
    )

    # ---- BAT options (mirroring file_usage.Options) ------------------------
    use_relative_only: BoolProperty(  # type: ignore[valid-type]
        name="Relative Paths Only",
        description="Only include dependencies that are referenced by a "
        "relative path. Blend files are always included regardless",
        default=False,
    )

    relocated_root: StringProperty(  # type: ignore[valid-type]
        name="Relocated Root",
        description="Sub-directory inside the pack used for files that live "
        "outside the project root",
        default="_outside_project",
    )

    exclude_globs: CollectionProperty(  # type: ignore[valid-type]
        name="Exclude Globs",
        type=BAT_ExcludeGlob,
    )
    exclude_globs_index: IntProperty(default=0)

    # ---- Behaviour ---------------------------------------------------------
    save_before_pack: BoolProperty(  # type: ignore[valid-type]
        name="Save Before Packing",
        description="Save the current .blend file before packing (recommended)",
        default=True,
    )

    post_action: EnumProperty(  # type: ignore[valid-type]
        name="After Packing",
        description="What to do once the pack finishes successfully",
        items=_POST_ACTION_ITEMS,
        default="NOTHING",
    )

    log_level: EnumProperty(  # type: ignore[valid-type]
        name="Log Level",
        description="Logging verbosity for the blender_asset_tracer module",
        items=_LOG_LEVEL_ITEMS,
        default="INFO",
    )

    # ---- Runtime state (read-only from UI) ---------------------------------
    is_running: BoolProperty(default=False)
    progress_total: IntProperty(default=0)
    progress_done: IntProperty(default=0)
    progress: FloatProperty(default=0.0, min=0.0, max=1.0, subtype="FACTOR")
    status_text: StringProperty(default="")
    last_error_count: IntProperty(default=0)
    cancel_requested: BoolProperty(default=False)
