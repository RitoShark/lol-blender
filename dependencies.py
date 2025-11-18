"""
Dependency loader for bundled pyritofile and its dependencies.
This ensures xxhash and pyzstd are available before importing pyritofile.
Also handles FBX SDK bundling.
"""

import os
import sys
from pathlib import Path

# Get the addon directory
_addon_dir = Path(__file__).parent
_vendor_dir = _addon_dir / "vendor"
_pyritofile_dir = _vendor_dir / "pyritofile-package"

# Dependencies that need to be bundled
_BUNDLED_DEPS = ["xxhash", "pyzstd", "pygltflib"]


def _setup_bundled_dependencies():
    """Add bundled dependencies to sys.path if they exist."""
    deps_dir = _vendor_dir / "dependencies"
    deps_abs = deps_dir.resolve()
    
    if not deps_abs.exists():
        print(f"[lol_league_v2] DEBUG: Dependencies dir does not exist: {deps_abs}")
        return False
    
    # Add the dependencies directory to sys.path so packages can be imported
    deps_str = str(deps_abs)
    if deps_str not in sys.path:
        sys.path.insert(0, deps_str)
        print(f"[lol_league_v2] DEBUG: Dependencies path added: {deps_str}")
    
    return True


def _setup_pyritofile_path():
    """Add pyritofile package directory to sys.path."""
    # Convert to absolute path to avoid issues
    pyritofile_abs = _pyritofile_dir.resolve()
    if pyritofile_abs.exists():
        pyritofile_str = str(pyritofile_abs)
        if pyritofile_str not in sys.path:
            sys.path.insert(0, pyritofile_str)
        print(f"[lol_league_v2] DEBUG: pyritofile path added: {pyritofile_str}")
        return True
    else:
        print(f"[lol_league_v2] DEBUG: pyritofile path does not exist: {pyritofile_abs}")
    return False


def ensure_dependencies():
    """
    Ensure all dependencies are available.
    Returns True if pyritofile can be imported, False otherwise.
    """
    # Setup bundled dependencies first
    if not _setup_bundled_dependencies():
        print("[lol_league_v2] WARNING: Dependencies directory not found")
        return False
    
    # Setup pyritofile path
    if not _setup_pyritofile_path():
        print("[lol_league_v2] WARNING: pyritofile-package directory not found")
        return False
    
    # Try to import pyritofile dependencies
    try:
        import xxhash
        print("[lol_league_v2] OK: xxhash imported")
    except ImportError as e:
        print(f"[lol_league_v2] ERROR: Failed to import xxhash: {e}")
        return False
    
    try:
        import pyzstd
        print("[lol_league_v2] OK: pyzstd imported")
    except ImportError as e:
        print(f"[lol_league_v2] ERROR: Failed to import pyzstd: {e}")
        return False
    
    # Try to import pyritofile
    try:
        import pyritofile
        print("[lol_league_v2] OK: pyritofile imported successfully")
        return True
    except ImportError as e:
        print(f"[lol_league_v2] ERROR: Failed to import pyritofile: {e}")
        import traceback
        traceback.print_exc()
        return False


def is_pyritofile_available():
    """Check if pyritofile is available after ensuring dependencies."""
    return ensure_dependencies()


# FBX SDK support removed - using glTF bridge only


def is_pygltflib_available():
    """Check if pygltflib is available (bundled or installed)."""
    # First try bundled version
    if _setup_bundled_dependencies():
        try:
            import pygltflib
            print("[lol_league_v4] OK: pygltflib imported from bundled location")
            return True
        except ImportError:
            pass
    
    # Try system-installed version
    try:
        import pygltflib
        print("[lol_league_v4] OK: pygltflib imported from system")
        return True
    except ImportError:
        return False


# Auto-setup on import (but don't fail if it doesn't work)
try:
    ensure_dependencies()
except Exception as e:
    print(f"[lol_league_v2] ERROR: Exception during dependency setup: {e}")
    import traceback
    traceback.print_exc()

