"""
Direct ANM Import - Reverses the exporter logic
Reads ANM files directly and creates Blender fcurves without FBX intermediate
"""

import bpy
from mathutils import Vector, Quaternion, Matrix
from ..dependencies import ensure_dependencies


def apply_anm_to_armature_direct(anm_path: str, armature_obj: bpy.types.Object, 
                                  action_name: str, scale_factor: float = 0.01,
                                  context: bpy.types.Context = None) -> tuple[bool, str]:
    """
    Apply ANM animation directly to Blender armature by reversing the exporter logic.
    
    This bypasses the FBX intermediate and directly creates fcurves from ANM data,
    applying the inverse coordinate transformations that the exporter uses.
    
    Args:
        anm_path: Path to ANM file
        armature_obj: Target Blender armature
        action_name: Name for the action
        scale_factor: Scale factor for animation (default: 0.01)
        context: Blender context
        
    Returns:
        (success: bool, error_message: str)
    """
    try:
        # Check dependencies
        deps_ok = ensure_dependencies()
        if not deps_ok:
            return False, "Failed to load dependencies (pyritofile, xxhash, pyzstd). Check console for details."
        
        # Import pyritofile
        import sys
        import os
        addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        vendor_path = os.path.join(addon_dir, "vendor", "pyritofile-package")
        if vendor_path not in sys.path:
            sys.path.insert(0, vendor_path)
        
        from pyritofile import ANM
        from pyritofile.ermmm import Elf
        
        # Read ANM file
        print(f"[lol_league_v4] Reading ANM file: {anm_path}")
        anm = ANM()
        anm.read(anm_path)
        print(f"[lol_league_v4] ANM: {len(anm.tracks)} tracks, {anm.duration} frames @ {anm.fps} FPS")
        
        # Build bone name lookup from armature
        bone_name_from_hash = {}
        for bone in armature_obj.data.bones:
            bone_hash = Elf(bone.name)
            bone_name_from_hash[bone_hash] = bone.name
        
        print(f"[lol_league_v4] Mapped {len(bone_name_from_hash)} bones from armature")
        
        # Create or get action
        if action_name in bpy.data.actions:
            action = bpy.data.actions[action_name]
            # Clear existing fcurves
            action.fcurves.clear()
        else:
            action = bpy.data.actions.new(name=action_name)
        
        action.frame_range = (1, anm.duration)
        
        # Set FPS
        if context:
            context.scene.render.fps = int(anm.fps)
            context.scene.render.fps_base = 1.0
        
        # Process each track (bone animation)
        for track in anm.tracks:
            # Find bone name from hash
            if track.joint_hash not in bone_name_from_hash:
                continue  # Bone not in armature, skip
            
            bone_name = bone_name_from_hash[track.joint_hash]
            bone = armature_obj.pose.bones.get(bone_name)
            if not bone:
                continue  # Bone not found, skip
            
            # Check if root bone (no parent)
            is_root_bone = (bone.parent is None)
            
            print(f"[lol_league_v4] Processing bone: {bone_name} (root={is_root_bone}, poses={len(track.poses)})")
            
            # Create fcurve data paths
            location_path = f'pose.bones["{bone_name}"].location'
            rotation_path = f'pose.bones["{bone_name}"].rotation_quaternion'
            scale_path = f'pose.bones["{bone_name}"].scale'
            
            # Create fcurves
            loc_x_fcurve = action.fcurves.new(data_path=location_path, index=0)
            loc_y_fcurve = action.fcurves.new(data_path=location_path, index=1)
            loc_z_fcurve = action.fcurves.new(data_path=location_path, index=2)
            
            rot_x_fcurve = action.fcurves.new(data_path=rotation_path, index=0)  # W
            rot_y_fcurve = action.fcurves.new(data_path=rotation_path, index=1)  # X
            rot_z_fcurve = action.fcurves.new(data_path=rotation_path, index=2)  # Y
            rot_w_fcurve = action.fcurves.new(data_path=rotation_path, index=3)  # Z
            
            scale_x_fcurve = action.fcurves.new(data_path=scale_path, index=0)
            scale_y_fcurve = action.fcurves.new(data_path=scale_path, index=1)
            scale_z_fcurve = action.fcurves.new(data_path=scale_path, index=2)
            
            # Ensure bone uses quaternion rotation
            bone.rotation_mode = 'QUATERNION'
            
            # Process all frames for this bone
            # ANM poses are keyed by time (frame), we need to evaluate for all frames
            # Sort poses by time
            sorted_times = sorted(track.poses.keys())
            
            # Process each frame
            for frame in range(anm.duration):
                # Find pose for this frame (interpolate if needed)
                pose = None
                
                # Try exact match first
                if frame in track.poses:
                    pose = track.poses[frame]
                else:
                    # Find nearest poses for interpolation
                    left_time = None
                    right_time = None
                    for time in sorted_times:
                        if time <= frame:
                            left_time = time
                        if time >= frame and right_time is None:
                            right_time = time
                            break
                    
                    # Use left pose if available, otherwise right, otherwise default
                    if left_time is not None:
                        pose = track.poses[left_time]
                    elif right_time is not None:
                        pose = track.poses[right_time]
                    else:
                        # No pose data, use identity/default
                        from pyritofile.anm import ANMPose
                        pose = ANMPose()
                        # For frames with no data, we'll use rest pose (zero translation, identity rotation)
                
                # Get transform values (default to identity/zero if not present)
                # Convert to mathutils types to ensure compatibility
                if pose.translate:
                    translation = Vector((pose.translate.x, pose.translate.y, pose.translate.z))
                else:
                    translation = Vector((0, 0, 0))
                
                if pose.rotate:
                    rotation = Quaternion((pose.rotate.w, pose.rotate.x, pose.rotate.y, pose.rotate.z))
                else:
                    rotation = Quaternion((1, 0, 0, 0))
                
                if pose.scale:
                    scale = Vector((pose.scale.x, pose.scale.y, pose.scale.z))
                else:
                    scale = Vector((1, 1, 1))
                
                # Apply inverse coordinate transformation for root bones
                # Exporter does (lines 67-71):
                #   rotation = bone.matrix_basis.to_quaternion()  # (w, x, y, z)
                #   rotation.x *= -1
                #   rotation.y *= -1
                #   rotation = Quaternion((rotation.y, rotation.z, rotation.w, rotation.x))
                #   translation = Vector((translation.x, translation.z, -translation.y))
                #
                # Reverse:
                # ANM has: (y, z, w, x) where original was (w, x, y, z) with x,y negated
                # To reverse: extract (w, x, y, z) from (y, z, w, x), then negate x,y
                if is_root_bone:
                    # Reverse translation: (x, z, -y) -> (x, -z, y)
                    translation = Vector((
                        translation.x,
                        -translation.z,
                        translation.y
                    ))
                    
                    # Reverse quaternion reordering
                    # Exporter: 
                    #   1. rotation = (w, x, y, z) from matrix_basis
                    #   2. rotation.x *= -1, rotation.y *= -1 -> (w, -x, -y, z)
                    #   3. rotation = Quaternion((rotation.y, rotation.z, rotation.w, rotation.x))
                    #      Quaternion(w, x, y, z) constructor, so:
                    #      new.w = rotation.y = -y
                    #      new.x = rotation.z = z
                    #      new.y = rotation.w = w
                    #      new.z = rotation.x = -x
                    # So ANM stores: (w=-y, x=z, y=w, z=-x) where original was (w, x, y, z)
                    # To reverse: original.w = ANM.y, original.x = -ANM.z, original.y = -ANM.w, original.z = ANM.x
                    original_w = rotation.y
                    original_x = -rotation.z
                    original_y = -rotation.w
                    original_z = rotation.x
                    rotation = Quaternion((original_w, original_x, original_y, original_z))
                
                # Apply scale factor (use regular multiplication, not *=, to ensure mathutils Vector)
                translation = translation * scale_factor
                
                # Add keyframes (Blender frame numbers start at 1, ANM starts at 0)
                frame_num = frame + 1
                
                # Location
                loc_x_fcurve.keyframe_points.insert(frame_num, translation.x)
                loc_y_fcurve.keyframe_points.insert(frame_num, translation.y)
                loc_z_fcurve.keyframe_points.insert(frame_num, translation.z)
                
                # Rotation (quaternion: W, X, Y, Z)
                rot_x_fcurve.keyframe_points.insert(frame_num, rotation.w)  # W
                rot_y_fcurve.keyframe_points.insert(frame_num, rotation.x)  # X
                rot_z_fcurve.keyframe_points.insert(frame_num, rotation.y)  # Y
                rot_w_fcurve.keyframe_points.insert(frame_num, rotation.z)  # Z
                
                # Scale
                scale_x_fcurve.keyframe_points.insert(frame_num, scale.x)
                scale_y_fcurve.keyframe_points.insert(frame_num, scale.y)
                scale_z_fcurve.keyframe_points.insert(frame_num, scale.z)
            
            # Update fcurves
            for fcurve in [loc_x_fcurve, loc_y_fcurve, loc_z_fcurve,
                          rot_x_fcurve, rot_y_fcurve, rot_z_fcurve, rot_w_fcurve,
                          scale_x_fcurve, scale_y_fcurve, scale_z_fcurve]:
                fcurve.update()
        
        # Apply action to armature
        if not armature_obj.animation_data:
            armature_obj.animation_data_create()
        armature_obj.animation_data.action = action
        
        # Zero out armature object transform
        armature_obj.location = (0, 0, 0)
        armature_obj.rotation_euler = (0, 0, 0)
        armature_obj.rotation_quaternion = (1, 0, 0, 0)
        armature_obj.rotation_axis_angle = (0, 0, 1, 0)
        
        if context:
            context.view_layer.update()
        
        print(f"[lol_league_v4] Successfully imported ANM animation: {action_name}")
        return True, ""
        
    except Exception as e:
        import traceback
        error_msg = f"Failed to import ANM directly: {e}"
        print(f"[lol_league_v4] ERROR: {error_msg}")
        traceback.print_exc()
        return False, error_msg

