"""
ANM Import Operator for LoL League Tools V2
"""

import os
import bpy
from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, FloatProperty


class LOLLeagueImportANM_V2(Operator, ImportHelper):
    """Import League of Legends ANM animation using FBX bridge"""
    bl_idname = "import_scene.lol_anm_v2"
    bl_label = "Import LoL ANM (V2)"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    
    scale_factor: FloatProperty(
        name="Scale",
        description="Scale factor for imported animation",
        default=0.01,
        min=0.0001,
        max=100.0
    )
    
    def execute(self, context):
        import tempfile
        from ..io.gltf_bridge import (
            export_blender_to_gltf, convert_gltf_to_skl_skn_with_lol2gltf,
            convert_skl_skn_anm_to_gltf_with_lol2gltf, import_gltf_to_blender,
            get_temp_gltf_path
        )
        
        anm_path = self.filepath
        
        # Get active armature
        armature_obj = context.active_object
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature to apply animation to")
            return {'CANCELLED'}
        
        # Find mesh object (if any) - look for mesh parented to armature
        mesh_obj = None
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.parent == armature_obj:
                mesh_obj = obj
                break
        # Also check scene objects if not found in selection
        if not mesh_obj:
            for obj in context.scene.objects:
                if obj.type == 'MESH' and obj.parent == armature_obj:
                    mesh_obj = obj
                    break
        
        if not mesh_obj:
            self.report({'ERROR'}, "No mesh found. ANM import requires a mesh.")
            return {'CANCELLED'}
        
        # Get animation name
        anm_name = os.path.splitext(os.path.basename(anm_path))[0]
        
        # Store references to old objects (we'll delete them before importing new ones)
        old_armature_obj = armature_obj
        old_mesh_obj = mesh_obj
        
        # Find and store the original skinned_mesh name (parent of armature or mesh)
        old_skinned_mesh_name = None
        if old_armature_obj and old_armature_obj.parent:
            old_skinned_mesh_name = old_armature_obj.parent.name
        elif old_mesh_obj and old_mesh_obj.parent:
            old_skinned_mesh_name = old_mesh_obj.parent.name
        
        # Get scale factor and metadata from old armature BEFORE deleting it
        scale_factor = old_armature_obj.get('lol_scale_factor', self.scale_factor)
        old_skl_path = old_armature_obj.get('lol_skl_path', '')
        old_skn_path = old_armature_obj.get('lol_skn_path', '')
        old_anm_paths = list(old_armature_obj.get('lol_anm_paths', []))
        
        try:
            # Step 1: Export current Blender state to glTF (preserves user edits)
            self.report({'INFO'}, "Step 1: Exporting current armature state to glTF...")
            temp_gltf_export = get_temp_gltf_path(f"anm_import_current_state")
            temp_gltf_export = os.path.splitext(temp_gltf_export)[0] + ".glb"
            
            success = export_blender_to_gltf(old_armature_obj, old_mesh_obj, temp_gltf_export)
            if not success:
                self.report({'ERROR'}, "Failed to export current state to glTF")
                return {'CANCELLED'}
            print(f"[lol_league_v4] Step 1: SUCCESS - Exported to {temp_gltf_export}")
            
            # Step 2: Convert glTF to SKL/SKN (this preserves all user edits)
            self.report({'INFO'}, "Step 2: Converting glTF to SKL/SKN (preserving edits)...")
            temp_skl = os.path.join(tempfile.gettempdir(), f"lol_league_v4_anm_temp_{anm_name}.skl")
            temp_skn = os.path.join(tempfile.gettempdir(), f"lol_league_v4_anm_temp_{anm_name}.skn")
            
            success, error_msg = convert_gltf_to_skl_skn_with_lol2gltf(temp_gltf_export, temp_skn, temp_skl)
            if not success:
                self.report({'ERROR'}, f"Failed to convert to SKL/SKN: {error_msg}")
                print(f"[lol_league_v4] Step 2: FAILED - {error_msg}")
                return {'CANCELLED'}
            print(f"[lol_league_v4] Step 2: SUCCESS - Created SKL and SKN")
            
            # Step 3: Delete old objects AND their data blocks BEFORE importing (prevents .001 suffixes)
            self.report({'INFO'}, "Step 3: Clearing existing armature...")
            
            # Store data block references before deleting objects
            old_armature_data = old_armature_obj.data if old_armature_obj else None
            old_mesh_data = old_mesh_obj.data if old_mesh_obj else None
            
            # Get materials from old mesh before deleting (to prevent .001 suffixes)
            old_materials = []
            if old_mesh_obj and old_mesh_obj.data and old_mesh_obj.data.materials:
                old_materials = [mat for mat in old_mesh_obj.data.materials if mat]
            
            # Delete objects first
            bpy.data.objects.remove(old_armature_obj, do_unlink=True)
            if old_mesh_obj:
                bpy.data.objects.remove(old_mesh_obj, do_unlink=True)
            
            # Delete data blocks to prevent name conflicts
            if old_armature_data and old_armature_data.name in bpy.data.armatures:
                bpy.data.armatures.remove(old_armature_data, do_unlink=True)
            if old_mesh_data and old_mesh_data.name in bpy.data.meshes:
                bpy.data.meshes.remove(old_mesh_data, do_unlink=True)
            
            # Delete materials to prevent .001 suffixes on re-import
            for mat in old_materials:
                if mat and mat.name in bpy.data.materials:
                    # Store material name before deletion (can't access after removal)
                    mat_name = mat.name
                    # Check if material is used by other objects
                    is_used = False
                    for obj in bpy.data.objects:
                        if obj.type == 'MESH' and obj.data and obj.data.materials:
                            if mat in obj.data.materials:
                                is_used = True
                                break
                    # Only delete if not used elsewhere
                    if not is_used:
                        bpy.data.materials.remove(mat, do_unlink=True)
                        print(f"[lol_league_v4] Deleted material: {mat_name}")
            
            print(f"[lol_league_v4] Step 3: SUCCESS - Old objects, data blocks, and materials deleted")
            
            # Step 4: Create glTF with SKL+SKN+ANM using lol2gltf
            self.report({'INFO'}, "Step 4: Creating glTF with animation using lol2gltf...")
            temp_gltf_with_anm = get_temp_gltf_path(f"anm_import_{anm_name}")
            temp_gltf_with_anm = os.path.splitext(temp_gltf_with_anm)[0] + ".glb"
            
            # Create a temp folder with the ANM file (lol2gltf expects a folder)
            anm_folder = os.path.join(tempfile.gettempdir(), f"lol_league_v4_anm_folder_{anm_name}")
            os.makedirs(anm_folder, exist_ok=True)
            anm_in_folder = os.path.join(anm_folder, os.path.basename(anm_path))
            import shutil
            shutil.copy2(anm_path, anm_in_folder)
            
            success, error_msg = convert_skl_skn_anm_to_gltf_with_lol2gltf(temp_skl, temp_skn, temp_gltf_with_anm, anm_folder)
            if not success:
                self.report({'ERROR'}, f"Failed to create glTF with animation: {error_msg}")
                print(f"[lol_league_v4] Step 4: FAILED - {error_msg}")
                # Cleanup
                try:
                    os.remove(temp_skl)
                    os.remove(temp_skn)
                    shutil.rmtree(anm_folder, ignore_errors=True)
                except:
                    pass
                return {'CANCELLED'}
            print(f"[lol_league_v4] Step 4: SUCCESS - Created glTF with animation")
            
            # Step 5: Import the glTF (creates new skeleton/mesh with animation)
            self.report({'INFO'}, "Step 5: Importing glTF with animation...")
            new_armature, new_mesh = import_gltf_to_blender(temp_gltf_with_anm, context, scale_factor)
            
            if not new_armature:
                self.report({'ERROR'}, "Failed to import glTF with animation")
                print(f"[lol_league_v4] Step 5: FAILED - Could not import glTF")
                return {'CANCELLED'}
            
            print(f"[lol_league_v4] Step 5: SUCCESS - Imported armature and mesh with animation")
            
            # Find the new skinned_mesh object (parent of armature or mesh)
            new_skinned_mesh_obj = None
            if new_armature and new_armature.parent:
                new_skinned_mesh_obj = new_armature.parent
            elif new_mesh and new_mesh.parent:
                new_skinned_mesh_obj = new_mesh.parent
            
            # Restore the original skinned_mesh name if we had one
            if new_skinned_mesh_obj and old_skinned_mesh_name:
                new_skinned_mesh_obj.name = old_skinned_mesh_name
                print(f"[lol_league_v4] Restored skinned_mesh name to: {old_skinned_mesh_name}")
            
            # Store metadata (using values we saved before deleting old objects)
            if new_armature:
                new_armature['lol_version'] = 'v4'
                new_armature['lol_skl_path'] = old_skl_path
                # Store original ANM filename (without extension) for export default
                new_armature['lol_anm_original_name'] = anm_name
                new_armature['lol_skn_path'] = old_skn_path
                new_armature['lol_scale_factor'] = scale_factor
                # Store ANM path
                if anm_path not in old_anm_paths:
                    old_anm_paths.append(anm_path)
                new_armature['lol_anm_paths'] = old_anm_paths
            
            # Select new armature
            context.view_layer.objects.active = new_armature
            new_armature.select_set(True)
            if new_mesh:
                new_mesh.select_set(True)
            
            # Cleanup temp files
            try:
                os.remove(temp_gltf_export)
                os.remove(temp_skl)
                os.remove(temp_skn)
                os.remove(temp_gltf_with_anm)
                shutil.rmtree(anm_folder, ignore_errors=True)
            except Exception as e:
                print(f"[lol_league_v4] WARNING: Could not clean up temp files: {e}")
            
            self.report({'INFO'}, f"Successfully imported animation '{anm_name}' (preserved edits, replaced with animated version)")
            return {'FINISHED'}
            
        except Exception as e:
            import traceback
            error_msg = f"Unexpected error: {e}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            traceback.print_exc()
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}
    


def menu_func_import(self, context):
    self.layout.operator(LOLLeagueImportANM_V2.bl_idname, text="LoL ANM Animation (V2)")


def register():
    bpy.utils.register_class(LOLLeagueImportANM_V2)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(LOLLeagueImportANM_V2)

