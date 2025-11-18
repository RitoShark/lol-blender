"""
Limit to 4 Influences Operator
Limits vertex weights to maximum 4 bone influences per vertex (League of Legends requirement)
"""

import bpy
from bpy.types import Operator
from bpy.props import FloatProperty


class LOLLeagueLimitInfluences_V4(Operator):
    """Limit vertex weights to maximum 4 bone influences per vertex"""
    bl_idname = "lol_league_v4.limit_influences"
    bl_label = "Limit to 4 Influences"
    bl_description = "Limit all vertices to maximum 4 bone influences (required for LoL export)"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        obj = context.active_object
        
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a mesh object")
            return {'CANCELLED'}
        
        mesh = obj.data
        
        # Check if mesh has vertex groups
        if not obj.vertex_groups:
            self.report({'WARNING'}, "Mesh has no vertex groups")
            return {'CANCELLED'}
        
        # Count vertices with more than 4 influences
        vertices_fixed = 0
        
        # Process each vertex
        for vertex in mesh.vertices:
            # Get all weights for this vertex
            vertex_weights = []
            for group in vertex.groups:
                if group.weight > 0.001:  # Only consider significant weights
                    vertex_weights.append((group.group, group.weight))
            
            # If vertex has more than 4 influences, limit it
            if len(vertex_weights) > 4:
                # Sort by weight (descending)
                vertex_weights.sort(key=lambda x: x[1], reverse=True)
                
                # Keep only top 4
                top_4 = vertex_weights[:4]
                
                # Calculate sum of top 4 weights for normalization
                weight_sum = sum(w for _, w in top_4)
                
                if weight_sum > 0.001:
                    # Remove vertex from all groups first
                    for group_idx, _ in vertex_weights:
                        obj.vertex_groups[group_idx].remove([vertex.index])
                    
                    # Re-add with normalized weights
                    for group_idx, weight in top_4:
                        normalized_weight = weight / weight_sum
                        obj.vertex_groups[group_idx].add([vertex.index], normalized_weight, 'REPLACE')
                    
                    vertices_fixed += 1
        
        if vertices_fixed == 0:
            self.report({'INFO'}, "All vertices already have 4 or fewer influences")
        else:
            self.report({'INFO'}, f"Limited {vertices_fixed} vertices to 4 influences")
        
        return {'FINISHED'}
    
    @classmethod
    def poll(cls, context):
        return (context.active_object and 
                context.active_object.type == 'MESH' and
                context.active_object.vertex_groups)

