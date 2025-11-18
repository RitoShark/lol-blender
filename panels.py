"""
UI Panels for LoL Blender
"""

import bpy
from bpy.types import Panel

class LOLLeaguePanel_V2(Panel):
    """Main panel for LoL Blender"""
    bl_label = "LoL Blender"
    bl_idname = "VIEW3D_PT_lol_blender"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'LoL Blender'
    
    def draw(self, context):
        layout = self.layout
        
        # SKN+SKL section
        box = layout.box()
        box.label(text="SKN+SKL", icon='MESH_DATA')
        row = box.row()
        row.operator("lol_league_v2.import_skn", text="Import", icon='IMPORT')
        row.operator("lol_league_v2.export_skn", text="Export", icon='EXPORT')
        
        # ANM section
        box = layout.box()
        box.label(text="ANM", icon='ANIM')
        row = box.row()
        row.operator("import_scene.lol_anm_v2", text="Import", icon='IMPORT')
        row.operator("export_scene.lol_anm_v4", text="Export", icon='EXPORT')
        
        # SCB section
        box = layout.box()
        box.label(text="SCB (Static Objects)", icon='MESH_CUBE')
        row = box.row()
        row.operator("lol_league_v4.import_scb", text="Import", icon='IMPORT')
        row.operator("lol_league_v4.export_scb", text="Export", icon='EXPORT')
        
        # SCO section
        box = layout.box()
        box.label(text="SCO (Static Objects with Pivot)", icon='BONE_DATA')
        row = box.row()
        row.operator("lol_league_v4.import_sco", text="Import", icon='IMPORT')
        row.operator("lol_league_v4.export_sco", text="Export", icon='EXPORT')
        
        # Limit to 4 Influences button
        box = layout.box()
        box.operator("lol_league_v4.limit_influences", text="Limit to 4 Influences", icon='MODIFIER_ON')
        
        # Show metadata if armature is selected
        if context.active_object and context.active_object.type == 'ARMATURE':
            arm_obj = context.active_object
            if arm_obj.get('lol_version') == 'v2':
                box = layout.box()
                box.label(text="Armature Info", icon='ARMATURE_DATA')
                box.label(text=f"Name: {arm_obj.name}")
                
                skl_path = arm_obj.get('lol_skl_path', 'None')
                if skl_path != 'None':
                    import os
                    box.label(text=f"SKL: {os.path.basename(skl_path)}")
                
                anm_paths = arm_obj.get('lol_anm_paths', [])
                box.label(text=f"Animations: {len(anm_paths)}")


class UV_CORNER_PT_panel(Panel):
    """UV Corner Placement Panel for UV Editor"""
    bl_label = "UV Corners"
    bl_idname = "IMAGE_EDITOR_PT_uv_corners"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'UV Corners'
    
    @classmethod
    def poll(cls, context):
        # Only show in UV editing mode (Image Editor)
        return (context.space_data and 
                context.space_data.type == 'IMAGE_EDITOR' and
                context.active_object and 
                context.active_object.type == 'MESH' and
                context.active_object.data.uv_layers.active)
    
    def draw(self, context):
        layout = self.layout
        
        # Corner buttons in a 2x2 grid with corner symbols
        col = layout.column(align=True)
        
        # Top row
        row = col.row(align=True)
        # Top Left - corner symbol ◸
        row.operator("uv.corner_top_left", text="◸", icon='NONE')
        # Top Right - corner symbol ◹
        row.operator("uv.corner_top_right", text="◹", icon='NONE')
        
        # Bottom row
        row = col.row(align=True)
        # Bottom Left - corner symbol ◺
        row.operator("uv.corner_bottom_left", text="◺", icon='NONE')
        # Bottom Right - corner symbol ◿
        row.operator("uv.corner_bottom_right", text="◿", icon='NONE')

# Note: Registration is handled in __init__.py

