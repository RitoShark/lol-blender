"""
SCB Import Operator for V4
Native SCB (Static Object Binary) importer for League of Legends
"""

import bpy
import os
import struct
import math
from bpy.types import Operator
from bpy.props import StringProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper
from mathutils import Vector


class LOLLeagueImportSCB_V4(Operator, ImportHelper):
    """Import League of Legends SCB (Static Object Binary)"""
    bl_idname = "lol_league_v4.import_scb"
    bl_label = "Import LoL SCB (V4)"
    bl_description = "Import SCB static object mesh"
    bl_options = {'REGISTER', 'UNDO'}
    
    filename_ext = ".scb"
    filter_glob: StringProperty(default="*.scb", options={'HIDDEN'})
    
    scale_factor: FloatProperty(
        name="Scale Factor",
        description="Scale factor for import (0.01 = 1% of original size)",
        default=0.01,
        min=0.0001,
        max=100.0
    )
    
    def execute(self, context):
        scb_path = self.filepath
        
        if not os.path.exists(scb_path):
            self.report({'ERROR'}, f"File not found: {scb_path}")
            return {'CANCELLED'}
        
        try:
            # Read SCB file
            scb_data = self.read_scb(scb_path)
            
            # Create mesh in Blender
            self.create_mesh(context, scb_data, self.scale_factor)
            
            self.report({'INFO'}, f"Successfully imported {os.path.basename(scb_path)}")
            return {'FINISHED'}
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to import SCB: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}
    
    def read_scb(self, path):
        """Read SCB file and return data structure"""
        with open(path, 'rb') as f:
            # Read magic
            magic = f.read(8).decode('ascii', errors='ignore')
            if magic != 'r3d2Mesh':
                raise ValueError(f"Invalid SCB file signature: {magic}")
            
            # Read version
            major, minor = struct.unpack('<HH', f.read(4))
            if not ((major == 3 and minor == 2) or (major == 2 and minor == 1)):
                raise ValueError(f"Unsupported SCB version: {major}.{minor}")
            
            # Skip name padding (128 bytes)
            f.seek(128, 1)
            
            # Read counts and flag
            vertex_count, face_count, scb_flag = struct.unpack('<III', f.read(12))
            
            # Read bounding box (6 floats = 24 bytes)
            bbox = struct.unpack('<6f', f.read(24))
            
            # Read vertex type (only for version 3.2)
            vertex_type = 0
            if major == 3 and minor == 2:
                vertex_type = struct.unpack('<I', f.read(4))[0]
            
            # Read vertices (swap Y and Z, rotate around Z by 180 degrees)
            vertices = []
            for i in range(vertex_count):
                x, y, z = struct.unpack('<fff', f.read(12))
                # Swap Y and Z: SCB uses Y-up, Blender uses Z-up
                # Rotate around Z by 180 degrees: X' = -X, Y' = -Y
                # After swap: (x, y, z) -> (x, z, y)
                # Rotate 180°: (x, z) -> (-x, -z, y)
                vertices.append(Vector((-x, -z, y)))
            
            # Skip vertex colors if present
            if vertex_type == 1:
                f.seek(4 * vertex_count, 1)
            
            # Read central point (swap Y and Z, rotate around Z by 180 degrees)
            cx, cy, cz = struct.unpack('<fff', f.read(12))
            # Swap Y and Z: SCB uses Y-up, Blender uses Z-up
            # Rotate around Z by 180 degrees: X' = -X, Y' = -Y
            # After swap: (x, y, z) -> (x, z, y)
            # Rotate 180°: (x, z) -> (-x, -z, y)
            central = Vector((-cx, -cz, cy))
            
            # Read faces
            indices = []
            uvs = []
            material = None
            
            for i in range(face_count):
                # Read face indices
                idx0, idx1, idx2 = struct.unpack('<III', f.read(12))
                
                # Skip degenerate faces
                if idx0 == idx1 or idx1 == idx2 or idx2 == idx0:
                    # Still need to read material and UVs
                    f.seek(64, 1)  # Material name
                    f.seek(24, 1)  # UVs (6 floats)
                    continue
                
                indices.extend([idx0, idx1, idx2])
                
                # Read material name (64 bytes, padded)
                material_bytes = f.read(64)
                material = material_bytes.split(b'\x00')[0].decode('ascii', errors='ignore')
                
                # Read UVs (6 floats: u1, u2, u3, v1, v2, v3)
                uv_data = struct.unpack('<6f', f.read(24))
                # Convert to per-vertex UVs (per-face format)
                uvs.append(Vector((uv_data[0], uv_data[3])))  # u1, v1
                uvs.append(Vector((uv_data[1], uv_data[4])))  # u2, v2
                uvs.append(Vector((uv_data[2], uv_data[5])))  # u3, v3
        
        return {
            'name': os.path.splitext(os.path.basename(path))[0],
            'vertices': vertices,
            'indices': indices,
            'uvs': uvs,
            'material': material or 'lambert69',
            'central': central,
            'scb_flag': scb_flag
        }
    
    def create_mesh(self, context, scb_data, scale_factor):
        """Create Blender mesh from SCB data"""
        # Create mesh
        mesh = bpy.data.meshes.new(scb_data['name'])
        
        # Convert vertices (apply scale and offset by central point)
        # Note: Y and Z are already swapped during import
        vertices = []
        for v in scb_data['vertices']:
            # Offset by central point, then scale
            pos = (v - scb_data['central']) * scale_factor
            vertices.append((pos.x, pos.y, pos.z))
        
        # Create mesh from vertices and faces
        # SCB stores per-face UVs, but we need to convert to per-vertex
        # We'll create unique vertices for each face vertex if UVs differ
        
        # Build face list
        face_count = len(scb_data['indices']) // 3
        faces = []
        face_uvs = []
        
        for i in range(face_count):
            idx = i * 3
            face_indices = [
                scb_data['indices'][idx],
                scb_data['indices'][idx + 1],
                scb_data['indices'][idx + 2]
            ]
            faces.append(face_indices)
            
            # Get UVs for this face
            face_uvs.append([
                scb_data['uvs'][idx],
                scb_data['uvs'][idx + 1],
                scb_data['uvs'][idx + 2]
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
        obj = bpy.data.objects.new(scb_data['name'], mesh)
        context.collection.objects.link(obj)
        
        # Set location to central point (scaled)
        obj.location = scb_data['central'] * scale_factor
        
        # Create material
        mat = bpy.data.materials.new(name=scb_data['material'])
        mat.use_nodes = True
        mesh.materials.append(mat)
        
        # Store metadata
        obj['lol_scb_path'] = self.filepath
        obj['lol_scb_flag'] = scb_data['scb_flag']
        obj['lol_scb_central'] = tuple(scb_data['central'])
        # Store original filename (without extension) for export default
        base_name = os.path.splitext(os.path.basename(self.filepath))[0]
        obj['lol_scb_original_name'] = base_name
        
        # Select and make active
        obj.select_set(True)
        context.view_layer.objects.active = obj
        
        return obj

