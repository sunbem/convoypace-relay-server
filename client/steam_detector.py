"""
client/steam_detector.py - Automatic detection of Steam and Euro Truck Simulator 2 on Windows.
Parses Steam registry keys, libraryfolders.vdf, and multi-drive game libraries.
"""

import os
import sys
import re
from pathlib import Path
from typing import Optional, List, Dict

ETS2_APP_ID = "227300"
ETS2_DIR_NAME = "Euro Truck Simulator 2"
PLUGIN_REL_PATH = os.path.join("bin", "win_x64", "plugins")
PLUGIN_DLL_NAME = "scs-telemetry.dll"


def get_steam_path_from_registry() -> Optional[str]:
    """Retrieve primary Steam installation path from Windows Registry."""
    if os.name != "nt":
        return None

    import winreg
    subkeys = [
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
    ]

    for root, subkey, value_name in subkeys:
        try:
            with winreg.OpenKey(root, subkey) as k:
                val, _ = winreg.QueryValueEx(k, value_name)
                if val and os.path.exists(val):
                    return os.path.normpath(val)
        except Exception:
            continue

    return None


def parse_library_folders(steam_path: str) -> List[str]:
    """Parse Steam's libraryfolders.vdf to find all Steam library paths across all drives."""
    libraries = [steam_path]
    vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")

    if not os.path.isfile(vdf_path):
        return libraries

    try:
        with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        # Extract "path" "\path\to\library"
        matches = re.findall(r'"path"\s+"([^"]+)"', content, re.IGNORECASE)
        for m in matches:
            norm = os.path.normpath(m.replace(r"\\", "\\"))
            if os.path.isdir(norm) and norm not in libraries:
                libraries.append(norm)
    except Exception:
        pass

    return libraries


def detect_ets2_path() -> Optional[str]:
    """
    Automatically detect the root directory of Euro Truck Simulator 2.
    Returns path e.g. 'E:\\SteamLibrary\\steamapps\\common\\Euro Truck Simulator 2' or None.
    """
    # 1. Check Steam Registry Uninstall key for AppID 227300
    if os.name == "nt":
        import winreg
        uninstall_subkeys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App " + ETS2_APP_ID),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App " + ETS2_APP_ID)
        ]
        for root, subkey in uninstall_subkeys:
            try:
                with winreg.OpenKey(root, subkey) as k:
                    install_loc, _ = winreg.QueryValueEx(k, "InstallLocation")
                    if install_loc and os.path.isdir(install_loc):
                        exe_check = os.path.join(install_loc, "bin", "win_x64", "eurotrucks2.exe")
                        if os.path.isfile(exe_check):
                            return os.path.normpath(install_loc)
            except Exception:
                continue

    # 2. Check Steam libraries parsed from libraryfolders.vdf
    steam_path = get_steam_path_from_registry()
    search_roots = []
    if steam_path:
        search_roots.extend(parse_library_folders(steam_path))

    # Standard fallback drives
    for drive in ["C", "D", "E", "F", "G", "H", "J"]:
        fallback_lib = f"{drive}:\\SteamLibrary"
        if os.path.isdir(fallback_lib) and fallback_lib not in search_roots:
            search_roots.append(fallback_lib)
        std_lib = f"{drive}:\\Program Files (x86)\\Steam"
        if os.path.isdir(std_lib) and std_lib not in search_roots:
            search_roots.append(std_lib)

    for lib in search_roots:
        candidate = os.path.join(lib, "steamapps", "common", ETS2_DIR_NAME)
        exe_check = os.path.join(candidate, "bin", "win_x64", "eurotrucks2.exe")
        if os.path.isfile(exe_check):
            return os.path.normpath(candidate)

    return None


def get_plugin_destination(ets2_path: str) -> str:
    """Return the full destination directory for scs-telemetry.dll."""
    return os.path.normpath(os.path.join(ets2_path, PLUGIN_REL_PATH))


def is_plugin_installed(ets2_path: Optional[str]) -> bool:
    """Check if scs-telemetry.dll is present in the game's plugins folder."""
    if not ets2_path or not os.path.isdir(ets2_path):
        return False
    dll_path = os.path.join(get_plugin_destination(ets2_path), PLUGIN_DLL_NAME)
    return os.path.isfile(dll_path) and os.path.getsize(dll_path) > 10000


if __name__ == "__main__":
    print("Detecting ETS2 installation...")
    detected = detect_ets2_path()
    if detected:
        print(f"✅ Found ETS2 at: {detected}")
        installed = is_plugin_installed(detected)
        print(f"   Plugin Installed: {'✅ Yes' if installed else '❌ No'}")
        print(f"   Target Plugin Path: {get_plugin_destination(detected)}\\{PLUGIN_DLL_NAME}")
    else:
        print("❌ Could not automatically detect ETS2 installation.")

