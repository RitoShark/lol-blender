"""
ANM Export Operator for V4
Exports Blender animations to League of Legends ANM format using glTF bridge
"""

import bpy
import os
import tempfile
from bpy.types import Operator
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ExportHelper

class LOLLeagueExportANM_V4(Operator, ExportHelper):
    """Export Blender animation to League of Legends ANM format"""
    bl_idname = "export_scene.lol_anm_v4"
    bl_label = "Export LoL ANM (V4 - glTF)"
    bl_description = "Export animation to ANM format using glTF bridge"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".anm"
    filter_glob: StringProperty(default="*.anm", options={'HIDDEN'})
    
    export_all_actions: BoolProperty(
        name="Export All Actions",
        description="Export all actions as separate ANM files (otherwise only active action)",
        default=False
    )
    
    def invoke(self, context, event):
        # Set default filename from imported file if available
        armature_obj = context.active_object
        if not armature_obj or armature_obj.type != 'ARMATURE':
            # Try to find armature from selection
            for obj in context.selected_objects:
                if obj.type == 'ARMATURE':
                    armature_obj = obj
                    break
        
        if armature_obj:
            # Try to get original ANM name first, then fall back to original SKN name
            if 'lol_anm_original_name' in armature_obj:
                original_name = armature_obj['lol_anm_original_name']
            elif 'lol_original_name' in armature_obj:
                original_name = armature_obj['lol_original_name']
            else:
                original_name = None
            
            if original_name:
                # Get directory from blend file or use user's default
                if bpy.data.filepath:
                    default_dir = os.path.dirname(bpy.data.filepath)
                else:
                    default_dir = os.path.expanduser("~")
                self.filepath = os.path.join(default_dir, f"{original_name}.anm")
        
        return super().invoke(context, event)
    
    def execute(self, context):
        from ..io.gltf_bridge import (
            export_blender_to_gltf,
            convert_gltf_to_anm_with_lol2gltf,
            get_temp_gltf_path
        )
        
        # Get active armature
        armature_obj = context.active_object
        if not armature_obj or armature_obj.type != 'ARMATURE':
            self.report({'ERROR'}, "Please select an armature to export animation from")
            return {'CANCELLED'}
        
        # Find mesh object
        mesh_obj = None
        for obj in context.selected_objects:
            if obj.type == 'MESH' and obj.parent == armature_obj:
                mesh_obj = obj
                break
        if not mesh_obj:
            for obj in context.scene.objects:
                if obj.type == 'MESH' and obj.parent == armature_obj:
                    mesh_obj = obj
                    break
        
        if not mesh_obj:
            self.report({'ERROR'}, "No mesh found. ANM export requires a mesh.")
            return {'CANCELLED'}
        
        # Get scale factor from metadata
        scale_factor = armature_obj.get('lol_scale_factor', 0.01)
        skl_path = armature_obj.get('lol_skl_path', '')
        
        # Find skinned_mesh parent object and upscale it for export
        skinned_mesh_obj = None
        original_scale = None
        if armature_obj.parent:
            skinned_mesh_obj = armature_obj.parent
        elif mesh_obj.parent:
            skinned_mesh_obj = mesh_obj.parent
        
        # Restore skinned_mesh to original size (divide by current scale to get back to 1.0)
        # This properly reverses the 0.1x scale applied on import, accounting for any precision issues
        if skinned_mesh_obj:
            original_scale = skinned_mesh_obj.scale.copy()
            # Divide by current scale to restore to 1.0 (instead of multiplying by fixed 10.0)
            # This handles cases where scale might not be exactly 0.1 due to precision or user edits
            # Safety check: avoid division by zero
            restore_scale = (
                1.0 / original_scale.x if abs(original_scale.x) > 0.0001 else 1.0,
                1.0 / original_scale.y if abs(original_scale.y) > 0.0001 else 1.0,
                1.0 / original_scale.z if abs(original_scale.z) > 0.0001 else 1.0
            )
            skinned_mesh_obj.scale = restore_scale
            print(f"[lol_league_v4] Restored skinned_mesh '{skinned_mesh_obj.name}' scale from {original_scale} to {restore_scale} for export")
        
        # Determine output directory and filename
        output_dir = os.path.dirname(self.filepath)
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        
        try:
            # Step 1: Export Blender scene to glTF with animation
            self.report({'INFO'}, "Step 1: Exporting to glTF with animation...")
            temp_gltf = get_temp_gltf_path(f"anm_export_{base_name}")
            temp_gltf = os.path.splitext(temp_gltf)[0] + ".glb"
            
            # Store current action
            original_action = armature_obj.animation_data.action if armature_obj.animation_data else None
            
            if self.export_all_actions:
                # Export all actions
                actions_to_export = [action for action in bpy.data.actions]
                if not actions_to_export:
                    self.report({'ERROR'}, "No actions found to export")
                    return {'CANCELLED'}
                
                exported_count = 0
                for action in actions_to_export:
                    # Set action as active
                    if not armature_obj.animation_data:
                        armature_obj.animation_data_create()
                    armature_obj.animation_data.action = action
                    
                    # Export to glTF
                    action_gltf = get_temp_gltf_path(f"anm_export_{action.name}")
                    action_gltf = os.path.splitext(action_gltf)[0] + ".glb"
                    
                    success = export_blender_to_gltf(armature_obj, mesh_obj, action_gltf, export_animations=True)
                    if not success:
                        self.report({'WARNING'}, f"Failed to export action: {action.name}")
                        continue
                    
                    # Step 2: Extract ANM from glTF
                    self.report({'INFO'}, f"Step 2: Extracting ANM for {action.name}...")
                    action_output_dir = tempfile.mkdtemp()
                    
                    success, error_msg = convert_gltf_to_anm_with_lol2gltf(
                        action_gltf, 
                        action_output_dir,
                        skl_path if skl_path else None
                    )
                    
                    if not success:
                        self.report({'WARNING'}, f"Failed to extract ANM for {action.name}: {error_msg}")
                        try:
                            os.remove(action_gltf)
                        except:
                            pass
                        continue
                    
                    # Step 3: Move ANM file to output directory
                    anm_files = [f for f in os.listdir(action_output_dir) if f.endswith('.anm')]
                    if anm_files:
                        src_anm = os.path.join(action_output_dir, anm_files[0])
                        dst_anm = os.path.join(output_dir, f"{action.name}.anm")
                        import shutil
                        shutil.move(src_anm, dst_anm)
                        print(f"[lol_league_v4] Exported: {dst_anm}")
                        exported_count += 1
                    
                    # Cleanup
                    try:
                        os.remove(action_gltf)
                        import shutil
                        shutil.rmtree(action_output_dir, ignore_errors=True)
                    except:
                        pass
                
                # Restore original action
                if armature_obj.animation_data:
                    armature_obj.animation_data.action = original_action
                
                if exported_count == 0:
                    self.report({'ERROR'}, "Failed to export any animations")
                    return {'CANCELLED'}
                
                self.report({'INFO'}, f"Successfully exported {exported_count} animation(s)")
                return {'FINISHED'}
            
            else:
                # Export only active action
                if not armature_obj.animation_data or not armature_obj.animation_data.action:
                    self.report({'ERROR'}, "No active action to export. Please select an action or enable 'Export All Actions'")
                    return {'CANCELLED'}
                
                success = export_blender_to_gltf(armature_obj, mesh_obj, temp_gltf, export_animations=True)
                if not success:
                    self.report({'ERROR'}, "Failed to export to glTF")
                    return {'CANCELLED'}
                
                print(f"[lol_league_v4] Step 1: SUCCESS - Exported to {temp_gltf}")
                
                # Step 2: Extract ANM from glTF
                self.report({'INFO'}, "Step 2: Extracting ANM from glTF...")
                temp_output_dir = tempfile.mkdtemp()
                
                success, error_msg = convert_gltf_to_anm_with_lol2gltf(
                    temp_gltf, 
                    temp_output_dir,
                    skl_path if skl_path else None
                )
                
                if not success:
                    self.report({'ERROR'}, f"Failed to extract ANM: {error_msg}")
                    try:
                        os.remove(temp_gltf)
                    except:
                        pass
                    return {'CANCELLED'}
                
                print(f"[lol_league_v4] Step 2: SUCCESS - Extracted ANM")
                
                # Step 3: Move ANM file to final destination
                anm_files = [f for f in os.listdir(temp_output_dir) if f.endswith('.anm')]
                if not anm_files:
                    self.report({'ERROR'}, "No ANM files were created")
                    return {'CANCELLED'}
                
                # Use the first ANM file (should only be one for single action export)
                src_anm = os.path.join(temp_output_dir, anm_files[0])
                import shutil
                shutil.move(src_anm, self.filepath)
                
                print(f"[lol_league_v4] Step 3: SUCCESS - Moved to {self.filepath}")
                
                # Cleanup
                try:
                    os.remove(temp_gltf)
                    shutil.rmtree(temp_output_dir, ignore_errors=True)
                except Exception as e:
                    print(f"[lol_league_v4] WARNING: Could not clean up temp files: {e}")
                
                self.report({'INFO'}, f"Successfully exported animation: {base_name}.anm")
                return {'FINISHED'}
            
        except Exception as e:
            import traceback
            error_msg = f"Unexpected error: {e}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            traceback.print_exc()
            self.report({'ERROR'}, error_msg)
            return {'CANCELLED'}
        finally:
            # Restore original scale
            if skinned_mesh_obj and original_scale:
                skinned_mesh_obj.scale = original_scale
                print(f"[lol_league_v4] Restored skinned_mesh '{skinned_mesh_obj.name}' scale to original")


def menu_func_export(self, context):
    self.layout.operator(LOLLeagueExportANM_V4.bl_idname, text="LoL ANM Animation (V4)")
