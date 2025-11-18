#!/usr/bin/env python3
"""
Create a release package for LoL Blender.
This script creates a clean ZIP file ready for distribution on GitHub.

Usage:
    python create_release.py [version]
    
Example:
    python create_release.py 1.0.0
"""

import os
import sys
import shutil
import zipfile
from pathlib import Path

# Files and folders to include in the release
INCLUDE_FILES = [
    "__init__.py",
    "dependencies.py",
    "panels.py",
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
]

INCLUDE_FOLDERS = [
    "operators",
    "io",
    "vendor",
]

# Files and folders to exclude
EXCLUDE_PATTERNS = [
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".git",
    ".gitignore",
    "*.log",
    ".DS_Store",
    "Thumbs.db",
]

def should_exclude(path: Path, exclude_patterns: list) -> bool:
    """Check if a path should be excluded based on patterns."""
    path_str = str(path)
    name = path.name
    
    for pattern in exclude_patterns:
        if pattern.startswith("*."):
            # File extension pattern
            ext = pattern[1:]
            if path_str.endswith(ext):
                return True
        else:
            # Name pattern
            if pattern in path_str or name == pattern:
                return True
    
    return False

def copy_tree(src: Path, dst: Path, exclude_patterns: list):
    """Copy directory tree, excluding certain patterns."""
    dst.mkdir(parents=True, exist_ok=True)
    
    for item in src.iterdir():
        src_item = src / item.name
        dst_item = dst / item.name
        
        if should_exclude(src_item, exclude_patterns):
            print(f"  Excluding: {src_item.relative_to(src.parent)}")
            continue
        
        if src_item.is_dir():
            copy_tree(src_item, dst_item, exclude_patterns)
        else:
            shutil.copy2(src_item, dst_item)
            print(f"  Copied: {src_item.relative_to(src.parent)}")

def create_release_package(version: str = None):
    """Create a release ZIP package."""
    
    # Get paths
    script_dir = Path(__file__).parent
    
    # Determine version
    if not version:
        # Try to read version from __init__.py
        init_file = script_dir / "__init__.py"
        if init_file.exists():
            with open(init_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '"version":' in line:
                        # Extract version tuple like (1, 0, 0)
                        import re
                        match = re.search(r'\((\d+),\s*(\d+),\s*(\d+)\)', line)
                        if match:
                            version = f"{match.group(1)}.{match.group(2)}.{match.group(3)}"
                            break
        
        if not version:
            version = "1.0.0"
    
    print("=" * 60)
    print(f"Creating LoL Blender Release Package v{version}")
    print("=" * 60)
    print()
    
    # Create build directory
    build_dir = script_dir / "build"
    if build_dir.exists():
        print("Cleaning old build directory...")
        shutil.rmtree(build_dir)
    
    build_dir.mkdir()
    addon_dir = build_dir / "lol_blender"
    addon_dir.mkdir()
    
    print("Copying files...")
    print()
    
    # Copy individual files
    for filename in INCLUDE_FILES:
        src_file = script_dir / filename
        # Check in docs/ folder if not found in root
        if not src_file.exists() and filename == "CHANGELOG.md":
            src_file = script_dir / "docs" / filename
        if src_file.exists():
            dst_file = addon_dir / filename
            shutil.copy2(src_file, dst_file)
            print(f"  Copied: {filename}")
        else:
            print(f"  Warning: {filename} not found, skipping")
    
    # Copy folders
    for folder in INCLUDE_FOLDERS:
        src_folder = script_dir / folder
        if src_folder.exists() and src_folder.is_dir():
            print(f"  Copying folder: {folder}/")
            dst_folder = addon_dir / folder
            copy_tree(src_folder, dst_folder, EXCLUDE_PATTERNS)
        else:
            print(f"  Warning: {folder}/ not found, skipping")
    
    # Check for optional lol2gltf.exe
    lol2gltf_locations = [
        script_dir / "lol2gltf-main" / "lol2gltf.exe",
        script_dir / "lol2gltf.exe",
    ]
    
    lol2gltf_found = False
    for lol2gltf_path in lol2gltf_locations:
        if lol2gltf_path.exists():
            dst_dir = addon_dir / "lol2gltf-main"
            dst_dir.mkdir(exist_ok=True)
            dst_file = dst_dir / "lol2gltf.exe"
            shutil.copy2(lol2gltf_path, dst_file)
            print(f"  Copied: lol2gltf.exe ({lol2gltf_path.stat().st_size / 1024 / 1024:.1f} MB)")
            lol2gltf_found = True
            break
    
    if not lol2gltf_found:
        print("  Warning: lol2gltf.exe not found (optional, users can download separately)")
    
    print()
    print("Creating ZIP archive...")
    
    # Create ZIP file
    zip_filename = f"lol_blender_v{version}.zip"
    zip_path = script_dir / zip_filename
    
    if zip_path.exists():
        zip_path.unlink()
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(addon_dir):
            # Remove excluded directories from traversal
            dirs[:] = [d for d in dirs if not should_exclude(Path(root) / d, EXCLUDE_PATTERNS)]
            
            for file in files:
                file_path = Path(root) / file
                if should_exclude(file_path, EXCLUDE_PATTERNS):
                    continue
                
                # Calculate archive name (relative to build_dir)
                arcname = file_path.relative_to(build_dir)
                zipf.write(file_path, arcname)
    
    # Get ZIP file size
    zip_size_mb = zip_path.stat().st_size / 1024 / 1024
    
    print()
    print("=" * 60)
    print("Release package created successfully!")
    print("=" * 60)
    print(f"  Version: {version}")
    print(f"  File: {zip_filename}")
    print(f"  Size: {zip_size_mb:.2f} MB")
    print(f"  Location: {zip_path}")
    print()
    print("Next steps:")
    print("  1. Test the addon by installing the ZIP in Blender")
    print("  2. Create a GitHub release and upload this ZIP file")
    print("  3. See GITHUB_SETUP.md for detailed instructions")
    print("=" * 60)
    
    # Clean up build directory
    print()
    print("Cleaning up build directory...")
    shutil.rmtree(build_dir)
    
    return True

if __name__ == "__main__":
    version = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        success = create_release_package(version)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

