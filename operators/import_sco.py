"""
SCO Import Operator for V4
Native SCO (Static Object) importer for League of Legends
Similar to SCB but text-based and includes pivot point (bone)
"""

import bpy
import os
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector


def sanitize_name(name):
    """Sanitize a name to be safe for Blender (valid UTF-8, no null bytes)"""
    if not name:
        return "unnamed"
    try:
        # Try to decode as UTF-8, replace invalid characters
        if isinstance(name, bytes):
            name = name.decode('utf-8', errors='replace')
        # Remove null bytes and other problematic characters
        name = name.replace('\x00', '').replace('\x01', '').replace('\x02', '')
        # Limit length (Blender has name length limits)
        if len(name) > 63:
            name = name[:63]
        return name if name else "unnamed"
    except Exception:
        return "unnamed"


class LOLLeagueImportSCO_V4(Operator, ImportHelper):
    """Import League of Legends SCO (Static Object)"""
    bl_idname = "lol_league_v4.import_sco"
    bl_label = "Import LoL SCO (V4)"
    bl_description = "Import SCO static object mesh with pivot point"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".sco"
    filter_glob: StringProperty(default="*.sco", options={'HIDDEN'})
    
    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Scale factor for import (0.01 = 1% of original size)",
        default=0.01,
        min=0.0001,
        max=100.0
    )
    
    def execute(self, context):
        sco_path = self.filepath
        
        if not os.path.exists(sco_path):
            self.report({'ERROR'}, f"File not found: {sco_path}")
            return {'CANCELLED'}
        
        try:
            # Read SCO file
            sco_data = self.read_sco(sco_path)
            
            # Create mesh in Blender
            self.create_mesh(context, sco_data, self.scale_factor)
            
            self.report({'INFO'}, f"Successfully imported {os.path.basename(sco_path)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import SCO: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def read_sco(self, path):
        """Read SCO file and return data structure"""
        with open(path, 'r') as f:
            lines = f.readlines()
            lines = [line.rstrip('\n\r') for line in lines]
        
        # Check signature
        if not lines or lines[0] != '[ObjectBegin]':
            raise ValueError(f"Invalid SCO file signature: {lines[0] if lines else 'empty file'}")
        
        name = None
        central = None
        pivot = None
        vertices = []
        indices = []
        uvs = []
        material = 'lambert69'
        
        index = 1  # Skip magic
        while index < len(lines):
            line = lines[index].strip()
            if not line:
                index += 1
                continue
            
            parts = line.split()
            if not parts:
                index += 1
                continue
            
            if parts[0] == 'Name=':
                name = parts[1] if len(parts) > 1 else None
            
            elif parts[0] == 'CentralPoint=':
                if len(parts) >= 4:
                    central = Vector((
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3])
                    ))
            
            elif parts[0] == 'PivotPoint=':
                if len(parts) >= 4:
                    pivot = Vector((
                        float(parts[1]),
                        float(parts[2]),
                        float(parts[3])
                    ))
            
            elif parts[0] == 'Verts=':
                if len(parts) >= 2:
                    vertex_count = int(parts[1])
                    # Read vertices
                    for i in range(vertex_count):
                        index += 1
                        if index >= len(lines):
                            break
                        vert_parts = lines[index].split()
                        if len(vert_parts) >= 3:
                            x, y, z = float(vert_parts[0]), float(vert_parts[1]), float(vert_parts[2])
                            # Transform from SCB coordinate system to Blender
                            # Import does: file -> Blender: (-x, -z, y)
                            vertices.append(Vector((-x, -z, y)))
            
            elif parts[0] == 'Faces=':
                if len(parts) >= 2:
                    face_count = int(parts[1])
                    # Read faces
                    for i in range(face_count):
                        index += 1
                        if index >= len(lines):
                            break
                        # Replace tabs with spaces and split
                        face_line = lines[index].replace('\t', ' ').split()
                        if len(face_line) < 11:
                            continue
                        
                        # Face format: 3 <idx0> <idx1> <idx2> <material> <u1> <v1> <u2> <v2> <u3> <v3>
                        idx0, idx1, idx2 = int(face_line[1]), int(face_line[2]), int(face_line[3])
                        
                        # Skip degenerate faces
                        if idx0 == idx1 or idx1 == idx2 or idx2 == idx0:
                            continue
                        
                        indices.extend([idx0, idx1, idx2])
                        
                        # Get material (first face sets it)
                        if i == 0:
                            material = face_line[4] if len(face_line) > 4 else 'lambert69'
                        
                        # Get UVs (per-face format)
                        uvs.append(Vector((float(face_line[5]), float(face_line[6]))))  # u1, v1
                        uvs.append(Vector((float(face_line[7]), float(face_line[8]))))  # u2, v2
                        uvs.append(Vector((float(face_line[9]), float(face_line[10]))))  # u3, v3
            
            index += 1
        
        # Transform central point from SCB coordinate system to Blender
        if central is not None:
            central = Vector((-central.x, -central.z, central.y))
        
        # Transform pivot point from SCB coordinate system to Blender
        if pivot is not None:
            pivot = Vector((-pivot.x, -pivot.z, pivot.y))
        
        # Sanitize name
        safe_name = sanitize_name(name or os.path.splitext(os.path.basename(path))[0])
        
        return {
            'name': safe_name,
            'vertices': vertices,
            'indices': indices,
            'uvs': uvs,
            'material': sanitize_name(material),
            'central': central or Vector((0, 0, 0)),
            'pivot': pivot
        }
    
    def create_mesh(self, context, sco_data, scale_factor):
        """Create Blender mesh from SCO data"""
        # Create mesh
        mesh = bpy.data.meshes.new(sco_data['name'])
        
        # Convert vertices (apply scale and offset by central point)
        # Note: Y and Z are already swapped during import
        vertices = []
        for v in sco_data['vertices']:
            # Offset by central point, then scale
            pos = (v - sco_data['central']) * scale_factor
            vertices.append((pos.x, pos.y, pos.z))
        
        # Create mesh from vertices and faces
        # SCO stores per-face UVs, but we need to convert to per-vertex
        face_count = len(sco_data['indices']) // 3
        faces = []
        face_uvs = []
        
        for i in range(face_count):
            idx = i * 3
            face_indices = [
                sco_data['indices'][idx],
                sco_data['indices'][idx + 1],
                sco_data['indices'][idx + 2]
            ]
            faces.append(face_indices)
            
            # Get UVs for this face
            face_uvs.append([
                sco_data['uvs'][idx],
                sco_data['uvs'][idx + 1],
                sco_data['uvs'][idx + 2]
            ])
        
        # Create mesh
        mesh.from_pydata(vertices, [], faces)
        mesh.update()
        
        # Add UV layer
        uv_layer = mesh.uv_layers.new(name="UVMap")
        
        # Assign UVs (per-face UVs need to be mapped to loops)
        for face_idx, face in enumerate(mesh.polygons):
            face_uv = face_uvs[face_idx]
            for loop_idx, loop in enumerate(face.loop_indices):
                uv = face_uv[loop_idx]
                # Flip V coordinate (Blender uses bottom-left origin)
                uv_layer.data[loop].uv = (uv.x, 1.0 - uv.y)
        
        # Create object
        obj = bpy.data.objects.new(sco_data['name'], mesh)
        context.collection.objects.link(obj)
        
        # Set location to central point (scaled)
        obj.location = sco_data['central'] * scale_factor
        
        # Create material
        mat = bpy.data.materials.new(name=sco_data['material'])
        mat.use_nodes = True
        mesh.materials.append(mat)
        
        # Create pivot bone if pivot point exists
        # Maya creates: joint at position = central - pivot
        if sco_data['pivot'] is not None:
            # Calculate bone position: central - pivot (in Blender coordinate space)
            # Pivot is stored as offset from central, so bone position = central - pivot
            bone_world_pos = sco_data['central'] - sco_data['pivot']
            bone_world_pos_scaled = bone_world_pos * scale_factor
            
            # Create armature with sanitized name
            armature_name = sanitize_name(f"armature_{sco_data['name']}")
            armature_data = bpy.data.armatures.new(name=armature_name)
            armature_obj = bpy.data.objects.new(armature_name, armature_data)
            context.collection.objects.link(armature_obj)
            
            # Enter edit mode to add bone
            context.view_layer.objects.active = armature_obj
            bpy.ops.object.mode_set(mode='EDIT')
            
            # Create bone at pivot position with sanitized name
            bone_name = sanitize_name(f"pivot_{sco_data['name']}")
            bone = armature_data.edit_bones.new(bone_name)
            bone.head = bone_world_pos_scaled
            bone.tail = bone_world_pos_scaled + Vector((0, 0, 0.1 * scale_factor))  # Small bone
            
            # Store the bone name before exiting edit mode (it's already sanitized)
            safe_bone_name = bone_name
            
            # Exit edit mode
            bpy.ops.object.mode_set(mode='OBJECT')
            
            # Parent mesh to armature
            obj.parent = armature_obj
            obj.parent_type = 'OBJECT'
            
            # Add armature modifier
            arm_mod = obj.modifiers.new(armature_data.name, 'ARMATURE')
            arm_mod.object = armature_obj
            arm_mod.use_vertex_groups = False
            arm_mod.use_bone_envelopes = True
            
            # Create vertex group for the bone using the sanitized name
            # We use the name we stored earlier since accessing bone.name after edit mode
            # might have encoding issues
            vg = obj.vertex_groups.new(name=safe_bone_name)
            # Assign all vertices to this bone
            vg.add(range(len(vertices)), 1.0, 'REPLACE')
            
            # Select armature
            armature_obj.select_set(True)
            context.view_layer.objects.active = armature_obj
        
        # Store metadata
        obj['lol_sco_path'] = self.filepath
        obj['lol_sco_central'] = tuple(sco_data['central'])
        if sco_data['pivot'] is not None:
            obj['lol_sco_pivot'] = tuple(sco_data['pivot'])
        # Store original filename (without extension) for export default
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        obj['lol_sco_original_name'] = base_name
        
        # Select and make active
        obj.select_set(True)
        if sco_data['pivot'] is None:
            context.view_layer.objects.active = obj
        
        return obj


def menu_func_import(self, context):
    self.layout.operator(LOLLeagueImportSCO_V4.bl_idname, text="LoL SCO (V4)")

