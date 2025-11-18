"""
SKL+SKN Import Operator for V4
Uses glTF bridge for reliable coordinate conversion (preserves bind matrices better than FBX)
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper

class LOLLeagueImportSKN_V2(Operator, ImportHelper):
    """Import League of Legends SKN+SKL using glTF bridge"""
    bl_idname = "lol_league_v2.import_skn"
    bl_label = "Import LoL SKN+SKL (V4 - glTF)"
    bl_description = "Import SKN mesh and SKL skeleton using glTF bridge (preserves bind matrices)"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".skn"
    filter_glob: StringProperty(default="*.skn;*.skl", options={'HIDDEN'})
    
    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Scale factor for import (0.01 = 1% of original size)",
        default=0.01,
        min=0.0001,
        max=100.0
    )
    
    def execute(self, context):
        from ..io.gltf_bridge import convert_skl_skn_to_gltf_with_lol2gltf, convert_skl_skn_to_gltf, import_gltf_to_blender, get_temp_gltf_path, get_cached_gltf_path
        import shutil
        
        # Handle both .skn and .skl files (for drag and drop)
        filepath = self.filepath
        file_ext = os.path.splitext(filepath)[1].lower()
        
        if file_ext == '.skl':
            # If .skl is dropped, look for corresponding .skn file
            skl_path = filepath
            skn_path = os.path.splitext(skl_path)[0] + ".skn"
        else:
            # Default: assume .skn file
            skn_path = filepath
            skl_path = os.path.splitext(skn_path)[0] + ".skl"
        
        # Check if both files exist
        if not os.path.exists(skn_path):
            self.report({'ERROR'}, f"SKN file not found: {os.path.basename(skn_path)}")
            return {'CANCELLED'}
        
        if not os.path.exists(skl_path):
            self.report({'ERROR'}, f"SKL file not found: {os.path.basename(skl_path)}")
            return {'CANCELLED'}
        
        # Get base name for temp file
        base_name = os.path.splitext(os.path.basename(skn_path))[0]
        
        # Step 1: Convert SKL+SKN to glTF using lol2gltf (more reliable)
        self.report({'INFO'}, "Converting SKL+SKN to glTF using lol2gltf...")
        temp_gltf = get_temp_gltf_path(f"{base_name}_import")
        temp_gltf = os.path.splitext(temp_gltf)[0] + ".glb"  # Use binary format
        
        # Try lol2gltf first (more reliable)
        success, error_msg = convert_skl_skn_to_gltf_with_lol2gltf(skl_path, skn_path, temp_gltf)
        if not success:
            # Fallback to pygltflib if lol2gltf fails
            print(f"[lol_league_v4] WARNING: lol2gltf failed, falling back to pygltflib: {error_msg}")
            self.report({'WARNING'}, "lol2gltf failed, using fallback method")
            success, error_msg = convert_skl_skn_to_gltf(skl_path, skn_path, temp_gltf, self.scale_factor)
            if not success:
                # Show detailed error message
                self.report({'ERROR'}, error_msg)
                print(f"[lol_league_v4] ERROR: {error_msg}")
                return {'CANCELLED'}
        
        # Step 1.5: Cache the glTF for ANM import later
        cached_gltf = get_cached_gltf_path(base_name)
        try:
            shutil.copy2(temp_gltf, cached_gltf)
            print(f"[lol_league_v4] Cached glTF for ANM import: {cached_gltf}")
        except Exception as e:
            print(f"[lol_league_v4] WARNING: Could not cache glTF: {e}")
            # Continue anyway, SKL+SKN import will work without cached glTF
        
        # Step 2: Import glTF to Blender
        self.report({'INFO'}, "Importing glTF to Blender...")
        armature_obj, mesh_obj = import_gltf_to_blender(temp_gltf, context, self.scale_factor, model_name=base_name)
        
        if not armature_obj and not mesh_obj:
            self.report({'ERROR'}, "Failed to import glTF. Check console for details.")
            if os.path.exists(temp_gltf):
                os.remove(temp_gltf)
            return {'CANCELLED'}
        
        # Step 3: Store metadata for future ANM imports
        if armature_obj:
            armature_obj['lol_version'] = 'v4'
            armature_obj['lol_skl_path'] = skl_path
            armature_obj['lol_skn_path'] = skn_path
            armature_obj['lol_base_gltf_path'] = cached_gltf  # Store cached glTF path
            armature_obj['lol_anm_paths'] = []
            armature_obj['lol_scale_factor'] = self.scale_factor
            # Store original filename (without extension) for export default
            armature_obj['lol_original_name'] = base_name
            
            # Store bind matrices for ANM import later
            self._store_bind_matrices(armature_obj)
            
            print(f"[lol_league_v4] Stored metadata on armature: {armature_obj.name}")
            print(f"[lol_league_v4] Cached glTF path: {cached_gltf}")
        
        # Step 4: Position objects at cursor
        if mesh_obj:
            try:
                mesh_obj.location = context.scene.cursor.location.copy()
                if armature_obj:
                    armature_obj.location = mesh_obj.location
            except Exception:
                pass
        
        # Step 5: Select imported objects
        # Make sure we're in Object Mode first
        try:
            if bpy.context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
        except:
            pass
        
        # Deselect all and select imported objects
        try:
            bpy.ops.object.select_all(action='DESELECT')
        except:
            # If that fails, manually deselect
            for obj in context.selected_objects:
                obj.select_set(False)
        
        if mesh_obj:
            mesh_obj.select_set(True)
            context.view_layer.objects.active = mesh_obj
        if armature_obj:
            armature_obj.select_set(True)
        
        # Step 6: Cleanup temp glTF
        try:
            if os.path.exists(temp_gltf):
                os.remove(temp_gltf)
                print(f"[lol_league_v4] Cleaned up temp glTF: {temp_gltf}")
        except Exception as e:
            print(f"[lol_league_v4] WARNING: Could not remove temp glTF: {e}")
        
        self.report({'INFO'}, f"Imported SKN+SKL: {base_name}")
        return {'FINISHED'}
    
    def _store_bind_matrices(self, armature_obj):
        """
        Store bind matrices from bones for ANM import.
        These will be used later when adding animations.
        """
        try:
            for bone in armature_obj.data.bones:
                # Store bind matrix (4x4 matrix as nested list)
                bind_matrix = bone.matrix_local.copy()
                bone['lol_bind_matrix'] = [list(row) for row in bind_matrix]
            
            print(f"[lol_league_v2] Stored bind matrices for {len(armature_obj.data.bones)} bones")
        except Exception as e:
            print(f"[lol_league_v2] WARNING: Could not store bind matrices: {e}")
    

def register():
    bpy.utils.register_class(LOLLeagueImportSKN_V2)

def unregister():
    bpy.utils.unregister_class(LOLLeagueImportSKN_V2)

