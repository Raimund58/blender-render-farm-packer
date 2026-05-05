# SPDX-License-Identifier: GPL-3.0-or-later
"""BAT Render Farm Packer.

A lightweight Blender 5.1+ add-on that prepares projects for render farms
by driving Blender Asset Tracer v2 (BAT v2) directly through its Python API.

BAT itself is not bundled. The add-on installs the official
`blender-asset-tracer` package from PyPI into a per-user site directory on
demand, so updates require no add-on changes.
"""

from __future__ import annotations

import bpy

# ---- Hard compatibility guard ------------------------------------------------
#
# BAT v2 requires Blender 5.1 or newer (it relies on
# bpy.data.libraries.file_path_map and friends, only available there).
# We fail loudly on register() rather than silently misbehaving.
MIN_BLENDER_VERSION = (5, 1, 0)


from . import deps, ops_install, ops_pack, preferences, properties, ui  # noqa: E402


_classes = (
    preferences.BAT_AddonPreferences,
    properties.BAT_ExcludeGlob,
    properties.BAT_PackProperties,
    ops_install.BAT_OT_install_dependency,
    ops_install.BAT_OT_uninstall_dependency,
    ops_install.BAT_OT_open_install_folder,
    ops_pack.BAT_OT_glob_add,
    ops_pack.BAT_OT_glob_remove,
    ops_pack.BAT_OT_list_deps,
    ops_pack.BAT_OT_pack,
    ops_pack.BAT_OT_cancel_pack,
    ui.RENDER_PT_bat_pack,
    ui.RENDER_PT_bat_pack_options,
    ui.RENDER_PT_bat_pack_excludes,
)


def register() -> None:
    if bpy.app.version < MIN_BLENDER_VERSION:
        raise RuntimeError(
            "BAT Render Farm Packer requires Blender "
            f"{'.'.join(str(v) for v in MIN_BLENDER_VERSION)} or newer "
            f"(detected {'.'.join(str(v) for v in bpy.app.version)}). "
            "BAT v2 itself does not support older Blender versions."
        )

    for cls in _classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.bat_pack = bpy.props.PointerProperty(
        type=properties.BAT_PackProperties,
        name="BAT Pack Settings",
    )

    # Make sure the per-user site dir is on sys.path early, so `import
    # blender_asset_tracer` works without further user action if BAT was
    # installed in a previous session.
    deps.add_user_site_to_path()


def unregister() -> None:
    # Tear down any in-flight pack first.
    try:
        ops_pack.force_cleanup()
    except Exception:  # pragma: no cover - defensive
        pass

    if hasattr(bpy.types.Scene, "bat_pack"):
        del bpy.types.Scene.bat_pack

    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:  # pragma: no cover - defensive
            pass


if __name__ == "__main__":
    register()
