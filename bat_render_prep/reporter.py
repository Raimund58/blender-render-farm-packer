# SPDX-License-Identifier: GPL-3.0-or-later
"""Bridge between BAT's `BATPackReporter` Protocol and the add-on UI.

BAT calls these callbacks from the main thread (we only ever drive its
`step()` from a Blender modal timer), so we can safely poke at Scene
properties here. We still tag areas for redraw to keep the panel live.
"""

from __future__ import annotations

import logging
from pathlib import Path, PurePath
from typing import TYPE_CHECKING

import bpy

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)


class BlenderReporter:
    """Implements `blender_asset_tracer.pack.BATPackReporter`.

    We don't inherit explicitly — BAT uses `typing.Protocol` so duck typing
    is enough. Inheriting would couple our import time to BAT being
    installed.
    """

    def __init__(self, scene: bpy.types.Scene) -> None:
        self._scene = scene
        self.errors: list[str] = []
        self.missing: list[str] = []
        self._copy_total_seen = 0

    # ---- helpers -----------------------------------------------------------
    def _props(self):
        return self._scene.bat_pack

    def _set_status(self, text: str) -> None:
        props = self._props()
        # Truncate long paths so the panel stays readable.
        if len(text) > 96:
            text = "…" + text[-95:]
        props.status_text = text
        _tag_redraw()

    # ---- BATPackReporter -- copy events ------------------------------------
    def on_copy_start(self, src: Path, dest: PurePath) -> None:
        log.info("copy start: %s -> %s", src, dest)
        self._set_status(f"Copying: {src.name}")

    def on_copy_done(self, src: Path, dest: PurePath) -> None:
        log.info("copy done: %s", dest)
        props = self._props()
        props.progress_done += 1
        if props.progress_total > 0:
            props.progress = min(
                1.0, props.progress_done / max(1, props.progress_total)
            )
        _tag_redraw()

    def on_copy_error(self, src: Path, dest: PurePath, errormsg: str) -> None:
        msg = f"Copy failed: {src} -> {dest}: {errormsg}"
        log.error(msg)
        self.errors.append(msg)
        self._props().last_error_count = len(self.errors)
        _tag_redraw()

    # ---- BATPackReporter -- rewrite events ---------------------------------
    def on_rewrite_start(self, blendfile: Path, save_to: Path) -> None:
        log.info("rewrite start: %s", blendfile)
        self._set_status(f"Rewriting: {blendfile.name}")

    def on_rewrite_done(self, blendfile: Path, save_to: Path) -> None:
        log.info("rewrite done: %s", save_to)

    def on_rewrite_error(
        self, blendfile: Path, save_to: Path, errormsg: str
    ) -> None:
        msg = f"Rewrite failed: {blendfile}: {errormsg}"
        log.error(msg)
        self.errors.append(msg)
        self._props().last_error_count = len(self.errors)
        _tag_redraw()

    # ---- BATPackReporter -- misc -------------------------------------------
    def on_missing_file(self, blendfile: Path, relpath_in_pack: PurePath) -> None:
        msg = f"Missing file referenced by {blendfile}: {relpath_in_pack}"
        log.warning(msg)
        self.missing.append(msg)
        _tag_redraw()

    def on_error_on_error(self, message: str, exception: Exception) -> None:
        msg = f"Reporter error: {message}: {exception!r}"
        log.error(msg)
        self.errors.append(msg)
        self._props().last_error_count = len(self.errors)
        _tag_redraw()


def _tag_redraw() -> None:
    """Mark Properties editors for redraw so progress updates are visible."""
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "PROPERTIES":
                    area.tag_redraw()
    except Exception:
        pass
