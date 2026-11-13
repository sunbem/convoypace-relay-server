"""
client/plugin_installer.py - 1-Click installer for scs-telemetry.dll into Euro Truck Simulator 2.
Supports running from source and bundled PyInstaller single-file executables.
"""

import os
import sys
import shutil
import hashlib
from pathlib import Path

# Ensure root directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from client.steam_detector import (
    detect_ets2_path,
    get_plugin_destination,
    is_plugin_installed,
    PLUGIN_DLL_NAME
)


def get_bundled_plugin_path() -> Optional[str]:
    """Find the bundled scs-telemetry.dll path (handles PyInstaller _MEIPASS and source repo)."""
    # 1. PyInstaller frozen environment
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_candidate = os.path.join(sys._MEIPASS, "bin", PLUGIN_DLL_NAME)
        if os.path.isfile(meipass_candidate):
            return meipass_candidate
        root_candidate = os.path.join(sys._MEIPASS, PLUGIN_DLL_NAME)
        if os.path.isfile(root_candidate):
            return root_candidate

    # 2. Source repository: bin/scs-telemetry.dll
    repo_root = Path(__file__).resolve().parent.parent
    source_candidate = repo_root / "bin" / PLUGIN_DLL_NAME
    if source_candidate.is_file():
        return str(source_candidate)

    # 3. Next to executable
    exe_dir = Path(sys.executable).parent
    exe_candidate = exe_dir / "bin" / PLUGIN_DLL_NAME
    if exe_candidate.is_file():
        return str(exe_candidate)

    return None


def get_file_md5(path: str) -> str:
    """Compute MD5 checksum of a file."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def install_plugin(ets2_path: Optional[str] = None) -> Dict[str, Any]:
    """
    1-Click install scs-telemetry.dll into Euro Truck Simulator 2\\bin\\win_x64\\plugins.
    """
    if not ets2_path:
        ets2_path = detect_ets2_path()

    if not ets2_path or not os.path.isdir(ets2_path):
        return {
            "success": False,
            "message": "Euro Truck Simulator 2 installation path could not be detected. Please locate it manually."
        }

    src_dll = get_bundled_plugin_path()
    if not src_dll or not os.path.isfile(src_dll):
        return {
            "success": False,
            "message": f"Bundled {PLUGIN_DLL_NAME} not found in application package."
        }

    dest_dir = get_plugin_destination(ets2_path)
    dest_dll = os.path.join(dest_dir, PLUGIN_DLL_NAME)

    try:
        os.makedirs(dest_dir, exist_ok=True)
        shutil.copy2(src_dll, dest_dll)

        if not os.path.isfile(dest_dll):
            return {"success": False, "message": "Failed to verify copied plugin DLL."}

        src_hash = get_file_md5(src_dll)
        dest_hash = get_file_md5(dest_dll)

        if src_hash != dest_hash:
            return {"success": False, "message": "Plugin DLL checksum mismatch after installation."}

        return {
            "success": True,
            "message": f"Successfully installed scs-telemetry.dll into {dest_dir}",
            "dest_path": dest_dll,
            "size_bytes": os.path.getsize(dest_dll)
        }
    except PermissionError:
        return {
            "success": False,
            "message": f"Permission denied while writing to {dest_dir}. Try running ConvoyPace as Administrator."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Installation failed: {str(e)}"
        }


def uninstall_plugin(ets2_path: Optional[str] = None) -> Dict[str, Any]:
    """Remove scs-telemetry.dll from Euro Truck Simulator 2."""
    if not ets2_path:
        ets2_path = detect_ets2_path()

    if not ets2_path:
        return {"success": False, "message": "ETS2 path not found."}

    dest_dll = os.path.join(get_plugin_destination(ets2_path), PLUGIN_DLL_NAME)
    if not os.path.isfile(dest_dll):
        return {"success": True, "message": "Plugin is not currently installed."}

    try:
        os.remove(dest_dll)
        return {"success": True, "message": "Plugin uninstalled successfully."}
    except Exception as e:
        return {"success": False, "message": f"Uninstall error: {str(e)}"}


if __name__ == "__main__":
    print("Testing 1-Click Plugin Installer...")
    res = install_plugin()
    print("Install result:", res)
    installed = is_plugin_installed(detect_ets2_path())
    print("Plugin is installed:", installed)
