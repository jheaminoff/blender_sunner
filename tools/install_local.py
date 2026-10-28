"""Install/update the verified Sunner ZIP without loading a user's startup scene.

Run with Blender --background --factory-startup --python-exit-code 1 --python this_file
-- --zip dist/sunner-<version>.zip. User preferences are read explicitly before saving.
Backups and receipts stay in Blender's local configuration directory, not this project.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tomllib
import zipfile

import bpy

parser = argparse.ArgumentParser()
parser.add_argument("--zip", required=True, type=Path)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
archive_path = args.zip.expanduser().resolve()
with zipfile.ZipFile(archive_path) as archive:
    manifest = tomllib.loads(archive.read("blender_manifest.toml").decode())
    if manifest["id"] != "sunner":
        raise RuntimeError("This installer only manages the Sunner extension")
    payload = {name: archive.read(name) for name in archive.namelist() if not name.endswith("/")}

config = Path(bpy.utils.user_resource("CONFIG", create=True))
preferences_file = config / "userpref.blend"
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
backup = config / "sunner-backups" / stamp
backup.mkdir(parents=True, mode=0o700)
backup.parent.chmod(0o700)
if preferences_file.exists():
    shutil.copy2(preferences_file, backup / "userpref.blend")
    (backup / "userpref.blend").chmod(0o600)
    if bpy.ops.wm.read_userpref() != {"FINISHED"}:
        raise RuntimeError("Could not read existing preferences; refusing to overwrite them")

enabled_before = set(bpy.context.preferences.addons.keys())
repos = bpy.context.preferences.extensions.repos
repo = next((entry for entry in repos
             if (Path(entry.directory) / "sunner" / "blender_manifest.toml").is_file()), None)
if repo is not None and repo.use_remote_url:
    raise RuntimeError("Sunner is managed by a remote repository; refusing to replace that installation")
if repo is None:
    repo = next((entry for entry in repos if entry.module == "sunner_local" and not entry.use_remote_url), None)
if repo is None:
    directory = bpy.utils.user_resource("EXTENSIONS", path="sunner_local", create=True)
    if bpy.ops.preferences.extension_repo_add(name="Sunner local", type="LOCAL",
                                              use_custom_directory=True, custom_directory=directory) != {"FINISHED"}:
        raise RuntimeError("Could not create the local Sunner extension repository")
    repo = repos[-1]

installed = Path(repo.directory) / "sunner"
if installed.exists():
    shutil.copytree(installed, backup / "sunner", ignore=shutil.ignore_patterns("__pycache__"))
result = bpy.ops.extensions.package_install_files(filepath=str(archive_path), repo=repo.module,
                                                  enable_on_install=True, overwrite=True)
if result != {"FINISHED"}:
    raise RuntimeError(f"Installation failed: {result}; previous files are in {backup}")
module = f"bl_ext.{repo.module}.sunner"
if module not in bpy.context.preferences.addons:
    raise RuntimeError("Sunner was installed but not enabled; preferences were not saved")
for name, content in payload.items():
    if (installed / name).read_bytes() != content:
        raise RuntimeError(f"Installed file differs from the ZIP: {name}")
if not hasattr(bpy.types, "SUNNER_PT_weather"):
    raise RuntimeError("Installed weather panel did not register")
if not enabled_before.issubset(set(bpy.context.preferences.addons.keys())):
    raise RuntimeError("Existing add-on enablement changed; preferences were not saved")
if bpy.ops.wm.save_userpref() != {"FINISHED"}:
    raise RuntimeError("Could not save updated user preferences")
receipt = {
    "version": manifest["version"], "blender": bpy.app.version_string,
    "module": module, "directory": str(installed), "preferences": str(preferences_file),
    "backup": str(backup), "zip_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    "enabled": True, "installed_files_match_zip": True,
}
receipt_path = config / "sunner-install.json"
receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
receipt_path.chmod(0o600)
print("SUNNER_LOCAL_INSTALL_OK " + json.dumps(receipt), flush=True)
