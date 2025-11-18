"""
SKL+SKN Export Operator for V4
Uses glTF bridge for reliable coordinate conversion (preserves bind matrices better than FBX)
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty
from bpy_extras.io_utils import ExportHelper

class LOLLeagueExportSKN_V2(Operator, ExportHelper):
    """Export League of Legends SKN+SKL using glTF bridge"""
    bl_idname = "lol_league_v2.export_skn"
    bl_label = "Export LoL SKN+SKL (V4 - glTF)"
    bl_description = "Export SKN mesh and SKL skeleton using glTF bridge (preserves bind matrices)"
    bl_options = {'REGISTER'}
    
    filename_ext = ".skn"
    filter_glob: StringProperty(default="*.skn", options={'HIDDEN'})
    
    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Scale factor for export (0.01 = 1% of original size)",
        default=0.01,
        min=0.0001,
        max=100.0
    )
    
    def invoke(self, context, event):
        # Set default filename from imported file if available
        armature_obj = None
        if context.active_object and context.active_object.type == 'ARMATURE':
            armature_obj = context.active_object
        elif context.active_object and context.active_object.type == 'MESH':
            if context.active_object.parent and context.active_object.parent.type == 'ARMATURE':
                armature_obj = context.active_object.parent
        
        # Find armature from selection
        if not armature_obj:
            for obj in context.selected_objects:
                if obj.type == 'ARMATURE':
                    armature_obj = obj
                    break
        
        if armature_obj and 'lol_original_name' in armature_obj:
            # Use the original imported filename
            original_name = armature_obj['lol_original_name']
            # Get directory from blend file or use user's default
            if bpy.data.filepath:
                default_dir = os.path.dirname(bpy.data.filepath)
            else:
                default_dir = os.path.expanduser("~")
            self.filepath = os.path.join(default_dir, f"{original_name}.skn")
        
        return super().invoke(context, event)
    
    def execute(self, context):
        from ..io.gltf_bridge import export_blender_to_gltf, get_temp_gltf_path
        
        # Export to glTF, then convert glTF→SKN/SKL using lol2gltf
        
        # Get selected objects
        armature_obj = None
        mesh_obj = None
        
        if context.active_object and context.active_object.type == 'ARMATURE':
            armature_obj = context.active_object
        elif context.active_object and context.active_object.type == 'MESH':
            mesh_obj = context.active_object
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                armature_obj = mesh_obj.parent
        
        # Find armature and mesh from selection
        for obj in context.selected_objects:
            if obj.type == 'ARMATURE':
                armature_obj = obj
            elif obj.type == 'MESH':
                mesh_obj = obj
                # If mesh is selected but armature not found yet, check mesh's parent
                if not armature_obj and mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                    armature_obj = mesh_obj.parent
        
        # If mesh found but no armature, try to find from mesh's parent or modifier
        if mesh_obj and not armature_obj:
            # Check parent first
            if mesh_obj.parent and mesh_obj.parent.type == 'ARMATURE':
                armature_obj = mesh_obj.parent
            else:
                # Check Armature modifier
                for mod in mesh_obj.modifiers:
                    if mod.type == 'ARMATURE' and mod.object and mod.object.type == 'ARMATURE':
                        armature_obj = mod.object
                        break
        
        if not mesh_obj:
            self.report({'ERROR'}, "Select a mesh object to export")
            return {'CANCELLED'}
        
        if not armature_obj:
            self.report({'ERROR'}, "No armature found. Cannot export SKL without skeleton. Make sure the mesh has an Armature modifier or is parented to an armature.")
            return {'CANCELLED'}
        
        # Check joint limit (max 256 joints, same as Maya exporter)
        bone_count = len(armature_obj.data.bones)
        if bone_count > 256:
            self.report({'ERROR'}, f"Too many bones found: {bone_count}, max allowed: 256 bones. Please reduce the number of bones in your armature.")
            return {'CANCELLED'}
        
        # Check vertex count limit (max 65535 vertices, SKN format uses ushort for indices)
        vertex_count = len(mesh_obj.data.vertices)
        if vertex_count > 65535:
            self.report({'ERROR'}, f"Too many vertices found: {vertex_count}, max allowed: 65535 vertices. Please reduce the vertex count (decimate, split mesh, etc.).")
            return {'CANCELLED'}
        
        # Check vertex influences (max 4 per vertex, same as Maya exporter)
        invalid_vertices = []
        for vertex in mesh_obj.data.vertices:
            influence_count = sum(1 for g in vertex.groups if g.weight > 0.001)
            if influence_count > 4:
                invalid_vertices.append(vertex.index)
        
        if invalid_vertices:
            self.report({'ERROR'}, f"{len(invalid_vertices)} vertices have more than 4 influences. Use 'Limit to 4 Influences' button to fix.")
            return {'CANCELLED'}
        
        # Get output paths
        skn_path = self.filepath
        skl_path = os.path.splitext(skn_path)[0] + ".skl"
        base_name = os.path.splitext(os.path.basename(skn_path))[0]
        
        # Check if we have a cached original glTF (preserves bind matrices better)
        # NOTE: If the cached glTF was created with old buggy code, it may be malformed.
        # In that case, we should regenerate it by re-importing SKN/SKL.
        cached_gltf = None
        if armature_obj and 'lol_base_gltf_path' in armature_obj:
            cached_gltf = armature_obj['lol_base_gltf_path']
            if os.path.exists(cached_gltf):
                print(f"[lol_league_v4] Using cached original glTF: {cached_gltf}")
                self.report({'INFO'}, "Using cached original glTF (preserves bind matrices)")
            else:
                cached_gltf = None
                print(f"[lol_league_v4] WARNING: Cached glTF not found: {armature_obj['lol_base_gltf_path']}")
        
        # If cached glTF fails, fall back to exporting from Blender
        use_cached = cached_gltf is not None
        
        # Step 1: Export Blender scene to glTF (or use cached)
        # Try cached first, but if it fails, fall back to exporting from Blender
        temp_gltf = None
        scale_factor = self.scale_factor
        
        if use_cached:
            temp_gltf = cached_gltf
            # Get scale factor from metadata
            scale_factor = armature_obj.get('lol_scale_factor', self.scale_factor)
        
        # Always export from Blender as fallback (cached might be malformed)
        # For now, let's always export from Blender to ensure it's correct
        self.report({'INFO'}, "Exporting to glTF...")
        temp_gltf = get_temp_gltf_path(f"{base_name}_export")
        temp_gltf = os.path.splitext(temp_gltf)[0] + ".glb"  # Use binary format
        
        try:
            success = export_blender_to_gltf(armature_obj, mesh_obj, temp_gltf)
            if not success:
                self.report({'ERROR'}, "Failed to export to glTF. Check console for details.")
                return {'CANCELLED'}
        except ValueError as e:
            # Name validation error - show detailed message
            error_msg = str(e)
            # Show first line as main error in popup
            first_line = error_msg.split('\n')[0] if '\n' in error_msg else error_msg
            self.report({'ERROR'}, first_line)
            
            # Report full error message to Info Log (replace newlines with spaces for single-line report)
            # The Info Log will show this as the operator's error report
            error_msg_single_line = error_msg.replace('\n', ' | ')
            self.report({'ERROR'}, error_msg_single_line)
            
            # Also print to console with full formatting
            print(f"[lol_league_v4] Full error details:\n{error_msg}")
            return {'CANCELLED'}
        
        # Step 2: Convert glTF to SKN/SKL using lol2gltf
        self.report({'INFO'}, "Converting glTF to SKN/SKL using lol2gltf...")
        from ..io.gltf_bridge import convert_gltf_to_skl_skn_with_lol2gltf
        
        success, error_msg = convert_gltf_to_skl_skn_with_lol2gltf(temp_gltf, skn_path, skl_path)
        if not success:
            self.report({'ERROR'}, f"Failed to convert glTF to SKN/SKL: {error_msg}")
            print(f"[lol_league_v4] ERROR: {error_msg}")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Exported SKN: {os.path.basename(skn_path)}")
        self.report({'INFO'}, f"Exported SKL: {os.path.basename(skl_path)}")
        return {'FINISHED'}

def register():
    bpy.utils.register_class(LOLLeagueExportSKN_V2)

def unregister():
    bpy.utils.unregister_class(LOLLeagueExportSKN_V2)

