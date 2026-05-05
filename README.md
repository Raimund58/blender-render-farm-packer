# BAT Render Farm Packer

A lightweight Blender 5.1+ add-on that prepares projects for render farms by
driving [Blender Asset Tracer v2 (BAT v2)](https://github.com/Raimund58/blender-asset-tracer)
directly through its Python API.

The add-on installs the official `blender-asset-tracer` package from PyPI
into a per-user folder on demand, so updating BAT requires no add-on
changes.

## Requirements

- **Blender 5.1.0 or newer.** BAT v2 itself only supports 5.1+, and so does
  this add-on. Older Blender versions will refuse to register the add-on.
- Network access on first use, to install BAT from PyPI.
- No admin / root privileges — BAT is installed into your user scripts
  folder.

## Install

1. Download or clone this repository.
2. In Blender, drag-and-drop the `bat_render_prep/` folder onto the
   3D Viewport (Blender 4.2+ extensions UX) **or** zip the folder and use
   `Edit > Preferences > Add-ons > Install from disk`.
3. Enable **BAT Render Farm Packer**.
4. In the add-on preferences, click **Install / Update BAT**.

## Use

1. Open the **Properties Editor → Output Properties** tab.
2. Find the **BAT Render Farm Packer** panel.
3. Set:
   - **Project Root** — root of your project (defaults to the .blend's
     folder).
   - **Pack Target** — empty folder to write the self-contained pack into.
4. (Optional) In the **Options** sub-panel, toggle "Relative paths only",
   set the relocated-root folder name and choose a post-pack action.
5. (Optional) In the **Exclude Patterns** sub-panel, add globs such as
   `*.abc` or `*.bphys` to skip certain caches.
6. Click **Create BAT-Pack**.

The operator is modal: progress is shown live, and you can cancel with the
**Cancel** button or by pressing `Esc`.

You can also click **List Dependencies** to write BAT's dependency tree
into a Blender Text datablock named `BAT Dependencies` for inspection.

## How it works

| UI control | BAT API |
|---|---|
| Project Root | `BATPacker(project_root=…)` |
| Pack Target | `BATPacker(pack_target_dir=…)` |
| Relative paths only | `file_usage.Options.use_relative_only` |
| Relocated Root | `file_usage.Options.relocated_root` |
| Exclude globs | `file_usage.Options.ignore_globs` |
| Log level | `logging.getLogger("blender_asset_tracer").setLevel(...)` |
| Create BAT-Pack | `BATPacker.start()` + `step()` loop in a modal timer |
| Cancel | `BATPacker.abort()` |
| List Dependencies | `file_usage.dependencies_of_current_blendfile(...)` |

The pack operator implements the `BATPackReporter` Protocol so progress and
errors flow naturally into the panel.

## Known limitations

These come from BAT v2 / Blender 5.1.0 itself:

- Blender 5.1.0 does not report legacy particle system cache files
  correctly (fixed in 5.1.1).
- Blender 5.1.0 does not report Alembic file sequences correctly.
- Blender 5.1.0 does not report Geometry Nodes simulation cache files.

See the [BAT README](https://github.com/Raimund58/blender-asset-tracer) for
details and tracking issues.

## License

GPL-3.0-or-later — same as BAT v2.
