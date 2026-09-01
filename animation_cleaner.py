bl_info = {
    "name": "Game Dev Weight & Animation Tools",
    "author": "Assistant",
    "version": (1, 2),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > GameDev",
    "description": "Tools for weight limiting and mesh cleanup for game engines",
    "category": "Mesh",
}

import bpy

# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------

def _nla_actions(armature):
    """Return unique actions referenced by the armature's NLA strips."""
    animation_data = armature.animation_data
    if not animation_data:
        return []

    actions = []
    seen_actions = set()
    for track in animation_data.nla_tracks:
        for strip in track.strips:
            action = strip.action
            if action and action.as_pointer() not in seen_actions:
                seen_actions.add(action.as_pointer())
                actions.append(action)
    return actions


def _remove_faulty_fcurves(armature, action):
    removed_count = 0
    for fcurve in list(action.fcurves):
        try:
            armature.path_resolve(fcurve.data_path)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            action.fcurves.remove(fcurve)
            removed_count += 1
    return removed_count


def _build_nla_track_name(model_name, track_name):
    model_name = model_name if model_name else ""
    if not model_name in track_name:
        full_track_name = model_name + "_" + track_name
    else:
        full_track_name = track_name
    return "".join([c for c in full_track_name if c.isalnum() or c in ('_')]).rstrip()

# -------------------------------------------------------------------------
# UI Panel
# -------------------------------------------------------------------------

class VIEW3D_PT_game_dev_animation(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Batch Export'
    bl_label = "Animation Cleaner"

    def draw(self, context):
        scene = bpy.context.scene
        layout = self.layout
        col = layout.column(align=True)
        
        # Rigging/Weight Section
        box = layout.box()
        box.label(text="Animation Cleaner", icon='ACTION')
        col = box.column(align=True)
        col.operator(ANIMATION_OT_clean_nla_actions.bl_idname, icon='ACTION')
        col.operator(ANIMATION_OT_rename_nla_strip_names.bl_idname, icon='SORTALPHA')
 
# -------------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------------

class ANIMATION_OT_clean_nla_actions(bpy.types.Operator):
    """Remove invalid NLA F-curves and key all NLA actions at frame 0."""

    bl_idname = "animation.clean_nla_actions"
    bl_label = "Clean NLA Actions"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        original_frame = context.scene.frame_current
        original_active = context.view_layer.objects.active
        original_selected = list(context.selected_objects)
        cleaned_fcurves = 0
        keyed_actions = 0

        try:
            for armature in armatures:
                actions = _nla_actions(armature)
                if not actions:
                    continue

                animation_data = armature.animation_data
                original_action = animation_data.action
                original_mute_states = [track.mute for track in animation_data.nla_tracks]

                try:
                    for action in actions:
                        cleaned_fcurves += _remove_faulty_fcurves(armature, action)

                        animation_data.action = action
                        context.view_layer.objects.active = armature
                        bpy.ops.object.mode_set(mode='POSE') if armature.mode != 'POSE' else None
                        context.scene.frame_set(0)
                        result = bpy.ops.anim.keyframe_insert_menu(type='WholeCharacter')
                        if 'FINISHED' in result:
                            keyed_actions += 1
                finally:
                    animation_data.action = original_action
                    for track, mute_state in zip(animation_data.nla_tracks, original_mute_states):
                        track.mute = mute_state
        finally:
            context.scene.frame_set(original_frame)
            for obj in context.selected_objects:
                obj.select_set(False)
            for obj in original_selected:
                obj.select_set(True)
            context.view_layer.objects.active = original_active

        self.report(
            {'INFO'},
            f"Cleaned {cleaned_fcurves} faulty F-curves and keyed {keyed_actions} NLA actions",
        )
        return {'FINISHED'}


class ANIMATION_OT_rename_nla_strip_names(bpy.types.Operator):
    """Rename every NLA strip on selected armatures using the model prefix and track name."""

    bl_idname = "animation.rename_nla_strip_names"
    bl_label = "Rename NLA Strip Names"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        renamed_count = 0
        model_name = getattr(context.scene, "vizor_fbx_model_name", "") or ""

        for armature in armatures:
            if not armature.animation_data or not armature.animation_data.nla_tracks:
                continue

            for track in armature.animation_data.nla_tracks:
                if not track.strips:
                    continue

                full_track_name = _build_nla_track_name(model_name, track.name)
                for strip in track.strips:
                    if strip.name != full_track_name:
                        strip.name = full_track_name
                        renamed_count += 1

        self.report({'INFO'}, f"Renamed {renamed_count} NLA strips")
        return {'FINISHED'}


classes = (ANIMATION_OT_clean_nla_actions, ANIMATION_OT_rename_nla_strip_names, VIEW3D_PT_game_dev_animation)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

