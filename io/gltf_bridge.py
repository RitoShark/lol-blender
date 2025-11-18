"""
glTF Bridge - Main conversion interface using glTF format
Handles conversion between LoL files and Blender via glTF
glTF preserves bind matrices better than FBX when going through Blender
"""

import os
import bpy
import tempfile
import numpy as np
import subprocess
import shutil
from typing import Tuple, Optional
from mathutils import Matrix, Vector, Quaternion

# Try to import pygltflib for programmatic glTF creation
# Import is lazy - will be checked when needed
PYGLTF_AVAILABLE = None
pygltflib = None

def _ensure_pygltflib():
    """Ensure pygltflib is available. Returns True if available."""
    global PYGLTF_AVAILABLE, pygltflib
    
    if PYGLTF_AVAILABLE is not None:
        return PYGLTF_AVAILABLE
    
    try:
        from ..dependencies import is_pygltflib_available, _setup_bundled_dependencies
        
        # Ensure bundled dependencies path is set up
        _setup_bundled_dependencies()
        
        if is_pygltflib_available():
            import pygltflib
            PYGLTF_AVAILABLE = True
            return True
        else:
            PYGLTF_AVAILABLE = False
            return False
    except Exception as e:
        print(f"[lol_league_v4] WARNING: Failed to import pygltflib: {e}")
        PYGLTF_AVAILABLE = False
        return False

def get_temp_gltf_path(name: str) -> str:
    """Get a temporary glTF file path"""
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, f"lol_league_v4_{name}.glb")

def get_cached_gltf_path(model_name: str) -> str:
    """
    Get a cached glTF file path for ANM import.
    This stores the original SKL+SKN glTF so we can add ANM to it later.
    """
    import tempfile
    temp_root = tempfile.gettempdir()
    cache_dir = os.path.join(temp_root, "lol_league_v4_cache")
    
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    
    return os.path.join(cache_dir, f"{model_name}_base.glb")

def convert_skl_skn_to_gltf(skl_path: str, skn_path: str, gltf_path: str, scale_factor: float = 0.01) -> tuple[bool, str]:
    """
    Convert SKL+SKN to glTF using pygltflib.
    This creates a glTF file with correct bind matrices.
    
    Args:
        skl_path: Path to SKL file
        skn_path: Path to SKN file
        gltf_path: Output glTF path (.glb for binary)
        
    Returns:
        (success: bool, error_message: str)
    """
    if not _ensure_pygltflib():
        return False, "pygltflib not available. Install with: pip install pygltflib"
    
    # Import pygltflib (now available after _ensure_pygltflib)
    global pygltflib
    if pygltflib is None:
        import pygltflib
    
    try:
        from ..dependencies import is_pyritofile_available
        if not is_pyritofile_available():
            return False, "pyritofile not available"
        
        from pyritofile import SKL, SKN
        
        # Read SKL
        skl = SKL()
        skl.read(skl_path)
        print(f"[lol_league_v4] Read SKL: {len(skl.joints)} joints")
        
        # Read SKN
        skn = SKN()
        skn.read(skn_path)
        print(f"[lol_league_v4] Read SKN: {len(skn.vertices)} vertices, {len(skn.submeshes)} submeshes")
        
        # Create glTF scene (initialize with empty nodes list)
        gltf = pygltflib.GLTF2(
            scene=0,
            scenes=[pygltflib.Scene(nodes=[])],
            nodes=[],
            meshes=[],
            skins=[],
            accessors=[],
            bufferViews=[],
            buffers=[],
            materials=[],
        )
        
        # Build joint hierarchy and create nodes
        joint_nodes = []
        joint_name_to_index = {}
        
        # First pass: create all nodes with initialized children lists
        for joint_id, joint in enumerate(skl.joints):
            joint_name_to_index[joint.name] = joint_id
            
            # Create node for joint (apply scale factor to translation)
            node = pygltflib.Node(
                name=joint.name,
                translation=[
                    joint.local_translate.x * scale_factor,
                    joint.local_translate.y * scale_factor,
                    joint.local_translate.z * scale_factor
                ],
                rotation=[joint.local_rotate.x, joint.local_rotate.y, joint.local_rotate.z, joint.local_rotate.w],
                scale=[joint.local_scale.x, joint.local_scale.y, joint.local_scale.z],
                children=[],  # Initialize children list
            )
            joint_nodes.append(node)
        
        # Second pass: set parent-child relationships
        root_node_indices = []
        for joint_id, joint in enumerate(skl.joints):
            if joint.parent != -1 and joint.parent < len(joint_nodes):
                parent_id = joint.parent
                # Ensure children list exists and add this joint as child
                if joint_nodes[parent_id].children is None:
                    joint_nodes[parent_id].children = []
                if joint_id not in joint_nodes[parent_id].children:
                    joint_nodes[parent_id].children.append(joint_id)
            else:
                # This is a root node (no parent or invalid parent)
                root_node_indices.append(joint_id)
        
        # Add joint nodes to glTF first
        gltf.nodes = joint_nodes
        
        # Create mesh from SKN
        # Collect all vertex data
        all_positions = []
        all_normals = []
        all_uvs = []
        all_indices = []
        all_joints = []  # Joint indices per vertex
        all_weights = []  # Weights per vertex
        
        vertex_offset = 0
        
        for submesh in skn.submeshes:
            submesh_vertices = skn.vertices[submesh.vertex_start:submesh.vertex_start+submesh.vertex_count]
            submesh_indices = skn.indices[submesh.index_start:submesh.index_start+submesh.index_count]
            
            # Add vertices
            for vertex in submesh_vertices:
                all_positions.extend([vertex.position.x, vertex.position.y, vertex.position.z])
                all_normals.extend([vertex.normal.x, vertex.normal.y, vertex.normal.z])
                all_uvs.extend([vertex.uv.x, 1.0 - vertex.uv.y])  # Flip V coordinate
                
                # Add joint influences and weights
                joints = []
                weights = []
                for i in range(4):
                    if vertex.weights[i] > 0.0:
                        influence_id = vertex.influences[i]
                        joint_id = skl.influences[influence_id]
                        joints.append(joint_id)
                        weights.append(vertex.weights[i])
                
                # Pad to 4 joints
                while len(joints) < 4:
                    joints.append(0)
                    weights.append(0.0)
                
                all_joints.extend(joints[:4])
                all_weights.extend(weights[:4])
            
            # Add indices (offset by current vertex count)
            for idx in submesh_indices:
                all_indices.append(idx - submesh.vertex_start + vertex_offset)
            
            vertex_offset += len(submesh_vertices)
        
        # Convert to numpy arrays and apply scale factor
        positions_array = np.array(all_positions, dtype=np.float32) * scale_factor
        normals_array = np.array(all_normals, dtype=np.float32)  # Normals don't need scaling
        uvs_array = np.array(all_uvs, dtype=np.float32)
        indices_array = np.array(all_indices, dtype=np.uint32)
        joints_array = np.array(all_joints, dtype=np.uint16)
        weights_array = np.array(all_weights, dtype=np.float32)
        
        # Create buffer data
        buffer_data = bytearray()
        
        # Add positions
        pos_offset = len(buffer_data)
        buffer_data.extend(positions_array.tobytes())
        
        # Add normals
        norm_offset = len(buffer_data)
        buffer_data.extend(normals_array.tobytes())
        
        # Add UVs
        uv_offset = len(buffer_data)
        buffer_data.extend(uvs_array.tobytes())
        
        # Add joints
        joints_offset = len(buffer_data)
        buffer_data.extend(joints_array.tobytes())
        
        # Add weights
        weights_offset = len(buffer_data)
        buffer_data.extend(weights_array.tobytes())
        
        # Add indices
        indices_offset = len(buffer_data)
        buffer_data.extend(indices_array.tobytes())
        
        # Create buffer (will be updated with IBM data later)
        gltf.buffers.append(pygltflib.Buffer(byteLength=len(buffer_data)))
        
        # Create buffer views
        def add_buffer_view(buffer, byte_offset, byte_length, target=None):
            view = pygltflib.BufferView(
                buffer=0,
                byteOffset=byte_offset,
                byteLength=byte_length,
            )
            if target is not None:
                view.target = target
            gltf.bufferViews.append(view)
            return len(gltf.bufferViews) - 1
        
        pos_view = add_buffer_view(0, pos_offset, len(positions_array.tobytes()), pygltflib.ARRAY_BUFFER)
        norm_view = add_buffer_view(0, norm_offset, len(normals_array.tobytes()), pygltflib.ARRAY_BUFFER)
        uv_view = add_buffer_view(0, uv_offset, len(uvs_array.tobytes()), pygltflib.ARRAY_BUFFER)
        joints_view = add_buffer_view(0, joints_offset, len(joints_array.tobytes()), pygltflib.ARRAY_BUFFER)
        weights_view = add_buffer_view(0, weights_offset, len(weights_array.tobytes()), pygltflib.ARRAY_BUFFER)
        indices_view = add_buffer_view(0, indices_offset, len(indices_array.tobytes()), pygltflib.ELEMENT_ARRAY_BUFFER)
        
        # Create accessors
        def add_accessor(buffer_view, component_type, count, type_, min_=None, max_=None):
            acc = pygltflib.Accessor(
                bufferView=buffer_view,
                componentType=component_type,
                count=count,
                type=type_,
            )
            if min_ is not None:
                acc.min = min_
            if max_ is not None:
                acc.max = max_
            gltf.accessors.append(acc)
            return len(gltf.accessors) - 1
        
        vertex_count = len(all_positions) // 3
        pos_acc = add_accessor(pos_view, pygltflib.FLOAT, vertex_count, pygltflib.VEC3)
        norm_acc = add_accessor(norm_view, pygltflib.FLOAT, vertex_count, pygltflib.VEC3)
        uv_acc = add_accessor(uv_view, pygltflib.FLOAT, vertex_count, pygltflib.VEC2)
        joints_acc = add_accessor(joints_view, pygltflib.UNSIGNED_SHORT, vertex_count, pygltflib.VEC4)
        weights_acc = add_accessor(weights_view, pygltflib.FLOAT, vertex_count, pygltflib.VEC4)
        indices_acc = add_accessor(indices_view, pygltflib.UNSIGNED_INT, len(all_indices), pygltflib.SCALAR)
        
        # Create primitive
        primitive = pygltflib.Primitive(
            attributes={
                "POSITION": pos_acc,
                "NORMAL": norm_acc,
                "TEXCOORD_0": uv_acc,
                "JOINTS_0": joints_acc,
                "WEIGHTS_0": weights_acc,
            },
            indices=indices_acc,
        )
        
        # Create mesh
        mesh = pygltflib.Mesh(primitives=[primitive])
        gltf.meshes.append(mesh)
        
        # Create skin with inverse bind matrices
        # Use SKL's ibind (inverse bind) fields directly
        from mathutils import Matrix, Quaternion
        
        inverse_bind_matrices = []
        for joint_id, joint in enumerate(skl.joints):
            # Build inverse bind matrix from ibind fields
            # Apply scale factor to translation component
            ibind_loc = Vector([
                joint.ibind_translate.x * scale_factor,
                joint.ibind_translate.y * scale_factor,
                joint.ibind_translate.z * scale_factor
            ])
            ibind_rot = Quaternion([joint.ibind_rotate.w, joint.ibind_rotate.x, joint.ibind_rotate.y, joint.ibind_rotate.z])
            ibind_scale = Vector([joint.ibind_scale.x, joint.ibind_scale.y, joint.ibind_scale.z])
            
            # Build inverse bind matrix
            ibind_mat = Matrix.LocRotScale(ibind_loc, ibind_rot, ibind_scale)
            
            # Convert to list (column-major for glTF)
            inv_bind_list = []
            for col in range(4):
                for row in range(4):
                    inv_bind_list.append(ibind_mat[row][col])
            
            inverse_bind_matrices.extend(inv_bind_list)
        
        # Add inverse bind matrices to buffer
        ibm_offset = len(buffer_data)
        ibm_array = np.array(inverse_bind_matrices, dtype=np.float32)
        buffer_data.extend(ibm_array.tobytes())
        
        # Update buffer length
        gltf.buffers[0].byteLength = len(buffer_data)
        
        # Set binary blob for GLB export
        gltf.set_binary_blob(bytes(buffer_data))
        
        # Add buffer view and accessor for inverse bind matrices
        ibm_view = add_buffer_view(0, ibm_offset, len(ibm_array.tobytes()))
        ibm_acc = add_accessor(ibm_view, pygltflib.FLOAT, len(skl.joints), pygltflib.MAT4)
        
        # Create skin
        skin = pygltflib.Skin(
            joints=list(range(len(skl.joints))),
            inverseBindMatrices=ibm_acc,
        )
        gltf.skins.append(skin)
        
        # Create mesh node (after all joint nodes are added)
        mesh_node_index = len(gltf.nodes)
        mesh_node = pygltflib.Node(
            name="mesh",
            mesh=0,
            skin=0,
        )
        gltf.nodes.append(mesh_node)
        
        # Set scene root nodes: only include root joint nodes
        # The mesh node should be a child of the first root joint, or we can add it as a separate root
        # For now, add mesh node as a separate root (common pattern in glTF)
        scene_root_nodes = list(root_node_indices) if root_node_indices else []
        if mesh_node_index is not None:
            scene_root_nodes.append(mesh_node_index)
        gltf.scenes[0].nodes = scene_root_nodes if scene_root_nodes else [0]  # Fallback to first node if empty
        
        # Save glTF (binary if .glb, otherwise embedded JSON)
        if gltf_path.endswith('.glb'):
            # For binary glTF, embed buffer data
            gltf.buffers[0].uri = None  # Embedded buffer
            # Save binary - pygltflib handles buffer data from buffers[0]
            # We need to set the buffer data on the GLTF2 object
            # Try using save_binary with just filepath - it should read from buffers
            gltf.save_binary(gltf_path)
            # If that doesn't work, we may need to manually write the GLB file
        else:
            # For JSON glTF, save buffer separately
            buffer_filename = os.path.splitext(gltf_path)[0] + ".bin"
            with open(buffer_filename, 'wb') as f:
                f.write(buffer_data)
            gltf.buffers[0].uri = os.path.basename(buffer_filename)
            gltf.save(gltf_path)
        
        print(f"[lol_league_v4] Exported glTF: {gltf_path}")
        return True, ""
        
    except Exception as e:
        error_msg = f"Failed to convert SKN/SKL to glTF: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg

def import_gltf_to_blender(gltf_path: str, context: bpy.types.Context, scale_factor: float = 0.01, model_name: str = None) -> Tuple[Optional[bpy.types.Object], Optional[bpy.types.Object]]:
    """
    Import glTF to Blender using native importer.
    
    Args:
        gltf_path: Path to glTF file
        context: Blender context
        
    Returns:
        (armature_obj, mesh_obj) tuple, or (None, None) if failed
    """
    try:
        # Store existing objects
        existing_objects = set(bpy.data.objects)
        
        # Import glTF
        bpy.ops.import_scene.gltf(filepath=gltf_path)
        
        # Find newly imported objects
        new_objects = set(bpy.data.objects) - existing_objects
        
        # Find armature and mesh, and filter out unwanted objects (like icospheres)
        armature_obj = None
        mesh_obj = None
        skinned_mesh_obj = None  # Parent object that contains armature and mesh
        icospheres_to_delete = []
        
        for obj in new_objects:
            if obj.type == 'ARMATURE':
                armature_obj = obj
                # Check if this armature has a parent (the skinned_mesh object)
                if obj.parent:
                    skinned_mesh_obj = obj.parent
            elif obj.type == 'MESH':
                # Check if it's an icosphere (Blender sometimes creates these as bone placeholders)
                # Icospheres typically have specific vertex/face counts or names
                mesh_data = obj.data
                is_icosphere = False
                
                if mesh_data and mesh_data.name:
                    # Check if it's likely an icosphere (has "Icosphere" in name or is a primitive)
                    if "Icosphere" in mesh_data.name or "icosphere" in obj.name.lower():
                        is_icosphere = True
                    # Also check mesh characteristics (icospheres have specific topology)
                    # Basic icosphere has 12 vertices, 20 faces
                    elif len(mesh_data.vertices) == 12 and len(mesh_data.polygons) == 20:
                        is_icosphere = True
                
                if is_icosphere:
                    icospheres_to_delete.append(obj)
                else:
                    mesh_obj = obj
                    # Check if this mesh has a parent (the skinned_mesh object)
                    if obj.parent and not skinned_mesh_obj:
                        skinned_mesh_obj = obj.parent
        
        # Delete icosphere objects (Blender 4.0+ bug where bones get icosphere placeholders)
        for icosphere in icospheres_to_delete:
            print(f"[lol_league_v4] Removing icosphere placeholder: {icosphere.name}")
            # Unlink from collections
            for collection in icosphere.users_collection:
                collection.objects.unlink(icosphere)
            # Delete the object and its mesh data
            mesh_data = icosphere.data
            bpy.data.objects.remove(icosphere, do_unlink=True)
            if mesh_data and mesh_data.users == 0:
                bpy.data.meshes.remove(mesh_data, do_unlink=True)
        
        if not armature_obj:
            print("[lol_league_v4] WARNING: No armature found in glTF")
        if not mesh_obj:
            print("[lol_league_v4] WARNING: No mesh found in glTF")
        
        # Set bone display to OCTAHEDRAL
        if armature_obj and armature_obj.type == 'ARMATURE':
            armature_obj.data.display_type = 'OCTAHEDRAL'
            armature_obj.data.show_axes = False
            armature_obj.data.show_names = False
            print("[lol_league_v4] Set bone display to OCTAHEDRAL")
        
        # Rename skinned_mesh object to match imported SKN filename
        if skinned_mesh_obj and model_name:
            skinned_mesh_obj.name = model_name
            print(f"[lol_league_v4] Renamed skinned_mesh to '{model_name}'")
        
        print(f"[lol_league_v4] Imported glTF (scale factor {scale_factor} applied during conversion)")
        
        return armature_obj, mesh_obj
        
    except Exception as e:
        print(f"[lol_league_v4] ERROR: Failed to import glTF: {e}")
        import traceback
        traceback.print_exc()
        return None, None

def sanitize_maya_name(name: str) -> str:
    """
    Sanitize a name to be Maya-compatible.
    Maya object names cannot contain spaces or certain special characters.
    
    Args:
        name: Original name
        
    Returns:
        Sanitized name safe for Maya
    """
    # Replace spaces with underscores
    sanitized = name.replace(' ', '_')
    # Remove or replace other invalid characters
    # Maya doesn't allow: | : ? * " < >
    invalid_chars = ['|', ':', '?', '*', '"', '<', '>', '/', '\\']
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    # Ensure it's not empty
    if not sanitized:
        sanitized = "default"
    return sanitized

def check_maya_name_validity(name: str) -> tuple[bool, list[str]]:
    """
    Check if a name is valid for Maya.
    Maya object names cannot contain spaces or certain special characters.
    Also checks for non-ASCII characters (like ç, é, etc.)
    
    Args:
        name: Name to check
        
    Returns:
        (is_valid: bool, invalid_chars: list of invalid characters found)
    """
    invalid_chars = []
    
    # Check for spaces
    if ' ' in name:
        invalid_chars.append('space')
    
    # Check for invalid special characters
    maya_invalid = ['|', ':', '?', '*', '"', '<', '>', '/', '\\']
    for char in maya_invalid:
        if char in name:
            invalid_chars.append(char)
    
    # Check for non-ASCII characters (like ç, é, ñ, etc.)
    try:
        name.encode('ascii')
    except UnicodeEncodeError:
        # Find non-ASCII characters
        for char in name:
            try:
                char.encode('ascii')
            except UnicodeEncodeError:
                if char not in invalid_chars:
                    invalid_chars.append(char)
    
    return len(invalid_chars) == 0, invalid_chars

def export_blender_to_gltf(armature_obj: bpy.types.Object, mesh_obj: bpy.types.Object, 
                          gltf_path: str, export_animations: bool = False) -> bool:
    """
    Export Blender scene to glTF using native exporter.
    glTF exporter preserves bind matrices better than FBX.
    
    Args:
        armature_obj: Armature object
        mesh_obj: Mesh object
        gltf_path: Output glTF path
        export_animations: Whether to export animations (default: False)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Ensure armature is in rest pose (only if not exporting animations)
        if not export_animations:
            current_mode = bpy.context.mode
            if current_mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            
            if armature_obj and armature_obj.type == 'ARMATURE':
                bpy.context.view_layer.objects.active = armature_obj
                bpy.ops.object.mode_set(mode='POSE')
                
                # Clear all pose bone transforms
                for pose_bone in armature_obj.pose.bones:
                    pose_bone.location = (0, 0, 0)
                    pose_bone.rotation_euler = (0, 0, 0)
                    pose_bone.rotation_quaternion = (1, 0, 0, 0)
                    pose_bone.scale = (1, 1, 1)
                
                bpy.ops.object.mode_set(mode='OBJECT')
        
        # Apply armature object's transform (location, rotation, scale) to bones before export
        # This ensures the bones are in the correct position/orientation for export
        # (glTF exporter doesn't apply armature object transforms to bones)
        armature_transform_applied = False
        if armature_obj and armature_obj.type == 'ARMATURE':
            # Check if armature has non-identity transform
            location_applied = False
            rotation_applied = False
            scale_applied = False
            
            # Check location
            loc = armature_obj.location
            if abs(loc.x) > 0.0001 or abs(loc.y) > 0.0001 or abs(loc.z) > 0.0001:
                location_applied = True
            
            # Check rotation (using Euler angles)
            rot_euler = armature_obj.rotation_euler
            if abs(rot_euler.x) > 0.0001 or abs(rot_euler.y) > 0.0001 or abs(rot_euler.z) > 0.0001:
                rotation_applied = True
            
            # Check scale
            scale = armature_obj.scale
            if abs(scale.x - 1.0) > 0.0001 or abs(scale.y - 1.0) > 0.0001 or abs(scale.z - 1.0) > 0.0001:
                scale_applied = True
            
            if location_applied or rotation_applied or scale_applied:
                # Apply all transforms to bake them into bone positions/orientations
                bpy.context.view_layer.objects.active = armature_obj
                bpy.ops.object.select_all(action='DESELECT')
                armature_obj.select_set(True)
                
                # Store original values for logging
                original_loc = loc.copy()
                original_rot = rot_euler.copy()
                original_scale = scale.copy()
                
                # Apply all transforms at once
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                
                print(f"[lol_league_v4] Applied armature transform:")
                if location_applied:
                    print(f"  Location: {original_loc} -> (0, 0, 0)")
                if rotation_applied:
                    print(f"  Rotation: {original_rot} -> (0, 0, 0)")
                if scale_applied:
                    print(f"  Scale: {original_scale} -> (1, 1, 1)")
                
                armature_transform_applied = True
        
        # Check material names for Maya compatibility
        invalid_materials = []
        if mesh_obj and mesh_obj.data and mesh_obj.data.materials:
            for mat in mesh_obj.data.materials:
                if mat and mat.name:
                    is_valid, invalid_chars = check_maya_name_validity(mat.name)
                    if not is_valid:
                        invalid_materials.append((mat.name, invalid_chars))
        
        # Check bone names for Maya compatibility
        invalid_bones = []
        if armature_obj and armature_obj.type == 'ARMATURE':
            for bone in armature_obj.data.bones:
                if bone.name:
                    is_valid, invalid_chars = check_maya_name_validity(bone.name)
                    if not is_valid:
                        invalid_bones.append((bone.name, invalid_chars))
        
        # Report errors if any invalid names found
        if invalid_materials or invalid_bones:
            error_msg = "Cannot export: Found names with invalid characters for Maya:\n\n"
            if invalid_materials:
                error_msg += "Materials:\n"
                for mat_name, invalid_chars in invalid_materials:
                    chars_str = ', '.join([f"'{c}'" if c != 'space' else "' ' (space)" for c in invalid_chars])
                    error_msg += f"  - '{mat_name}' (invalid characters: {chars_str})\n"
            if invalid_bones:
                error_msg += "\nBones:\n"
                for bone_name, invalid_chars in invalid_bones:
                    chars_str = ', '.join([f"'{c}'" if c != 'space' else "' ' (space)" for c in invalid_chars])
                    error_msg += f"  - '{bone_name}' (invalid characters: {chars_str})\n"
            error_msg += "\nPlease rename these to use only ASCII letters, numbers, and underscores."
            
            # Print full error to Blender console
            print(f"[lol_league_v4] ERROR: {error_msg}")
            # Also print each line separately for better visibility in console
            for line in error_msg.split('\n'):
                if line.strip():
                    print(f"[lol_league_v4] {line}")
            
            raise ValueError(error_msg)
        
        # Sanitize material names for Maya compatibility (spaces -> underscores, etc.)
        # Store original names and temporarily rename materials
        material_renames = {}
        if mesh_obj and mesh_obj.data and mesh_obj.data.materials:
            for mat in mesh_obj.data.materials:
                if mat and mat.name:
                    sanitized_name = sanitize_maya_name(mat.name)
                    if sanitized_name != mat.name:
                        # Store original name
                        material_renames[mat] = mat.name
                        # Temporarily rename for export
                        mat.name = sanitized_name
                        print(f"[lol_league_v4] Sanitized material name: '{material_renames[mat]}' -> '{sanitized_name}'")
        
        # Sanitize bone names for Maya compatibility
        # Store original names and temporarily rename bones
        bone_renames = {}
        if armature_obj and armature_obj.type == 'ARMATURE':
            # Switch to Edit Mode to rename bones
            current_mode = bpy.context.mode
            if current_mode != 'EDIT_ARMATURE':
                bpy.context.view_layer.objects.active = armature_obj
                bpy.ops.object.mode_set(mode='EDIT')
            
            for bone in armature_obj.data.edit_bones:
                if bone.name:
                    original_name = bone.name
                    sanitized_name = sanitize_maya_name(original_name)
                    if sanitized_name != original_name:
                        # Store original name before renaming
                        bone_renames[original_name] = sanitized_name
                        # Temporarily rename for export
                        bone.name = sanitized_name
                        print(f"[lol_league_v4] Sanitized bone name: '{original_name}' -> '{sanitized_name}'")
            
            # Switch back to Object Mode
            bpy.ops.object.mode_set(mode='OBJECT')
        
        # Select objects
        bpy.ops.object.select_all(action='DESELECT')
        armature_obj.select_set(True)
        if mesh_obj:
            mesh_obj.select_set(True)
        
        try:
            # Export glTF
            # Note: Operator parameters use 'export_' prefix, not 'gltf_'
            export_settings = {
                'filepath': gltf_path,
                'use_selection': True,
                'export_format': 'GLB',  # Binary format
                'export_animations': export_animations,
                'export_cameras': False,
                'export_lights': False,
                'export_extras': True,
                'export_yup': True,  # glTF uses Y-up
                'export_apply': True,  # Apply modifiers
                'export_skins': True,
                'export_morph': False,
            }
            
            # Add animation-specific settings if exporting animations
            if export_animations:
                export_settings['export_frame_range'] = True
                export_settings['export_force_sampling'] = True
                export_settings['export_animation_mode'] = 'ACTIONS'
                export_settings['export_nla_strips'] = False
                export_settings['export_def_bones'] = False
                # Note: export_optimize_animation_size might not exist in all Blender versions
                # Only add it if it's a valid parameter
            
            bpy.ops.export_scene.gltf(**export_settings)
            
            print(f"[lol_league_v4] Exported glTF: {gltf_path} (animations: {export_animations})")
            return True
        finally:
            # Restore original material names
            for mat, original_name in material_renames.items():
                if mat and mat.name:
                    mat.name = original_name
                    print(f"[lol_league_v4] Restored material name: '{mat.name}' -> '{original_name}'")
            
            # Restore original bone names
            if bone_renames and armature_obj and armature_obj.type == 'ARMATURE':
                current_mode = bpy.context.mode
                if current_mode != 'EDIT_ARMATURE':
                    bpy.context.view_layer.objects.active = armature_obj
                    bpy.ops.object.mode_set(mode='EDIT')
                
                # Restore bone names (create reverse mapping: sanitized -> original)
                sanitized_to_original = {sanitized: original for original, sanitized in bone_renames.items()}
                for bone in armature_obj.data.edit_bones:
                    if bone.name in sanitized_to_original:
                        original_name = sanitized_to_original[bone.name]
                        sanitized_name = bone.name  # Store before changing
                        bone.name = original_name
                        print(f"[lol_league_v4] Restored bone name: '{sanitized_name}' -> '{original_name}'")
                
                bpy.ops.object.mode_set(mode='OBJECT')
        
    except Exception as e:
        print(f"[lol_league_v4] ERROR: Failed to export glTF: {e}")
        import traceback
        traceback.print_exc()
        return False

def convert_gltf_to_skl_skn(gltf_path: str, skl_path: str, skn_path: str, scale_factor: float = 0.01) -> tuple[bool, str]:
    """
    Convert glTF to SKL+SKN using pygltflib and pyritofile.
    This is the reverse of convert_skl_skn_to_gltf.
    
    Args:
        gltf_path: Path to glTF file (.glb for binary)
        skl_path: Output SKL path
        skn_path: Output SKN path
        scale_factor: Scale factor to apply (inverse of import scale)
        
    Returns:
        (success: bool, error_message: str)
    """
    if not _ensure_pygltflib():
        return False, "pygltflib not available"
    
    global pygltflib
    if pygltflib is None:
        import pygltflib
    
    try:
        from ..dependencies import is_pyritofile_available
        if not is_pyritofile_available():
            return False, "pyritofile not available"
        
        from pyritofile import SKL, SKN, structs
        from pyritofile.skl import SKLJoint
        from pyritofile.skn import SKNVertex, SKNSubmesh
        from pyritofile.ermmm import Elf
        
        # Load glTF
        gltf = pygltflib.GLTF2().load(gltf_path)
        print(f"[lol_league_v4] Loaded glTF: {len(gltf.nodes)} nodes, {len(gltf.meshes)} meshes")
        
        # Get binary data
        binary_data = gltf.binary_blob() if hasattr(gltf, 'binary_blob') else None
        if binary_data is None and len(gltf.buffers) > 0 and gltf.buffers[0].uri:
            # Load external buffer
            buffer_path = os.path.join(os.path.dirname(gltf_path), gltf.buffers[0].uri)
            if os.path.exists(buffer_path):
                with open(buffer_path, 'rb') as f:
                    binary_data = f.read()
        
        if binary_data is None:
            return False, "Could not load glTF binary data"
        
        # Find skin
        if not gltf.skins or len(gltf.skins) == 0:
            return False, "No skin found in glTF"
        
        skin = gltf.skins[0]
        
        # Find mesh
        if not gltf.meshes or len(gltf.meshes) == 0:
            return False, "No mesh found in glTF"
        
        mesh = gltf.meshes[0]
        if not mesh.primitives or len(mesh.primitives) == 0:
            return False, "No primitives in mesh"
        
        primitive = mesh.primitives[0]
        
        # Read accessors
        def read_accessor(accessor_idx):
            if accessor_idx is None:
                return None
            acc = gltf.accessors[accessor_idx]
            view = gltf.bufferViews[acc.bufferView]
            offset = view.byteOffset or 0
            length = view.byteLength
            data = binary_data[offset:offset+length]
            
            dtype_map = {
                pygltflib.BYTE: np.int8,
                pygltflib.UNSIGNED_BYTE: np.uint8,
                pygltflib.SHORT: np.int16,
                pygltflib.UNSIGNED_SHORT: np.uint16,
                pygltflib.UNSIGNED_INT: np.uint32,
                pygltflib.FLOAT: np.float32,
            }
            
            dtype = dtype_map.get(acc.componentType, np.float32)
            count = acc.count
            
            if acc.type == pygltflib.SCALAR:
                return np.frombuffer(data, dtype=dtype).reshape(count)
            elif acc.type == pygltflib.VEC2:
                return np.frombuffer(data, dtype=dtype).reshape(count, 2)
            elif acc.type == pygltflib.VEC3:
                return np.frombuffer(data, dtype=dtype).reshape(count, 3)
            elif acc.type == pygltflib.VEC4:
                return np.frombuffer(data, dtype=dtype).reshape(count, 4)
            elif acc.type == pygltflib.MAT4:
                return np.frombuffer(data, dtype=dtype).reshape(count, 4, 4)
            return None
        
        # Read vertex data (Attributes is an object with properties, not a dict)
        positions = read_accessor(getattr(primitive.attributes, 'POSITION', None))
        normals = read_accessor(getattr(primitive.attributes, 'NORMAL', None))
        uvs = read_accessor(getattr(primitive.attributes, 'TEXCOORD_0', None))
        joints = read_accessor(getattr(primitive.attributes, 'JOINTS_0', None))
        weights = read_accessor(getattr(primitive.attributes, 'WEIGHTS_0', None))
        indices = read_accessor(primitive.indices)
        
        if positions is None:
            return False, "No positions in mesh"
        
        # Apply inverse scale factor (convert back from glTF scale)
        inv_scale = 1.0 / scale_factor if scale_factor != 0 else 1.0
        positions = positions * inv_scale
        
        # Build SKL from nodes
        skl = SKL()
        skl.joints = []
        skl.influences = []
        
        # Map node indices to joint indices (skin.joints contains node indices)
        node_to_joint = {}
        for joint_idx, node_idx in enumerate(skin.joints):
            node_to_joint[node_idx] = joint_idx
        
        # Build SKL joints
        for joint_idx, node_idx in enumerate(skin.joints):
            node = gltf.nodes[node_idx]
            
            # Find parent joint index
            parent_joint_idx = -1
            for parent_node_idx in range(len(gltf.nodes)):
                if gltf.nodes[parent_node_idx].children and node_idx in gltf.nodes[parent_node_idx].children:
                    if parent_node_idx in node_to_joint:
                        parent_joint_idx = node_to_joint[parent_node_idx]
                        break
            
            # Get transform (apply inverse scale)
            trans = node.translation or [0, 0, 0]
            rot = node.rotation or [0, 0, 0, 1]
            scale_vals = node.scale or [1, 1, 1]
            
            # Apply inverse scale to translation
            trans = [t * inv_scale for t in trans]
            
            joint = SKLJoint()
            joint.id = joint_idx
            joint.name = node.name or f"joint_{joint_idx}"
            joint.bin_hash = None  # Will be set by SKL.write() if needed
            joint.parent = parent_joint_idx
            joint.hash = Elf(joint.name)  # Hash from joint name
            joint.radius = 0.0  # Default radius
            joint.flags = 0  # Default flags
            joint.local_translate = structs.Vector(trans[0], trans[1], trans[2])
            joint.local_rotate = structs.Quaternion(rot[0], rot[1], rot[2], rot[3])
            joint.local_scale = structs.Vector(scale_vals[0], scale_vals[1], scale_vals[2])
            
            # Get inverse bind matrix from skin
            ibm_acc = gltf.accessors[skin.inverseBindMatrices]
            ibm_view = gltf.bufferViews[ibm_acc.bufferView]
            ibm_offset = ibm_view.byteOffset or 0
            ibm_data = binary_data[ibm_offset:ibm_offset+ibm_view.byteLength]
            ibm_array = np.frombuffer(ibm_data, dtype=np.float32).reshape(len(skin.joints), 4, 4)
            
            # Extract inverse bind transform (apply inverse scale)
            ibm = ibm_array[joint_idx]
            ibm_mat = Matrix(ibm.tolist())
            
            # Extract translation, rotation, scale from matrix
            ibm_loc, ibm_rot, ibm_scale = ibm_mat.decompose()
            ibm_loc = ibm_loc * inv_scale  # Apply inverse scale
            
            joint.ibind_translate = structs.Vector(ibm_loc.x, ibm_loc.y, ibm_loc.z)
            joint.ibind_rotate = structs.Quaternion(ibm_rot.w, ibm_rot.x, ibm_rot.y, ibm_rot.z)
            joint.ibind_scale = structs.Vector(ibm_scale.x, ibm_scale.y, ibm_scale.z)
            
            skl.joints.append(joint)
        
        # Build influence list (all unique joint indices used by vertices)
        if joints is not None:
            unique_joints = set()
            for j in joints.flatten():
                unique_joints.add(int(j))
            skl.influences = sorted(list(unique_joints))
        else:
            skl.influences = list(range(len(skl.joints)))
        
        # Build joint to influence map
        joint_to_influence = {joint_id: inf_id for inf_id, joint_id in enumerate(skl.influences)}
        
        # Build SKN
        skn = SKN()
        skn.vertices = []
        skn.indices = []
        skn.submeshes = []
        
        # Convert vertices
        vertex_count = len(positions)
        for i in range(vertex_count):
            vertex = SKNVertex()
            vertex.position = structs.Vector(positions[i][0], positions[i][1], positions[i][2])
            
            if normals is not None and i < len(normals):
                vertex.normal = structs.Vector(normals[i][0], normals[i][1], normals[i][2])
            else:
                vertex.normal = structs.Vector(0, 0, 1)
            
            if uvs is not None and i < len(uvs):
                vertex.uv = structs.Vector(uvs[i][0], 1.0 - uvs[i][1], 0.0)  # Flip V coordinate back, z=0 for UV
            else:
                vertex.uv = structs.Vector(0, 0, 0)
            
            # Set influences and weights (must be tuples, not lists)
            if joints is not None and weights is not None and i < len(joints):
                joint_ids = joints[i]
                weight_vals = weights[i]
                
                # Sort by weight (descending) and keep top 4
                influences_weights = [(joint_to_influence.get(int(j), 0), float(w)) for j, w in zip(joint_ids, weight_vals)]
                influences_weights.sort(key=lambda x: x[1], reverse=True)
                influences_weights = influences_weights[:4]
                
                # Pad to 4
                while len(influences_weights) < 4:
                    influences_weights.append((0, 0.0))
                
                # Assign as tuples (influences and weights are tuples, not lists)
                vertex.influences = tuple(influences_weights[j][0] for j in range(4))
                vertex.weights = tuple(influences_weights[j][1] for j in range(4))
            else:
                # Default to first joint with full weight
                vertex.influences = (0, 0, 0, 0)
                vertex.weights = (1.0, 0.0, 0.0, 0.0)
            
            skn.vertices.append(vertex)
        
        # Convert indices
        if indices is not None:
            skn.indices = [int(idx) for idx in indices]
        else:
            # Generate indices if not present
            skn.indices = list(range(vertex_count))
        
        # Create single submesh (for now - could split by material later)
        submesh = SKNSubmesh()
        submesh.name = "default"
        submesh.vertex_start = 0
        submesh.vertex_count = vertex_count
        submesh.index_start = 0
        submesh.index_count = len(skn.indices)
        skn.submeshes.append(submesh)
        
        # Ensure output directories exist
        os.makedirs(os.path.dirname(skl_path) if os.path.dirname(skl_path) else '.', exist_ok=True)
        os.makedirs(os.path.dirname(skn_path) if os.path.dirname(skn_path) else '.', exist_ok=True)
        
        # Write SKL and SKN
        skl.write(skl_path)
        skn.write(skn_path)
        
        print(f"[lol_league_v4] Exported SKL: {len(skl.joints)} joints")
        print(f"[lol_league_v4] Exported SKN: {len(skn.vertices)} vertices, {len(skn.submeshes)} submeshes")
        
        return True, ""
        
    except Exception as e:
        error_msg = f"Failed to convert glTF to SKN/SKL: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg

def find_lol2gltf_executable() -> Optional[str]:
    """
    Find the lol2gltf executable.
    Checks common locations and addon directory.
    
    Returns:
        Path to lol2gltf executable, or None if not found
    """
    # Check if lol2gltf is in PATH
    lol2gltf_path = shutil.which("lol2gltf")
    if lol2gltf_path:
        return lol2gltf_path
    
    # Check addon directory for bundled lol2gltf
    addon_dir = os.path.dirname(os.path.dirname(__file__))  # io -> addons -> lol_league_v4
    possible_paths = [
        os.path.join(addon_dir, "lol2gltf-main", "lol2gltf.exe"),  # In lol2gltf-main subdirectory (Windows)
        os.path.join(addon_dir, "lol2gltf-main", "lol2gltf"),  # In lol2gltf-main subdirectory (Linux/Mac)
        os.path.join(addon_dir, "lol2gltf.exe"),  # Directly in addon directory (Windows)
        os.path.join(addon_dir, "lol2gltf"),  # Directly in addon directory (Linux/Mac)
        os.path.join(addon_dir, "lol2gltf", "lol2gltf.exe"),  # In subdirectory (Windows)
        os.path.join(addon_dir, "lol2gltf", "lol2gltf"),  # In subdirectory (Linux/Mac)
        os.path.join(addon_dir, "vendor", "lol2gltf", "lol2gltf.exe"),
        os.path.join(addon_dir, "vendor", "lol2gltf", "lol2gltf"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            # On Windows, check if it's executable (or just exists)
            # On Unix, check if it's executable
            if os.name == 'nt' or os.access(path, os.X_OK):
                return path
    
    return None

def convert_skl_skn_anm_to_gltf_with_lol2gltf(skl_path: str, skn_path: str, gltf_path: str, anm_folder: Optional[str] = None) -> tuple[bool, str]:
    """
    Convert SKN/SKL/ANM to glTF using lol2gltf command-line tool.
    This supports adding ANM animations.
    
    Args:
        skl_path: Path to SKL file
        skn_path: Path to SKN file
        gltf_path: Output glTF path (.glb for binary)
        anm_folder: Optional path to folder containing ANM files
        
    Returns:
        (success: bool, error_message: str)
    """
    # Find lol2gltf executable
    lol2gltf_exe = find_lol2gltf_executable()
    if not lol2gltf_exe:
        return False, "lol2gltf executable not found. Please install lol2gltf and ensure it's in PATH or bundled with the addon."
    
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(gltf_path) if os.path.dirname(gltf_path) else '.', exist_ok=True)
        
        # Run lol2gltf: skn2gltf -m <skn_path> -s <skl_path> -g <gltf_path> [-a <anm_folder>]
        cmd = [
            lol2gltf_exe,
            "skn2gltf",
            "-m", skn_path,
            "-s", skl_path,
            "-g", gltf_path
        ]
        
        # Add ANM folder if provided
        if anm_folder and os.path.exists(anm_folder):
            cmd.extend(["-a", anm_folder])
        
        print(f"[lol_league_v4] Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid UTF-8 sequences instead of failing
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            error_msg = f"lol2gltf failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            if result.stdout:
                error_msg += f"\nOutput: {result.stdout}"
            return False, error_msg
        
        # Verify file was created
        if not os.path.exists(gltf_path):
            return False, f"glTF file was not created: {gltf_path}"
        
        print(f"[lol_league_v4] Successfully converted SKN/SKL/ANM to glTF using lol2gltf")
        print(f"[lol_league_v4] glTF: {gltf_path}")
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "lol2gltf conversion timed out after 60 seconds"
    except FileNotFoundError:
        return False, f"lol2gltf executable not found at: {lol2gltf_exe}"
    except Exception as e:
        error_msg = f"Failed to run lol2gltf: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg

def convert_skl_skn_to_gltf_with_lol2gltf(skl_path: str, skn_path: str, gltf_path: str) -> tuple[bool, str]:
    """
    Convert SKN/SKL to glTF using lol2gltf command-line tool.
    This is more reliable than using pygltflib directly.
    
    Args:
        skl_path: Path to SKL file
        skn_path: Path to SKN file
        gltf_path: Output glTF path (.glb for binary)
        
    Returns:
        (success: bool, error_message: str)
    """
    # Find lol2gltf executable
    lol2gltf_exe = find_lol2gltf_executable()
    if not lol2gltf_exe:
        return False, "lol2gltf executable not found. Please install lol2gltf and ensure it's in PATH or bundled with the addon."
    
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(gltf_path) if os.path.dirname(gltf_path) else '.', exist_ok=True)
        
        # Run lol2gltf: skn2gltf -m <skn_path> -s <skl_path> -g <gltf_path>
        cmd = [
            lol2gltf_exe,
            "skn2gltf",
            "-m", skn_path,
            "-s", skl_path,
            "-g", gltf_path
        ]
        
        print(f"[lol_league_v4] Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid UTF-8 sequences instead of failing
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            error_msg = f"lol2gltf failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            if result.stdout:
                error_msg += f"\nOutput: {result.stdout}"
            return False, error_msg
        
        # Verify file was created
        if not os.path.exists(gltf_path):
            return False, f"glTF file was not created: {gltf_path}"
        
        print(f"[lol_league_v4] Successfully converted SKN/SKL to glTF using lol2gltf")
        print(f"[lol_league_v4] glTF: {gltf_path}")
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "lol2gltf conversion timed out after 60 seconds"
    except FileNotFoundError:
        return False, f"lol2gltf executable not found at: {lol2gltf_exe}"
    except Exception as e:
        error_msg = f"Failed to run lol2gltf: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg

def convert_gltf_to_skl_skn_with_lol2gltf(gltf_path: str, skn_path: str, skl_path: str) -> tuple[bool, str]:
    """
    Convert glTF to SKN/SKL using lol2gltf command-line tool.
    This is more reliable than using pyritofile directly.
    
    Args:
        gltf_path: Path to glTF file (.glb for binary)
        skn_path: Output SKN path
        skl_path: Output SKL path
        
    Returns:
        (success: bool, error_message: str)
    """
    # Find lol2gltf executable
    lol2gltf_exe = find_lol2gltf_executable()
    if not lol2gltf_exe:
        return False, "lol2gltf executable not found. Please install lol2gltf and ensure it's in PATH or bundled with the addon."
    
    try:
        # Convert paths to absolute paths
        gltf_path = os.path.abspath(gltf_path)
        skn_path = os.path.abspath(skn_path)
        skl_path = os.path.abspath(skl_path)
        
        # Ensure output directories exist
        skn_dir = os.path.dirname(skn_path) if os.path.dirname(skn_path) else '.'
        skl_dir = os.path.dirname(skl_path) if os.path.dirname(skl_path) else '.'
        os.makedirs(skn_dir, exist_ok=True)
        if skl_dir != skn_dir:
            os.makedirs(skl_dir, exist_ok=True)
        
        # Run lol2gltf: gltf2skn -g <gltf_path> -m <skn_path> -s <skl_path>
        cmd = [
            lol2gltf_exe,
            "gltf2skn",
            "-g", gltf_path,
            "-m", skn_path,
            "-s", skl_path
        ]
        
        print(f"[lol_league_v4] Output paths:")
        print(f"[lol_league_v4]   SKN: {skn_path}")
        print(f"[lol_league_v4]   SKL: {skl_path}")
        
        print(f"[lol_league_v4] Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid UTF-8 sequences instead of failing
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            error_msg = f"lol2gltf failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            if result.stdout:
                error_msg += f"\nOutput: {result.stdout}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            return False, error_msg
        
        # Print output for debugging
        if result.stdout:
            print(f"[lol_league_v4] lol2gltf output: {result.stdout}")
        if result.stderr:
            print(f"[lol_league_v4] lol2gltf stderr: {result.stderr}")
        
        # Verify files were created
        if not os.path.exists(skn_path):
            error_msg = f"SKN file was not created: {skn_path}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            print(f"[lol_league_v4] lol2gltf stdout: {result.stdout}")
            print(f"[lol_league_v4] lol2gltf stderr: {result.stderr}")
            return False, error_msg
        if not os.path.exists(skl_path):
            error_msg = f"SKL file was not created: {skl_path}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            print(f"[lol_league_v4] Directory contents: {os.listdir(os.path.dirname(skl_path) if os.path.dirname(skl_path) else '.')}")
            print(f"[lol_league_v4] lol2gltf stdout: {result.stdout}")
            print(f"[lol_league_v4] lol2gltf stderr: {result.stderr}")
            return False, error_msg
        
        print(f"[lol_league_v4] Successfully converted glTF to SKN/SKL using lol2gltf")
        print(f"[lol_league_v4] SKN: {skn_path}")
        print(f"[lol_league_v4] SKL: {skl_path}")
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "lol2gltf conversion timed out after 60 seconds"
    except FileNotFoundError:
        return False, f"lol2gltf executable not found at: {lol2gltf_exe}"
    except Exception as e:
        error_msg = f"Failed to run lol2gltf: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg


def convert_gltf_to_anm_with_lol2gltf(gltf_path: str, output_dir: str, skl_path: Optional[str] = None) -> tuple[bool, str]:
    """
    Extract animations from glTF to ANM files using lol2gltf command-line tool.
    
    Args:
        gltf_path: Path to glTF file (.glb for binary)
        output_dir: Output directory for ANM files
        skl_path: Optional path to SKL file for validation
        
    Returns:
        (success: bool, error_message: str)
    """
    # Find lol2gltf executable
    lol2gltf_exe = find_lol2gltf_executable()
    if not lol2gltf_exe:
        return False, "lol2gltf executable not found. Please install lol2gltf and ensure it's in PATH or bundled with the addon."
    
    try:
        # Convert paths to absolute paths
        gltf_path = os.path.abspath(gltf_path)
        output_dir = os.path.abspath(output_dir)
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Run lol2gltf: gltf2anm -g <gltf_path> -o <output_dir> [-s <skl_path>]
        cmd = [
            lol2gltf_exe,
            "gltf2anm",
            "-g", gltf_path,
            "-o", output_dir
        ]
        
        # Add SKL path if provided
        if skl_path and os.path.exists(skl_path):
            cmd.extend(["-s", os.path.abspath(skl_path)])
        
        print(f"[lol_league_v4] Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace invalid UTF-8 sequences instead of failing
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            error_msg = f"lol2gltf failed with return code {result.returncode}"
            if result.stderr:
                error_msg += f": {result.stderr}"
            if result.stdout:
                error_msg += f"\nOutput: {result.stdout}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            return False, error_msg
        
        # Print output for debugging
        if result.stdout:
            print(f"[lol_league_v4] lol2gltf output: {result.stdout}")
        if result.stderr:
            print(f"[lol_league_v4] lol2gltf stderr: {result.stderr}")
        
        # Check if any ANM files were created
        anm_files = [f for f in os.listdir(output_dir) if f.endswith('.anm')]
        if not anm_files:
            error_msg = f"No ANM files were created in: {output_dir}"
            print(f"[lol_league_v4] ERROR: {error_msg}")
            return False, error_msg
        
        print(f"[lol_league_v4] Successfully extracted {len(anm_files)} animation(s) from glTF")
        for anm_file in anm_files:
            print(f"[lol_league_v4]   - {anm_file}")
        
        return True, ""
        
    except subprocess.TimeoutExpired:
        return False, "lol2gltf conversion timed out after 60 seconds"
    except FileNotFoundError:
        return False, f"lol2gltf executable not found at: {lol2gltf_exe}"
    except Exception as e:
        error_msg = f"Failed to run lol2gltf: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return False, error_msg
