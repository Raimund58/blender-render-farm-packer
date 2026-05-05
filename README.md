# BAT Render Farm Packer

A lightweight Blender 5.1+ add-on that prepares projects for render farms by
driving [Blender Asset Tracer v2 (BAT v2)](https://github.com/Raimund58/blender-asset-tracer)
directly through its Python API.

The add-on installs the official `blender-asset-tracer` package from PyPI
into a per-user folder on demand, so updating BAT requires no add-on
changes.

## Requirements

- **Blender 5.1.1 or newer.** BAT v2 needs 5.1+, and 5.1.0 has dependency-
  reporting bugs that BAT cannot work around (legacy particle caches in
  particular). We require 5.1.1 so the add-on can rely on a known-good
  baseline. Older Blender versions will refuse to register the add-on.
- Network access on first use, to install BAT from PyPI.
- No admin / root privileges — BAT is installed into your user scripts
  folder.

## Install

Blender's add-on installer needs a `.zip` file — a raw folder will not work.

### Option A — download a release zip (recommended)

1. Grab `bat_render_prep-<version>.zip` from the
   [Releases page](https://github.com/Raimund58/blender-render-farm-packer/releases).
2. In Blender, drag the zip onto the 3D Viewport, **or** use
   `Edit > Preferences > Add-ons > Install from disk` and pick the zip.
3. Enable **BAT Render Farm Packer**.
4. In the add-on preferences, click **Install / Update BAT**.

### Option B — build the zip yourself

From a clone of this repository:

```sh
# macOS / Linux
cd blender-render-farm-packer
zip -r bat_render_prep.zip bat_render_prep -x '*/__pycache__/*'
```

```powershell
# Windows PowerShell
cd blender-render-farm-packer
Compress-Archive -Path bat_render_prep -DestinationPath bat_render_prep.zip -Force
```

Then install `bat_render_prep.zip` in Blender as in Option A.

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

These come from Blender itself, not from this add-on or BAT:

- Alembic file sequences are not reported correctly by Blender
  ([blender#155774](https://projects.blender.org/blender/blender/issues/155774)),
  so BAT cannot pack them correctly either.
- Geometry Nodes simulation cache files are not reported by Blender
  ([blender#155953](https://projects.blender.org/blender/blender/issues/155953)),
  so BAT does not know about them and will not pack them.

The legacy particle-system cache reporting bug that affected Blender 5.1.0
is fixed in 5.1.1, which is why this add-on requires 5.1.1 as a minimum.

See the [BAT README](https://github.com/Raimund58/blender-asset-tracer) for
the latest tracking status.

## License

GPL-3.0-or-later — same as BAT v2.
