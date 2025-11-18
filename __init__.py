"""
LoL Blender - League of Legends Blender Addon
Import/Export League of Legends game files (SKL, SKN, ANM, SCB, SCO).

Uses pyritofile for reading LoL files and glTF bridge for conversion.
Supports character models, animations, and static objects.
"""

bl_info = {
    "name": "LoL Blender",
    "author": "LoL Blender Contributors",
    "version": (1, 0, 0),
    "blender": (3, 0, 0),
    "location": "File > Import-Export, View3D > Sidebar > LoL Blender",
    "description": "Import/Export League of Legends game files (SKL, SKN, ANM, SCB, SCO)",
    "warning": "",
    "doc_url": "https://github.com/sxrmss/lol-blender",
    "category": "Import-Export",
}

import bpy
from . import operators, panels
from bpy_extras.io_utils import poll_file_object_drop

classes = []
_menu_funcs = []
_file_handlers = []

def register_classes():
    """Register all addon classes"""
    global classes, _menu_funcs
    from .operators import import_skl_skn, export_skl_skn, import_anm, export_anm, uv_corners, import_scb, export_scb, import_sco, export_sco, limit_influences
    
    classes = []
    
    # Register operators only if they imported successfully
    if import_skl_skn is not None:
        classes.append(import_skl_skn.LOLLeagueImportSKN_V2)
    if export_skl_skn is not None:
        classes.append(export_skl_skn.LOLLeagueExportSKN_V2)
    if import_anm is not None:
        classes.append(import_anm.LOLLeagueImportANM_V2)
    if export_anm is not None:
        classes.append(export_anm.LOLLeagueExportANM_V4)
    if import_scb is not None:
        classes.append(import_scb.LOLLeagueImportSCB_V4)
    if export_scb is not None:
        classes.append(export_scb.LOLLeagueExportSCB_V4)
    if import_sco is not None:
        classes.append(import_sco.LOLLeagueImportSCO_V4)
    if export_sco is not None:
        classes.append(export_sco.LOLLeagueExportSCO_V4)
    if limit_influences is not None:
        classes.append(limit_influences.LOLLeagueLimitInfluences_V4)
    
    # File handler for drag and drop support
    if import_skl_skn is not None:
        class IO_FH_skn_skl(bpy.types.FileHandler):
            bl_idname = "IO_FH_skn_skl"
            bl_label = "LoL SKN+SKL"
            bl_import_operator = "lol_league_v2.import_skn"
            bl_file_extensions = ".skn;.skl"
            
            @classmethod
            def poll_drop(cls, context):
                return poll_file_object_drop(context)
        
        classes.append(IO_FH_skn_skl)
        _file_handlers.append(IO_FH_skn_skl)
    
    # Always register panels
    classes.append(panels.LOLLeaguePanel_V2)
    
    # UV Corner operators
    if uv_corners is not None:
        classes.extend([
            uv_corners.UV_CORNER_OT_top_left,
            uv_corners.UV_CORNER_OT_top_right,
            uv_corners.UV_CORNER_OT_bottom_left,
            uv_corners.UV_CORNER_OT_bottom_right,
        ])
        # UV Corner panel
        classes.append(panels.UV_CORNER_PT_panel)
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register menu functions (classes are already registered above, so only add menu items)
    if import_anm is not None:
        bpy.types.TOPBAR_MT_file_import.append(import_anm.menu_func_import)
        _menu_funcs.append(import_anm.menu_func_import)
    
    if import_scb is not None:
        def menu_func_import_scb(self, context):
            self.layout.operator(import_scb.LOLLeagueImportSCB_V4.bl_idname, text="LoL SCB (V4)")
        
        bpy.types.TOPBAR_MT_file_import.append(menu_func_import_scb)
        _menu_funcs.append(menu_func_import_scb)
    
    if import_sco is not None:
        bpy.types.TOPBAR_MT_file_import.append(import_sco.menu_func_import)
        _menu_funcs.append(import_sco.menu_func_import)
    
    # Add export menu items
    if export_skl_skn is not None:
        def menu_func_export_skn(self, context):
            self.layout.operator(export_skl_skn.LOLLeagueExportSKN_V2.bl_idname, text="LoL SKN+SKL (V4)")
        
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export_skn)
        _menu_funcs.append(menu_func_export_skn)
    
    if export_anm is not None:
        def menu_func_export_anm(self, context):
            self.layout.operator(export_anm.LOLLeagueExportANM_V4.bl_idname, text="LoL ANM Animation (V4)")
        
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export_anm)
        _menu_funcs.append(menu_func_export_anm)
    
    if export_scb is not None:
        def menu_func_export_scb(self, context):
            self.layout.operator(export_scb.LOLLeagueExportSCB_V4.bl_idname, text="LoL SCB (V4)")
        
        bpy.types.TOPBAR_MT_file_export.append(menu_func_export_scb)
        _menu_funcs.append(menu_func_export_scb)
    
    if export_sco is not None:
        bpy.types.TOPBAR_MT_file_export.append(export_sco.menu_func_export)
        _menu_funcs.append(export_sco.menu_func_export)
    
    print("[LoL Blender] Registered operators:")
    if export_skl_skn is not None:
        print(f"  - {export_skl_skn.LOLLeagueExportSKN_V2.bl_idname}")
    if export_anm is not None:
        print(f"  - {export_anm.LOLLeagueExportANM_V4.bl_idname}")
    if export_scb is not None:
        print(f"  - {export_scb.LOLLeagueExportSCB_V4.bl_idname}")
    if import_sco is not None:
        print(f"  - {import_sco.LOLLeagueImportSCO_V4.bl_idname}")
    if export_sco is not None:
        print(f"  - {export_sco.LOLLeagueExportSCO_V4.bl_idname}")
    print(f"[LoL Blender] Added {len(_menu_funcs)} menu functions")

def unregister_classes():
    """Unregister all addon classes"""
    global _menu_funcs
    # Unregister menu functions
    from .operators import import_anm, import_sco, export_sco
    
    # Determine which menu functions are imports vs exports
    import_menu_funcs = []
    if import_anm is not None:
        import_menu_funcs.append(import_anm.menu_func_import)
    if import_sco is not None:
        import_menu_funcs.append(import_sco.menu_func_import)
    
    for menu_func in _menu_funcs:
        try:
            # Try import menu first
            if menu_func in import_menu_funcs:
                bpy.types.TOPBAR_MT_file_import.remove(menu_func)
            else:
                # Try export menu
                try:
                    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
                except ValueError:
                    # If not in export, try import (for locally defined functions)
                    try:
                        bpy.types.TOPBAR_MT_file_import.remove(menu_func)
                    except ValueError:
                        pass  # Not found in either menu
        except ValueError:
            pass  # Menu function already removed
    
    _menu_funcs.clear()
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

def register():
    """Register addon"""
    try:
        register_classes()
        print("[LoL Blender] Successfully registered all operators and menu items")
    except Exception as e:
        print(f"[LoL Blender] ERROR during registration: {e}")
        import traceback
        traceback.print_exc()
        raise

def unregister():
    """Unregister addon"""
    unregister_classes()
    print("[LoL Blender] Unregistered")

if __name__ == "__main__":
    register()

