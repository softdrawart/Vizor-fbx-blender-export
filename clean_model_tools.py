bl_info = {
    "name": "Game Dev Weight & Mesh Tools",
    "author": "Assistant",
    "version": (1, 2),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > GameDev",
    "description": "Tools for weight limiting and mesh cleanup for game engines",
    "category": "Mesh",
}

import bpy
import bmesh

# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------

def get_deform_bone_names(obj):
    """Finds the armature influencing the mesh and returns names of deforming bones."""
    arm_mod = next((m for m in obj.modifiers if m.type == 'ARMATURE' and m.object), None)
    if arm_mod and arm_mod.object:
        return {b.name for b in arm_mod.object.data.bones if b.use_deform}
    
    # Fallback to parent if no modifier
    if obj.parent and obj.parent.type == 'ARMATURE':
        return {b.name for b in obj.parent.data.bones if b.use_deform}
    
    return set()

def limit_weights(obj, limit):
    """Prune weights to a specific limit reliably."""
    # 1. Save current context
    original_mode = obj.mode
    old_active = bpy.context.view_layer.objects.active
    
    # 2. Set object as active
    bpy.context.view_layer.objects.active = obj
    
    # 3. Switch to Weight Paint Mode (the 'native' home for this operator)
    if obj.mode != 'WEIGHT_PAINT':
        bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
    
    # 4. Run the operator
    # group_select_mode='ALL' ensures it checks all groups, not just the locked/unlocked ones
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=limit)
    
    # 5. Restore original mode and active object
    bpy.ops.object.mode_set(mode=original_mode)
    bpy.context.view_layer.objects.active = old_active

# -------------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------------

class MESH_OT_check_total_deform_bones(bpy.types.Operator):
    """Check if the total number of deforming bones used by this mesh exceeds the engine limit"""
    bl_idname = "mesh.check_total_deform_bones"
    bl_label = "Check Total Bone Count"
    bl_description = "Check if the mesh has more than the allowed total deformation bones (e.g., 50)"
    bl_options = {'REGISTER', 'UNDO'}

    max_bones: bpy.props.IntProperty(
        name="Max Total Bones",
        description="Maximum deformation bones allowed per mesh by the engine",
        default=50,
        min=1
    )

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        over_limit_found = False

        for obj in selected_meshes:
            deform_bone_names = get_deform_bone_names(obj)
            if not deform_bone_names:
                continue
            
            # Find the intersection of vertex groups on the mesh and deforming bones in the armature
            mesh_vgroup_names = {vg.name for vg in obj.vertex_groups}
            active_deform_groups = mesh_vgroup_names.intersection(deform_bone_names)
            
            count = len(active_deform_groups)
            
            if count > self.max_bones:
                self.report({'ERROR'}, f"'{obj.name}' exceeds limit: {count}/{self.max_bones} bones!")
                over_limit_found = True
            else:
                self.report({'INFO'}, f"'{obj.name}': {count}/{self.max_bones} bones (OK)")

        if not over_limit_found:
            self.report({'INFO'}, "All selected meshes within bone count limits.")
            
        return {'FINISHED'}


class MESH_OT_clean_model_data(bpy.types.Operator):
    """Remove all Vertex Colors and keep only the active UV map"""
    bl_idname = "mesh.clean_model_vertex_color_uv"
    bl_label = "Clean Colors & UVs"
    bl_description = "Removes all vertex color attributes and all UV maps except the active one"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return all(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        for obj in selected_meshes:
            # 1. Clean Vertex Colors (Color Attributes)
            # Modern Blender (3.2+) uses color_attributes
            colors = obj.data.color_attributes
            while colors:
                colors.remove(colors[0])
            
            # 2. Clean UV Maps (Keep only active)
            uv_layers = obj.data.uv_layers
            if len(uv_layers) > 1:
                active_uv_name = uv_layers.active.name
                # Create a list of layers to remove (avoiding mutating the list while iterating)
                to_remove = [layer.name for layer in uv_layers if layer.name != active_uv_name]
                for layer_name in to_remove:
                    uv_layers.remove(uv_layers[layer_name])
                    
            self.report({'INFO'}, f"Cleaned {obj.name}")

        return {'FINISHED'}


class MESH_OT_check_weight_limit(bpy.types.Operator):
    """Select vertices exceeding the maximum allowed bone influences"""
    bl_idname = "mesh.check_weight_limit"
    bl_label = "Check Per-Vertex Influences"
    bl_options = {'REGISTER', 'UNDO'}

    max_limit: bpy.props.IntProperty(
        name="Max Influences",
        description="Maximum number of deformation bones per vertex",
        default=4,
        min=1,
        max=32
    )

    @classmethod
    def poll(cls, context):
        return all(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        total_offenders = 0

        for obj in selected_meshes:
            deform_bones = get_deform_bone_names(obj)
            if not deform_bones:
                self.report({'INFO'}, f"Skip {obj.name}: No armature/deform bones found")
                continue

            # Switch to Edit Mode to manipulate selection
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode='EDIT')
            
            bm = bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            
            # Get vertex group indices that are deformation bones
            deform_indices = {obj.vertex_groups[name].index for name in deform_bones if name in obj.vertex_groups}
            
            # Reset selection
            bpy.ops.mesh.select_all(action='DESELECT')
            
            dvert_lay = bm.verts.layers.deform.active
            if not dvert_lay:
                continue

            for v in bm.verts:
                dvert = v[dvert_lay]
                # Count only groups that belong to deforming bones
                influence_count = sum(1 for group_idx, weight in dvert.items() if group_idx in deform_indices and weight > 0.0001)
                
                if influence_count > self.max_limit:
                    v.select = True
                    total_offenders += 1
            
            bmesh.update_edit_mesh(obj.data)
            
        if total_offenders > 0:
            self.report({'WARNING'}, f"Found {total_offenders} vertices over limit")
        else:
            self.report({'INFO'}, "All vertices clean")
            bpy.ops.object.mode_set(mode='OBJECT')

        return {'FINISHED'}

class CLEAR_EMPTY_WEIGHTS_OT_VIZOR(bpy.types.Operator):
    bl_idname = "skin.clear_empty_weights"
    bl_label = "clear empty weights from object"
    bl_description = "clear empty weights from object"
    bl_options = {'REGISTER', 'UNDO'}

    threshold: bpy.props.FloatProperty(default=0, min=0, max=1)

    def find_weights(self, obj):
        maxWeight = {}
        for i in obj.vertex_groups:
            maxWeight[i.index] = 0

        for v in obj.data.vertices:
            for g in v.groups:
                gn = g.group
                w = obj.vertex_groups[gn].weight(v.index)
                if (maxWeight.get(gn) is None or w>maxWeight[gn]):
                    maxWeight[gn] = w
        return maxWeight
    def remove_empty_weights(self, obj):
        maxWeight = self.find_weights(obj)
        # fix bug pointed out by user2859
        ka = []
        ka.extend(maxWeight.keys())
        ka.sort(key=lambda gn: -gn)
        print (ka)
        for gn in ka:
            if maxWeight[gn]<=self.threshold:
                print ("delete %d"%gn)
                obj.vertex_groups.remove(obj.vertex_groups[gn]) # actually remove the group

    def execute(self, context):
        obj = context.active_object
        for obj in [obj for obj in context.selected_objects if obj.type=='MESH']:
            self.remove_empty_weights(obj)
        return {'FINISHED'}


class MESH_OT_prune_weight_limit(bpy.types.Operator):
    """Prune weights to match max influence limit"""
    bl_idname = "mesh.prune_weight_limit"
    bl_label = "Prune Weights"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return all(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        limit = context.scene.game_dev_max_influence
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                limit_weights(obj, limit)
        return {'FINISHED'}

class MESH_RemoveNonDeformVGroups_OT_VIZOR(bpy.types.Operator):
    """Remove all vertex groups not associated with a deforming bone in the armature(s)"""
    bl_idname = "mesh.remove_non_deform_vgroups"
    bl_label = "Remove Non-Deform Vertex Groups"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'MESH' for obj in context.selected_objects)

    def execute(self, context):
        # Filter selection to meshes only
        selected_meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        
        total_removed_count = 0
        processed_objects_count = 0

        for obj in selected_meshes:
            # 1. Find all armature modifiers for THIS specific object
            arm_modifiers = [m for m in obj.modifiers if m.type == 'ARMATURE' and m.object]
            
            # Skip this object if it has no armatures assigned
            if not arm_modifiers:
                continue
                
            # 2. Build a set of all valid deform bone names from all attached armatures
            deform_bone_names = set()
            for mod in arm_modifiers:
                arm_obj = mod.object
                for bone in arm_obj.data.bones:
                    if bone.use_deform:
                        deform_bone_names.add(bone.name)

            # 3. Identify vertex groups on this mesh that are NOT in the deform set
            vgroups_to_remove = [vg for vg in obj.vertex_groups if vg.name not in deform_bone_names]

            # 4. Remove the groups
            if vgroups_to_remove:
                processed_objects_count += 1
                for vg in vgroups_to_remove:
                    obj.vertex_groups.remove(vg)
                    total_removed_count += 1
            
        # Final report
        self.report(
            {'INFO'}, 
            f"Processed {processed_objects_count} objects. Removed {total_removed_count} vertex groups."
        )
        
        return {'FINISHED'}

# -------------------------------------------------------------------------
# Modal Operator for Real-time Limiting
# -------------------------------------------------------------------------

class MESH_OT_auto_limit_modal(bpy.types.Operator):
    """Enforce weight limit in real-time during painting"""
    bl_idname = "mesh.auto_limit_modal"
    bl_label = "Auto Limit Weights"
    
    _handle = None

    @classmethod
    def poll(cls, context):
        return context.area.type == 'VIEW_3D' and context.mode == 'PAINT_WEIGHT'

    def modal(self, context, event):
        if not context.scene.game_dev_auto_limit:
            self.cancel(context)
            return {'FINISHED'}

        if context.mode == 'PAINT_WEIGHT' and event.type in {'MOUSEMOVE', 'LEFTMOUSE'}:
            obj = context.active_object
            if obj and obj.type == 'MESH':
                limit_weights(obj, context.scene.game_dev_max_influence)

        return {'PASS_THROUGH'}

    def execute(self, context):
        if context.scene.game_dev_auto_limit:
            context.scene.game_dev_auto_limit = False
            return {'FINISHED'}
        
        context.scene.game_dev_auto_limit = True
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        context.scene.game_dev_auto_limit = False



# -------------------------------------------------------------------------
# UI Panel
# -------------------------------------------------------------------------

class VIEW3D_PT_game_dev_weights(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Batch Export'
    bl_label = "Weight Limiter"

    def draw(self, context):
        scene = bpy.context.scene
        layout = self.layout
        col = layout.column(align=True)
        
        # Rigging/Weight Section
        box = layout.box()
        box.label(text="Engine Bone Limits", icon='ARMATURE_DATA')
        col = box.column(align=True)
        col.prop(scene, "game_dev_total_bone_limit", text="Total Limit")
        op = col.operator(MESH_OT_check_total_deform_bones.bl_idname, text="Check Total Bone Count")
        op.max_bones = scene.game_dev_total_bone_limit
        
        # 2. Weight Management Section
        box = layout.box()
        box.label(text="Weight Influences (Per-Vertex)", icon='BONE_DATA')
        col = box.column(align=True)
        col.prop(scene, "game_dev_max_influence", text="Max Per-Vertex")
        col.separator()
        
        op_check = col.operator(MESH_OT_check_weight_limit.bl_idname, text="Check & Select Overlimit")
        op_check.max_limit = scene.game_dev_max_influence
        
        col.operator(MESH_OT_prune_weight_limit.bl_idname, text="Prune Influences")
        
        # Modal Toggle Button
        is_active = scene.game_dev_auto_limit
        col.operator(MESH_OT_auto_limit_modal.bl_idname, 
                    text="Auto-Limit: ON" if is_active else "Auto-Limit: OFF", 
                    depress=is_active,
                    icon='BRUSH_DATA')

        # Cleanup Section
        box = layout.box()
        box.label(text="Mesh Cleanup", icon='MESH_DATA')
        col = box.column()
        col.operator(MESH_RemoveNonDeformVGroups_OT_VIZOR.bl_idname, text="Remove Non-Deform Vertex Groups")
        col.operator(MESH_OT_clean_model_data.bl_idname, text="Clean Colors & UVs")
        col.operator(CLEAR_EMPTY_WEIGHTS_OT_VIZOR.bl_idname, text="Clear Empty Weights")

# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------

classes = (
    MESH_OT_check_total_deform_bones,
    MESH_OT_check_weight_limit,
    MESH_OT_prune_weight_limit,
    MESH_OT_auto_limit_modal,
    MESH_OT_clean_model_data,
    MESH_RemoveNonDeformVGroups_OT_VIZOR,
    CLEAR_EMPTY_WEIGHTS_OT_VIZOR,
    VIEW3D_PT_game_dev_weights,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.Scene.game_dev_max_influence = bpy.props.IntProperty(
        name="Max Per-Vertex Influence",
        default=4, min=1, max=32
    )
    bpy.types.Scene.game_dev_total_bone_limit = bpy.props.IntProperty(
        name="Max Total Deform Bones",
        default=50, min=1
    )
    bpy.types.Scene.game_dev_auto_limit = bpy.props.BoolProperty(
        name="Auto Limit Active",
        default=False
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    del bpy.types.Scene.game_dev_max_influence
    del bpy.types.Scene.game_dev_total_bone_limit
    del bpy.types.Scene.game_dev_auto_limit

if __name__ == "__main__":
    register()