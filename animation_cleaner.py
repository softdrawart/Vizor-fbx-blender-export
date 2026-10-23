bl_info = {
    "name": "Game Dev Weight & Animation Tools",
    "author": "Assistant",
    "version": (1, 2),
    "blender": (4, 5, 0),
    "location": "View3D > Sidebar > GameDev",
    "description": "Tools for weight limiting and mesh cleanup for game engines",
    "category": "Mesh",
}

import re

import bpy

# -------------------------------------------------------------------------
# Utilities
# -------------------------------------------------------------------------

REDUNDANT_RIG_CHANNEL_PREFIXES = ('ORG', 'MCH', 'DEF')


def _has_redundant_rig_prefix(name):
    if not name:
        return False
    normalized = name.upper().strip()
    if normalized.startswith(REDUNDANT_RIG_CHANNEL_PREFIXES):
        return True
    for prefix in REDUNDANT_RIG_CHANNEL_PREFIXES:
        if normalized.startswith(f"{prefix}-"):
            return True
    return False


def _channel_name_from_data_path(data_path):
    """Return the bone name from a pose-channel data path, if present."""
    match = re.search(r'pose\.bones\[(?:"|\')?([^"\']+)(?:"|\')?\]', data_path)
    if match:
        return match.group(1)
    return None

def get_all_fcurves(action):
    """Safely get all F-Curves in Blender 4 (action) and Blender 5 (slotted channelbags)."""
    if hasattr(action, 'fcurves'):
        return list(action.fcurves)
    fcurves_list = []
    if hasattr(action, 'slots') and hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        bag = strip.channelbag(slot)
                        if bag and hasattr(bag, 'fcurves'):
                            fcurves_list.extend(list(bag.fcurves))
                    except Exception:
                        continue
    return fcurves_list

def remove_fcurve(action, fcurve):
    """Safely removes an F-Curve in Blender 4 and Blender 5."""
    if hasattr(action, 'fcurves'):
        action.fcurves.remove(fcurve)
        return True
    if hasattr(action, 'slots') and hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        bag = strip.channelbag(slot)
                        if bag and hasattr(bag, 'fcurves') and fcurve in list(bag.fcurves):
                            bag.fcurves.remove(fcurve)
                            return True
                    except Exception:
                        continue
    return False

def get_all_groups(action):
    """Safely get all bone Groups in Blender 4 and Blender 5."""
    if hasattr(action, 'groups'):
        return list(action.groups)
    groups_list = []
    if hasattr(action, 'slots') and hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        bag = strip.channelbag(slot)
                        if bag and hasattr(bag, 'groups'):
                            groups_list.extend(list(bag.groups))
                    except Exception:
                        continue
    return groups_list

def remove_group(action, group):
    """Safely removes a bone Group in Blender 4 and Blender 5."""
    if hasattr(action, 'groups'):
        action.groups.remove(group)
        return True
    if hasattr(action, 'slots') and hasattr(action, 'layers'):
        for layer in action.layers:
            for strip in layer.strips:
                for slot in action.slots:
                    try:
                        bag = strip.channelbag(slot)
                        if bag and hasattr(bag, 'groups') and group in list(bag.groups):
                            bag.groups.remove(group)
                            return True
                    except Exception:
                        continue
    return False

def _remove_redundant_rig_channels(action):
    """Remove rig helper channels and their groups from the action."""
    removed_channels = []

    for fcurve in get_all_fcurves(action):
        bone_name = _channel_name_from_data_path(fcurve.data_path)
        if bone_name and _has_redundant_rig_prefix(bone_name):
            remove_fcurve(action, fcurve)
            removed_channels.append(bone_name)
            print(f"Removed rig channel from action '{action.name}': {bone_name}")

    for group in get_all_groups(action):
        group_name = group.name  # Save the name before deleting!
        if group_name and _has_redundant_rig_prefix(group_name):
            try:
                remove_group(action, group)
                print(f"Removed rig channel group from action '{action.name}': {group_name}")
            except RuntimeError:
                pass

    return len(removed_channels)

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
    for fcurve in get_all_fcurves(action):
        try:
            armature.path_resolve(fcurve.data_path)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            remove_fcurve(action, fcurve)
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
        return (
            context.mode == 'OBJECT' and 
            any(
                obj.type == 'ARMATURE' and 
                obj.mode == 'OBJECT' and 
                (obj.animation_data is None or obj.animation_data.action is None) 
                for obj in context.selected_objects
            )
        )

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
                        cleaned_fcurves += _remove_redundant_rig_channels(action)
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
            f"Removed {cleaned_fcurves} redundant/invalid channels and keyed {keyed_actions} NLA actions",
        )
        return {'FINISHED'}


class ANIMATION_OT_rename_nla_strip_names(bpy.types.Operator):
    """Rename every NLA strip on selected armatures using the model prefix and track name."""

    bl_idname = "animation.rename_nla_strip_names"
    bl_label = "Rename NLA Strip Names"
    bl_options = {'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(obj.type == 'ARMATURE' for obj in context.selected_objects) and context.mode == 'OBJECT'

    def execute(self, context):
        armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
        model_name = getattr(context.scene, "vizor_fbx_model_name", "") or ""
        renamed_strips = 0
        renamed_actions = 0

        for armature in armatures:
            if not armature.animation_data or not armature.animation_data.nla_tracks:
                continue

            for track in armature.animation_data.nla_tracks:
                if not track.strips:
                    continue

                full_track_name = _build_nla_track_name(model_name, track.name)
                for strip in track.strips:
                    if strip.name != full_track_name:
                        old_strip_name = strip.name
                        strip.name = full_track_name
                        renamed_strips += 1
                        print(f"Renamed NLA strip on {armature.name}: {old_strip_name} -> {full_track_name}")

                    action = strip.action
                    if action and action.name != full_track_name:
                        old_action_name = action.name
                        action.name = full_track_name
                        renamed_actions += 1
                        print(f"Renamed NLA action on {armature.name}: {old_action_name} -> {full_track_name}")

        self.report(
            {'INFO'},
            f"Renamed {renamed_strips} NLA strips and {renamed_actions} NLA actions",
        )
        return {'FINISHED'}


classes = (ANIMATION_OT_clean_nla_actions, ANIMATION_OT_rename_nla_strip_names, VIEW3D_PT_game_dev_animation)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

