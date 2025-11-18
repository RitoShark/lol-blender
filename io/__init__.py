"""
I/O module for LoL Blender
Handles conversion between LoL files, glTF, and Blender
"""

# Import from gltf_bridge (main conversion bridge)
from .gltf_bridge import (
    convert_skl_skn_to_gltf_with_lol2gltf,
    convert_skl_skn_to_gltf,
    convert_gltf_to_skl_skn_with_lol2gltf,
    convert_skl_skn_anm_to_gltf_with_lol2gltf,
    import_gltf_to_blender,
    export_blender_to_gltf,
    get_temp_gltf_path,
    get_cached_gltf_path,
)

__all__ = [
    # glTF bridge functions
    'convert_skl_skn_to_gltf_with_lol2gltf',
    'convert_skl_skn_to_gltf',
    'convert_gltf_to_skl_skn_with_lol2gltf',
    'convert_skl_skn_anm_to_gltf_with_lol2gltf',
    'import_gltf_to_blender',
    'export_blender_to_gltf',
    'get_temp_gltf_path',
    'get_cached_gltf_path',
]

