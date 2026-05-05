# SPDX-License-Identifier: GPL-3.0-or-later
"""The modal packing operator and the dependency-listing operator.

The pack operator follows BAT v2's `BATPacker` design: build it once, call
`start()`, then drive `step()` from a Blender modal timer until it reports
done. This keeps the UI responsive and lets the user cancel mid-run.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import bpy
from bpy.props import IntProperty, StringProperty
from bpy.types import Operator

from . import deps
from .reporter import BlenderReporter

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level state for the active modal pack.
# Only one pack can run at a time; that's a sensible UX simplification.
# ---------------------------------------------------------------------------
_active_packer = None  # type: ignore[var-annotated]
_active_reporter: BlenderReporter | None = None
_active_timer = None  # type: ignore[var-annotated]


def force_cleanup() -> None:
    """Tear down any in-flight pack. Used during unregister()."""
    global _active_packer, _active_reporter, _active_timer
    if _active_packer is not None:
        try:
            _active_packer.abort()
        except Exception:
            log.exception("Error aborting active BAT packer")
    _active_packer = None
    _active_reporter = None
    _active_timer = None


# ---------------------------------------------------------------------------
# Glob-list helpers
# ---------------------------------------------------------------------------
class BAT_OT_glob_add(Operator):
    bl_idname = "bat_pack.glob_add"
    bl_label = "Add Exclude Pattern"
    bl_description = "Add a new exclude glob pattern"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.bat_pack
        item = props.exclude_globs.add()
        item.pattern = "*.abc"
        props.exclude_globs_index = len(props.exclude_globs) - 1
        return {"FINISHED"}


class BAT_OT_glob_remove(Operator):
    bl_idname = "bat_pack.glob_remove"
    bl_label = "Remove Exclude Pattern"
    bl_description = "Remove the selected exclude glob pattern"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    index: IntProperty(default=-1)  # type: ignore[valid-type]

    def execute(self, context: bpy.types.Context) -> set[str]:
        props = context.scene.bat_pack
        idx = self.index if self.index >= 0 else props.exclude_globs_index
        if 0 <= idx < len(props.exclude_globs):
            props.exclude_globs.remove(idx)
            props.exclude_globs_index = max(0, idx - 1)
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Common preflight
# ---------------------------------------------------------------------------
def _ensure_ready(operator: Operator, context: bpy.types.Context) -> tuple[Path, Path] | None:
    """Verify BAT is installed and the file is saved. Return (project_root, blendfile_path)."""

    if not deps.is_installed():
        operator.report(
            {"ERROR"},
            "blender-asset-tracer is not installed. Open Preferences > Add-ons > "
            "BAT Render Farm Packer and click 'Install / Update BAT'.",
        )
        return None

    if not bpy.data.filepath:
        operator.report({"ERROR"}, "Save the .blend file before using BAT.")
        return None

    blendfile = Path(bpy.data.filepath).resolve()

    props = context.scene.bat_pack
    if props.project_root:
        project_root = Path(bpy.path.abspath(props.project_root)).resolve()
    else:
        project_root = blendfile.parent

    return project_root, blendfile


def _build_options(context: bpy.types.Context):
    """Build a `file_usage.Options` instance from Scene properties."""
    from blender_asset_tracer import file_usage  # type: ignore[import-not-found]
    from pathlib import PurePath

    props = context.scene.bat_pack
    globs = {item.pattern.strip() for item in props.exclude_globs if item.pattern.strip()}
    return file_usage.Options(
        use_relative_only=bool(props.use_relative_only),
        relocated_root=PurePath(props.relocated_root or "_outside_project"),
        ignore_globs=globs,
    )


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name, logging.INFO)
    logging.getLogger("blender_asset_tracer").setLevel(level)


# ---------------------------------------------------------------------------
# List dependencies (non-modal, fast enough for typical scenes)
# ---------------------------------------------------------------------------
class BAT_OT_list_deps(Operator):
    """List the dependencies of the current .blend file in a Text datablock."""

    bl_idname = "bat_pack.list_deps"
    bl_label = "List Dependencies"
    bl_description = (
        "Investigate the current .blend file with BAT and write the "
        "dependency tree to a 'BAT Dependencies' Text datablock"
    )
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        ready = _ensure_ready(self, context)
        if ready is None:
            return {"CANCELLED"}
        project_root, blendfile = ready

        props = context.scene.bat_pack
        _configure_logging(props.log_level)

        try:
            from blender_asset_tracer import file_usage  # type: ignore[import-not-found]
        except Exception as ex:
            self.report({"ERROR"}, f"Failed to import BAT: {ex}")
            return {"CANCELLED"}

        options = _build_options(context)

        try:
            deps_repo = file_usage.dependencies_of_current_blendfile(
                project_root, options
            )
        except Exception as ex:
            log.exception("BAT dependency analysis failed")
            self.report({"ERROR"}, f"BAT failed: {ex}")
            return {"CANCELLED"}

        text = _render_dep_tree(deps_repo, project_root, blendfile)

        text_name = "BAT Dependencies"
        text_block = bpy.data.texts.get(text_name) or bpy.data.texts.new(text_name)
        text_block.clear()
        text_block.write(text)

        self.report(
            {"INFO"},
            f"BAT: {len(deps_repo.file_infoes)} files — see Text datablock '{text_name}'",
        )
        return {"FINISHED"}


def _render_dep_tree(deps_repo, project_root: Path, blendfile: Path) -> str:
    """Render a human-readable dependency tree as plain text."""
    from collections import defaultdict

    lines: list[str] = []
    lines.append(f"BAT Dependencies for: {blendfile}")
    lines.append(f"Project root: {project_root}")
    lines.append(f"Total files:  {len(deps_repo.file_infoes)}")
    lines.append("")

    def show_path(p: Path) -> str:
        try:
            if p.is_relative_to(project_root):
                return str(p.relative_to(project_root))
        except Exception:
            pass
        return str(p)

    # Build user -> [used] map.
    from blender_asset_tracer.file_usage import library_abspath  # type: ignore[import-not-found]

    deps_map: dict[Path, list[Path]] = defaultdict(list)
    for used_file_info in deps_repo.file_infoes.values():
        for user_lib in used_file_info.references:
            user_path = library_abspath(user_lib)
            deps_map[user_path].append(used_file_info.source_path)

    source_info = deps_repo.source_file_info()
    seen: set[Path] = set()

    def emit(path: Path, depth: int = 0) -> None:
        if path in seen:
            return
        seen.add(path)
        lines.append("  " * depth + show_path(path))
        for child in sorted(deps_map.get(path, [])):
            emit(child, depth + 1)

    emit(source_info.source_path)

    # Anything not reachable from the source file (rare) — list flatly.
    remaining = [
        p for p in sorted(deps_repo.file_infoes) if p not in seen
    ]
    if remaining:
        lines.append("")
        lines.append("# Files not reachable from the source tree:")
        for p in remaining:
            lines.append(show_path(p))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Modal pack
# ---------------------------------------------------------------------------
class BAT_OT_pack(Operator):
    """Create a BAT pack from the current .blend file."""

    bl_idname = "bat_pack.pack"
    bl_label = "Create BAT-Pack"
    bl_description = (
        "Investigate the current .blend file, rewrite paths as needed and "
        "copy every dependency into the chosen target directory. The result "
        "is a self-contained folder ready for a render farm"
    )
    bl_options = {"REGISTER"}

    _step_count: int = 0

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return not context.scene.bat_pack.is_running

    def invoke(self, context: bpy.types.Context, event) -> set[str]:
        global _active_packer, _active_reporter, _active_timer

        ready = _ensure_ready(self, context)
        if ready is None:
            return {"CANCELLED"}
        project_root, blendfile = ready

        props = context.scene.bat_pack
        if not props.pack_target:
            self.report({"ERROR"}, "Set a 'Pack Target' directory.")
            return {"CANCELLED"}

        target = Path(bpy.path.abspath(props.pack_target)).resolve()
        if target == project_root or target == blendfile.parent:
            self.report(
                {"ERROR"},
                "Pack target must not be the project root or the blend file's folder.",
            )
            return {"CANCELLED"}

        # Refuse to overwrite a non-empty existing dir unless it looks like
        # one of ours (idempotence / safety).
        if target.exists() and any(target.iterdir()):
            self.report(
                {"WARNING"},
                f"Pack target '{target}' is not empty — files will be added/overwritten.",
            )

        if props.save_before_pack:
            try:
                bpy.ops.wm.save_mainfile()
            except Exception as ex:
                self.report({"ERROR"}, f"Could not save file: {ex}")
                return {"CANCELLED"}

        _configure_logging(props.log_level)

        try:
            from blender_asset_tracer.pack import BATPacker  # type: ignore[import-not-found]
        except Exception as ex:
            self.report({"ERROR"}, f"Failed to import BAT: {ex}")
            return {"CANCELLED"}

        options = _build_options(context)
        reporter = BlenderReporter(context.scene)

        try:
            target.mkdir(parents=True, exist_ok=True)
            packer = BATPacker(
                project_root=project_root,
                options=options,
                reporter=reporter,
                pack_target_dir=target,
            )
            packer.start()
        except Exception as ex:
            log.exception("BATPacker failed to start")
            self.report({"ERROR"}, f"BAT failed: {ex}")
            return {"CANCELLED"}

        # Reset progress UI.
        props.is_running = True
        props.cancel_requested = False
        props.progress = 0.0
        props.progress_total = 0
        props.progress_done = 0
        props.status_text = "Investigating dependencies…"
        props.last_error_count = 0

        _active_packer = packer
        _active_reporter = reporter
        self._step_count = 0

        wm = context.window_manager
        _active_timer = wm.event_timer_add(0.05, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context: bpy.types.Context, event) -> set[str]:
        global _active_packer, _active_reporter

        props = context.scene.bat_pack

        if event.type == "ESC" or props.cancel_requested:
            return self._finish(context, cancelled=True)

        if event.type != "TIMER":
            return {"PASS_THROUGH"}

        packer = _active_packer
        if packer is None:
            return self._finish(context, cancelled=True)

        # Update total file count opportunistically. BATPacker only knows
        # this once investigation is done.
        try:
            total, done = packer.num_files_to_transfer()
            if total > 0:
                props.progress_total = total
                props.progress_done = done
                props.progress = min(1.0, done / max(1, total))
        except Exception:
            pass

        # Run a few steps per timer tick to keep things flowing without
        # blocking the UI for too long.
        steps_per_tick = 8
        try:
            for _ in range(steps_per_tick):
                more = packer.step()
                self._step_count += 1
                if not more:
                    return self._finish(context, cancelled=False)
        except Exception as ex:
            log.exception("BAT packing failed")
            self.report({"ERROR"}, f"BAT failed: {ex}")
            return self._finish(context, cancelled=True)

        return {"RUNNING_MODAL"}

    def _finish(self, context: bpy.types.Context, *, cancelled: bool) -> set[str]:
        global _active_packer, _active_reporter, _active_timer

        wm = context.window_manager
        if _active_timer is not None:
            try:
                wm.event_timer_remove(_active_timer)
            except Exception:
                pass
            _active_timer = None

        packer = _active_packer
        reporter = _active_reporter
        props = context.scene.bat_pack

        if cancelled and packer is not None:
            try:
                packer.abort()
            except Exception:
                log.exception("Error aborting BAT packer")

        props.is_running = False
        props.cancel_requested = False

        target_str = props.pack_target
        target = Path(bpy.path.abspath(target_str)).resolve() if target_str else None

        errors = len(reporter.errors) if reporter else 0
        missing = len(reporter.missing) if reporter else 0
        props.last_error_count = errors

        _active_packer = None
        _active_reporter = None

        if cancelled:
            props.status_text = "Cancelled"
            self.report({"WARNING"}, "BAT pack cancelled")
            return {"CANCELLED"}

        # Success.
        summary = f"BAT pack complete: {props.progress_done} files"
        if errors:
            summary += f", {errors} error(s)"
        if missing:
            summary += f", {missing} missing"
        props.status_text = summary
        self.report({"INFO"} if not errors else {"WARNING"}, summary)

        if target is not None:
            self._post_action(context, target)

        return {"FINISHED"}

    def _post_action(self, context: bpy.types.Context, target: Path) -> None:
        action = context.scene.bat_pack.post_action
        if action == "OPEN":
            try:
                if sys.platform.startswith("win"):
                    os.startfile(str(target))  # type: ignore[attr-defined]
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", str(target)])
                else:
                    subprocess.Popen(["xdg-open", str(target)])
            except Exception:
                log.exception("Could not open pack folder")
        elif action == "ZIP":
            try:
                import shutil

                archive = shutil.make_archive(
                    base_name=str(target),
                    format="zip",
                    root_dir=str(target.parent),
                    base_dir=target.name,
                )
                self.report({"INFO"}, f"Zip created: {archive}")
            except Exception as ex:
                log.exception("Zip creation failed")
                self.report({"WARNING"}, f"Zip failed: {ex}")


class BAT_OT_cancel_pack(Operator):
    bl_idname = "bat_pack.cancel"
    bl_label = "Cancel BAT Pack"
    bl_description = "Request that the running BAT pack stops as soon as possible"
    bl_options = {"REGISTER", "INTERNAL"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        context.scene.bat_pack.cancel_requested = True
        return {"FINISHED"}
