bl_info = {
    "name": "Vizor NPC FBX Exporter",
    "author": "AI Assistant with Mikhail Lebedev",
    "version": (1, 4),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Batch Export",
    "description": "Exports Model and NLA with Vizor script settings",
    "category": "Import-Export",
}

import bpy
import os

GLOBAL_SCALE=0.75 #scale of the model exported
MAX_ALLOWED_MESHES = 2 #max meshes allowed to be selected for export
def update_global_scale(self, context):
    global GLOBAL_SCALE
    GLOBAL_SCALE = self.vizor_global_scale

def update_max_meshes(self, context):
    global MAX_ALLOWED_MESHES
    MAX_ALLOWED_MESHES = self.vizor_max_meshes

# -------------------------------------------------------------------------
# UI Panel
# -------------------------------------------------------------------------

class VIEW3D_PT_vizor_exporter_precise(bpy.types.Panel):
    bl_label = "Vizor Batch Exporter"
    bl_idname = "VIEW3D_PT_vizor_exporter_precise"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Batch Export'


    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "export_path", text="Folder")

        layout.prop(scene, "vizor_fbx_model_name", text="FBX Model Name")

        layout.prop(scene, "vizor_global_scale", text="Global Scale")

        layout.prop(scene, "vizor_max_meshes", text="Max Meshes")
        
        """ layout.label(text=f"Export Model FBX:")
        layout.operator(EXPORT_OT_vizor_model.bl_idname, icon='MESH_DATA')
        
        layout.separator()
        
        layout.label(text="Export Animations Separate FBX:")
        layout.operator(EXPORT_OT_vizor_nla_separate.bl_idname, icon='ANIM_DATA')

        layout.separator()
        
        layout.label(text="Export Animations One FBX:")
        layout.operator(EXPORT_OT_vizor_full_mesh_anim.bl_idname, icon='ANIM_DATA')

        layout.separator()
        
        layout.label(text="Export Animations One FBX:")
        layout.operator(EXPORT_OT_vizor_active_nla_mesh.bl_idname, icon='ANIM_DATA') """

                
        layout.separator()
        layout.label(text="NPC Workflow:", icon='FORCE_VORTEX')
        layout.operator(EXPORT_OT_vizor_save_textures.bl_idname, icon='TEXTURE')
        layout.operator(EXPORT_OT_vizor_npc_combined.bl_idname, icon='EXPORT')
        layout.operator(EXPORT_OT_vizor_npc_model_only.bl_idname, icon='MESH_DATA')
        layout.operator(EXPORT_OT_vizor_npc_active_anim.bl_idname, icon='ACTION')
        
# -------------------------------------------------------------------------
# Operators
# -------------------------------------------------------------------------

class EXPORT_OT_vizor_model(bpy.types.Operator):
    """Export Model using (mob_clon2) settings"""
    bl_idname = "export.vizor_model"
    bl_label = "Export Model (mob_clon2)"

    @classmethod
    def poll(cls, context):
        # Check if selection contains both an Armature and a Mesh
        selected = context.selected_objects
        has_armature = any(obj.type == 'ARMATURE' for obj in selected)
        has_mesh = any(obj.type == 'MESH' for obj in selected)
        return has_armature and has_mesh and len(selected) <= MAX_ALLOWED_MESHES

    def execute(self, context):
        obj = context.active_object

        # Use the name of the first armature found in selection for the filename
        naming_obj = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        if not naming_obj:
            self.report({'ERROR'}, "No Armature found")
            return {'CANCELLED'}

        
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(context.scene.export_path)
        file_path = os.path.join(export_path, naming_obj.name + "_Model.fbx")

        # Settings from mob_clon2.py
        bpy.ops.export_scene.vizor_fbx(
            filepath=file_path,
            use_selection=True,
            use_visible=False,
            use_active_collection=False,
            global_scale=GLOBAL_SCALE, #scale of the model exported
            apply_unit_scale=True,
            apply_scale_options='FBX_SCALE_UNITS',
            use_space_transform=True,
            bake_space_transform=True,
            object_types={'ARMATURE', 'MESH'},
            use_mesh_modifiers=True,
            use_mesh_modifiers_render=True,
            mesh_smooth_type='OFF',
            colors_type='SRGB',
            prioritize_active_color=False,
            use_subsurf=False,
            use_mesh_edges=False,
            use_tspace=False,
            use_triangles=False,
            use_custom_props=False,
            add_leaf_bones=False,
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            use_armature_deform_only=True,
            armature_nodetype='NULL',
            bake_anim=False,
            bake_anim_use_all_bones=False,
            bake_anim_use_nla_strips=True,
            bake_anim_use_all_actions=False,
            bake_anim_force_startend_keying=False,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
            path_mode='AUTO',
            embed_textures=False,
            batch_mode='OFF',
            use_batch_own_dir=True,
            axis_forward='-Z',
            axis_up='Y'
        )

        self.report({'INFO'}, f"Model Exported: {obj.name}_Model.fbx")
        return {'FINISHED'}

class EXPORT_OT_vizor_nla_separate(bpy.types.Operator):
    """Export NLA Tracks using (my_HH_export_animation) settings"""
    bl_idname = "export.vizor_nla_separate"
    bl_label = "Export NLA Tracks (my_HH)"
    
    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'ARMATURE' and len(context.selected_objects) == 1

    def execute(self, context):
        obj = context.active_object
        if not obj or obj.type != 'ARMATURE' or not obj.animation_data:
            self.report({'ERROR'}, "Select Armature with NLA tracks")
            return {'CANCELLED'}

        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(context.scene.export_path)
        if not os.path.exists(export_path): os.makedirs(export_path)

        # Cache state
        original_mute_states = [t.mute for t in obj.animation_data.nla_tracks]
        original_frame_start = context.scene.frame_start
        original_frame_end = context.scene.frame_end

        # Only select the Armature (as per settings: object_types={'ARMATURE'})
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True)

        tracks = obj.animation_data.nla_tracks
        for track in tracks:
            if not track.strips: continue
            
            # Solo the track
            for t in tracks: t.mute = True
            track.mute = False
            
            # Set frames
            start_f = min(s.frame_start for s in track.strips)
            end_f = max(s.frame_end for s in track.strips)
            context.scene.frame_start, context.scene.frame_end = int(start_f), int(end_f)
            
            file_name = "".join([c for c in track.name if c.isalnum() or c in (' ', '.', '_')]).rstrip()
            file_path = os.path.join(export_path, file_name + ".fbx")

            # Settings from my_HH_export_animation.py
            bpy.ops.export_scene.vizor_fbx(
                filepath=file_path,
                use_selection=True,
                use_visible=False,
                use_active_collection=False,
                global_scale=GLOBAL_SCALE,
                apply_unit_scale=False,
                apply_scale_options='FBX_SCALE_UNITS',
                use_space_transform=False,
                bake_space_transform=False,
                object_types={'ARMATURE'},
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=True,
                mesh_smooth_type='OFF',
                colors_type='SRGB',
                prioritize_active_color=False,
                use_subsurf=False,
                use_mesh_edges=False,
                use_tspace=False,
                use_triangles=False,
                use_custom_props=False,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=True,
                armature_nodetype='REMOVE_GHOST',
                bake_anim=True,
                bake_anim_use_all_bones=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=False,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=0.0,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=True,
                axis_forward='Y',
                axis_up='Z'
            )

        # Restore
        for i, track in enumerate(obj.animation_data.nla_tracks):
            track.mute = original_mute_states[i]
        context.scene.frame_start, context.scene.frame_end = original_frame_start, original_frame_end

        self.report({'INFO'}, f"Exported {len(tracks)} Animations")
        return {'FINISHED'}

class EXPORT_OT_vizor_full_mesh_anim(bpy.types.Operator):
    """Export single FBX with Armature + Meshes + All Animations (Single File)"""
    bl_idname = "export.vizor_full_mesh_anim_precise"
    bl_label = "Export Full Model + All Anims"

    @classmethod
    def poll(cls, context):
        selected = context.selected_objects
        has_armature = any(obj.type == 'ARMATURE' for obj in selected)
        len_meshes = sum(1 for obj in selected if obj.type == 'MESH')
        has_mesh = len_meshes > 0
        return has_armature and has_mesh and len_meshes <= MAX_ALLOWED_MESHES

    def execute(self, context):
        naming_obj = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(context.scene.export_path)
        file_path = os.path.join(export_path, naming_obj.name + "_Full.fbx")

        # 1. STORE EXISTING MUTE STATES
        state_backup = []
        if naming_obj.animation_data and naming_obj.animation_data.nla_tracks:
            for track in naming_obj.animation_data.nla_tracks:
                track_info = {
                    'track': track,
                    'mute': track.mute,
                    'strips': [{'strip': s, 'mute': s.mute} for s in track.strips]
                }
                state_backup.append(track_info)
                
                # 2. ENABLE EVERYTHING FOR EXPORT
                track.mute = False
                for strip in track.strips:
                    strip.mute = False

        # Use Animation Settings (Scale 1.0, Y Forward) but export both Mesh and Armature
        # Includes all animations (NLA Strips + All Actions)
        bpy.ops.export_scene.vizor_fbx(
                filepath=file_path,
                use_selection=True,
                use_visible=False,
                object_types={'ARMATURE', 'MESH'},
                use_active_collection=False,
                global_scale=GLOBAL_SCALE,
                apply_unit_scale=False,
                apply_scale_options='FBX_SCALE_UNITS',
                use_space_transform=False,
                bake_space_transform=False,
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=True,
                mesh_smooth_type='OFF',
                colors_type='SRGB',
                prioritize_active_color=False,
                use_subsurf=False,
                use_mesh_edges=False,
                use_tspace=False,
                use_triangles=False,
                use_custom_props=False,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=True,
                armature_nodetype='REMOVE_GHOST',
                bake_anim=True,
                bake_anim_use_all_bones=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=False,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=0.0,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=True,
                axis_forward='Y',
                axis_up='Z'
            )
        
        # 4. REVERT TO STORED MUTE STATES
        for info in state_backup:
            info['track'].mute = info['mute']
            for s_info in info['strips']:
                s_info['strip'].mute = s_info['mute']

        self.report({'INFO'}, f"Full Model Exported: {naming_obj.name}_Full.fbx")
        return {'FINISHED'}

class EXPORT_OT_vizor_active_nla_mesh(bpy.types.Operator):
    """Export the currently UNMUTED NLA track with selected Meshes"""
    bl_idname = "export.vizor_active_nla_mesh"
    bl_label = "Export Active NLA + Mesh"

    @classmethod
    def poll(cls, context):
        selected = context.selected_objects
        has_armature = any(obj.type == 'ARMATURE' for obj in selected)
        len_meshes = sum(1 for obj in selected if obj.type == 'MESH')
        has_mesh = len_meshes > 0
        return has_armature and has_mesh and len_meshes <= MAX_ALLOWED_MESHES

    def execute(self, context):
        arm = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        
        if not arm.animation_data or not arm.animation_data.nla_tracks:
            self.report({'ERROR'}, "No NLA data found on Armature")
            return {'CANCELLED'}

        # Find the first track that is not muted
        active_track = next((t for t in arm.animation_data.nla_tracks if not t.mute), None)
        
        if not active_track:
            self.report({'ERROR'}, "No unmuted NLA track found")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(context.scene.export_path)
        file_path = os.path.join(export_path, active_track.name + ".fbx")

        # Sync frame range to track
        orig_start, orig_end = context.scene.frame_start, context.scene.frame_end
        if active_track.strips:
            s_f = min(s.frame_start for s in active_track.strips)
            e_f = max(s.frame_end for s in active_track.strips)
            context.scene.frame_start, context.scene.frame_end = int(s_f), int(e_f)

        bpy.ops.export_scene.vizor_fbx(
            filepath=file_path,
            use_selection=True,
            use_visible=False,
            object_types={'ARMATURE', 'MESH'},
            global_scale=GLOBAL_SCALE,
            apply_unit_scale=False,
            apply_scale_options='FBX_SCALE_UNITS',
            use_space_transform=False,
            bake_space_transform=False,
            mesh_smooth_type='OFF',
            primary_bone_axis='Y',
            secondary_bone_axis='X',
            use_armature_deform_only=True,
            armature_nodetype='REMOVE_GHOST',
            bake_anim=True,
            bake_anim_use_all_bones=True,
            bake_anim_use_nla_strips=True,
            bake_anim_use_all_actions=False, # Only export the active NLA track
            bake_anim_force_startend_keying=True,
            bake_anim_step=1.0,
            bake_anim_simplify_factor=0.0,
            axis_forward='Y',
            axis_up='Z',
            path_mode='AUTO'
        )

        context.scene.frame_start, context.scene.frame_end = orig_start, orig_end
        self.report({'INFO'}, f"Exported Active Track: {active_track.name}.fbx")
        return {'FINISHED'}

class EXPORT_OT_vizor_npc_combined(bpy.types.Operator):
    """Stage 1: Export Model (Rest Pose) | Stage 2: Export NLA Tracks (Pose)"""
    bl_idname = "export.vizor_npc_combined"
    bl_label = "NPC Full Export (Model + Anims)"

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT':
            return False
        selected = context.selected_objects
        has_armature = any(obj.type == 'ARMATURE' for obj in selected)
        len_meshes = sum(1 for obj in selected if obj.type == 'MESH')
        has_mesh = len_meshes > 0
        return has_armature and has_mesh and len_meshes <= MAX_ALLOWED_MESHES

    def execute(self, context):
        # 1. SETUP & PATH VALIDATION
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}
        
        export_path = bpy.path.abspath(context.scene.export_path)
        if not os.path.exists(export_path):
            os.makedirs(export_path)

        # Identify Armature and Meshes
        arm = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        
        # BACKUP ORIGINAL STATE
        original_active = context.view_layer.objects.active
        original_selection = context.selected_objects[:]
        original_pose_position = arm.data.pose_position  # Store if it was 'POSE' or 'REST'
        original_frame_start = context.scene.frame_start
        original_frame_end = context.scene.frame_end
        
        original_nla_mutes = []
        if arm.animation_data and arm.animation_data.nla_tracks:
            for track in arm.animation_data.nla_tracks:
                original_nla_mutes.append((track, track.mute))

        try:
            # --- STAGE 1: EXPORT MODEL (NPC_Model.py settings) ---
            self.report({'INFO'}, "Stage 1: Exporting Model (Rest Pose)...")
            arm.data.pose_position = 'REST'
            
            # Selection: Armature + Meshes
            bpy.ops.object.select_all(action='DESELECT')
            arm.select_set(True)
            for m in meshes: m.select_set(True)
            context.view_layer.objects.active = arm

            model_name = context.scene.vizor_fbx_model_name if context.scene.vizor_fbx_model_name else arm.name
            
            safe_name = "".join([c for c in model_name if c.isalnum() or c in ('_')]).rstrip()
            model_path = os.path.join(export_path, f"{safe_name}.fbx")

            bpy.ops.export_scene.vizor_fbx(
                filepath=model_path,
                use_selection=True,
                use_visible=False,
                use_active_collection=False,
                global_scale=GLOBAL_SCALE,
                apply_unit_scale=False,
                apply_scale_options='FBX_SCALE_UNITS',
                use_space_transform=False,
                bake_space_transform=False,
                object_types={'MESH', 'ARMATURE'},
                use_mesh_modifiers=True,
                use_mesh_modifiers_render=True,
                mesh_smooth_type='OFF',
                colors_type='SRGB',
                prioritize_active_color=False,
                use_subsurf=False,
                use_mesh_edges=False,
                use_tspace=False,
                use_triangles=False,
                use_custom_props=False,
                add_leaf_bones=False,
                primary_bone_axis='Y',
                secondary_bone_axis='X',
                use_armature_deform_only=True,
                armature_nodetype='REMOVE_GHOST',
                bake_anim=False,
                bake_anim_use_all_bones=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=True,
                bake_anim_force_startend_keying=True,
                bake_anim_step=1.0,
                bake_anim_simplify_factor=1.0,
                path_mode='AUTO',
                embed_textures=False,
                batch_mode='OFF',
                use_batch_own_dir=True,
                axis_forward='Y',
                axis_up='Z'
            )

            # --- STAGE 2: EXPORT ANIMATIONS (NPC_Animation.py settings) ---
            self.report({'INFO'}, "Stage 2: Exporting Animations (Pose)...")
            arm.data.pose_position = 'POSE'
            
            # Selection: Armature Only
            bpy.ops.object.select_all(action='DESELECT')
            arm.select_set(True)
            context.view_layer.objects.active = arm

            if arm.animation_data and arm.animation_data.nla_tracks:
                tracks = arm.animation_data.nla_tracks
                for track in tracks:
                    if not track.strips: continue
                    
                    # Solo the track
                    for t in tracks: t.mute = True
                    track.mute = False
                    
                    # Set frames to match the animation track
                    start_f = min(s.frame_start for s in track.strips)
                    end_f = max(s.frame_end for s in track.strips)
                    context.scene.frame_start, context.scene.frame_end = int(start_f), int(end_f)
                    
                    # Clean filename
                    model_name = context.scene.vizor_fbx_model_name if context.scene.vizor_fbx_model_name else ""
                    if not model_name in track.name:
                        full_track_name = model_name + "_" + track.name
                    else:
                        full_track_name = track.name
                    safe_name = "".join([c for c in full_track_name if c.isalnum() or c in ('_')]).rstrip()
                    anim_path = os.path.join(export_path, f"{safe_name}.fbx")

                    bpy.ops.export_scene.vizor_fbx(
                        filepath=anim_path,
                        use_selection=True,
                        use_visible=False,
                        use_active_collection=False,
                        global_scale=GLOBAL_SCALE,
                        apply_unit_scale=False,
                        apply_scale_options='FBX_SCALE_UNITS',
                        use_space_transform=False,
                        bake_space_transform=False,
                        object_types={'ARMATURE'},
                        use_mesh_modifiers=True,
                        use_mesh_modifiers_render=True,
                        mesh_smooth_type='OFF',
                        colors_type='SRGB',
                        prioritize_active_color=False,
                        use_subsurf=False,
                        use_mesh_edges=False,
                        use_tspace=False,
                        use_triangles=False,
                        use_custom_props=False,
                        add_leaf_bones=False,
                        primary_bone_axis='Y',
                        secondary_bone_axis='X',
                        use_armature_deform_only=True,
                        armature_nodetype='REMOVE_GHOST',
                        bake_anim=True,
                        bake_anim_use_all_bones=True,
                        bake_anim_use_nla_strips=True,
                        bake_anim_use_all_actions=False,
                        bake_anim_force_startend_keying=True,
                        bake_anim_step=1.0,
                        bake_anim_simplify_factor=0.0,
                        path_mode='AUTO',
                        embed_textures=False,
                        batch_mode='OFF',
                        use_batch_own_dir=True,
                        axis_forward='Y',
                        axis_up='Z'
                    )

        finally:
            # --- RESTORE PRE-EXPORT STATE ---
            arm.data.pose_position = original_pose_position
            context.scene.frame_start = original_frame_start
            context.scene.frame_end = original_frame_end
            
            # Restore NLA mutes
            for track, mute_val in original_nla_mutes:
                track.mute = mute_val
            
            # Restore Selection and Active Object
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                try: obj.select_set(True)
                except: pass
            context.view_layer.objects.active = original_active

        self.report({'INFO'}, "Combined NPC Export Complete")
        return {'FINISHED'}

class EXPORT_OT_vizor_save_textures(bpy.types.Operator):
    """Find images connected to Material Output and save them to the 'textures' folder"""
    bl_idname = "export.vizor_save_textures"
    bl_label = "Save Material Textures"

    @classmethod
    def poll(cls, context):
        selected = context.selected_objects
        meshes = all(obj.type == 'MESH' for obj in selected)
        return meshes

    def find_image_nodes_recursive(self, node, visited=None):
        """Recursively trace backwards from a node to find Image Texture nodes"""
        if visited is None:
            visited = set()
        
        image_nodes = []
        if node in visited:
            return image_nodes
        visited.add(node)

        # If this is an Image Texture node, we found one!
        if node.type == 'TEX_IMAGE' and node.image:
            image_nodes.append(node)
        
        # Check all inputs of the current node
        for input_socket in node.inputs:
            for link in input_socket.links:
                # Trace back to the node connected to this input
                image_nodes.extend(self.find_image_nodes_recursive(link.from_node, visited))
        
        return image_nodes

    def execute(self, context):
        # 1. PATH VALIDATION
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}
        
        export_path = bpy.path.abspath(context.scene.export_path)
        textures_path = os.path.join(export_path, "textures")

        if not os.path.exists(textures_path):
            os.makedirs(textures_path)

        # 2. FIND SELECTED MESHES
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        if not meshes:
            self.report({'WARNING'}, "No meshes selected")
            return {'CANCELLED'}

        saved_count = 0
        processed_images = set()

        for obj in meshes:
            for slot in obj.material_slots:
                mat = slot.material
                if not mat or not mat.use_nodes:
                    continue

                # Find the active Material Output node
                output_node = next((n for n in mat.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None)
                
                if not output_node:
                    continue

                # Trace back from the 'Surface' input
                surface_input = output_node.inputs.get("Surface")
                if surface_input and surface_input.is_linked:
                    # Get all image nodes connected to this output
                    image_nodes = self.find_image_nodes_recursive(surface_input.links[0].from_node)
                    
                    for img_node in image_nodes:
                        img = img_node.image
                        if img and img.name not in processed_images:
                            # Determine file extension and name
                            # Use original file extension if possible, otherwise default to PNG
                            img_name = bpy.path.basename(img.filepath)
                            if not img_name:
                                img_name = f"{img.name}.png"
                            
                            target_file_path = os.path.join(textures_path, img_name)
                            
                            try:
                                # Save the image
                                img.save_render(target_file_path)
                                processed_images.add(img.name)
                                saved_count += 1
                                self.report({'INFO'}, f"Saved: {img_name}")
                            except Exception as e:
                                self.report({'ERROR'}, f"Failed to save {img.name}: {str(e)}")

        self.report({'INFO'}, f"Finished. Saved {saved_count} unique textures to /textures/")
        return {'FINISHED'}

class EXPORT_OT_vizor_npc_model_only(bpy.types.Operator):
    """Export Model and Armature in Rest Pose (No Animations)"""
    bl_idname = "export.vizor_npc_model_only"
    bl_label = "NPC Export Model (Rest)"

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT':
            return False
        selected = context.selected_objects
        has_armature = any(obj.type == 'ARMATURE' for obj in selected)
        len_meshes = sum(1 for obj in selected if obj.type == 'MESH')
        has_mesh = len_meshes > 0
        return has_armature and has_mesh and len_meshes <= MAX_ALLOWED_MESHES

    def execute(self, context):
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}
        
        export_path = bpy.path.abspath(context.scene.export_path)
        if not os.path.exists(export_path):
            os.makedirs(export_path)

        arm = next((o for o in context.selected_objects if o.type == 'ARMATURE'), None)
        meshes = [o for o in context.selected_objects if o.type == 'MESH']
        
        # Backup state
        original_active = context.view_layer.objects.active
        original_selection = context.selected_objects[:]
        original_pose_position = arm.data.pose_position

        try:
            arm.data.pose_position = 'REST'
            
            # Select only what is needed
            bpy.ops.object.select_all(action='DESELECT')
            arm.select_set(True)
            for m in meshes: m.select_set(True)
            context.view_layer.objects.active = arm
            model_name = context.scene.vizor_fbx_model_name if context.scene.vizor_fbx_model_name else arm.name

            model_path = os.path.join(export_path, f"{model_name}.fbx")

            # Using your specific vizor_fbx settings
            bpy.ops.export_scene.vizor_fbx(
                filepath=model_path,
                use_selection=True,
                object_types={'MESH', 'ARMATURE'},
                global_scale=1.0, # Adjust as per your GLOBAL_SCALE variable
                bake_anim=False, 
                armature_nodetype='REMOVE_GHOST',
                use_armature_deform_only=True,
                axis_forward='Y',
                axis_up='Z'
            )
            self.report({'INFO'}, f"Model exported to: {model_path}")

        finally:
            arm.data.pose_position = original_pose_position
            bpy.ops.object.select_all(action='DESELECT')
            for obj in original_selection:
                try: obj.select_set(True)
                except: pass
            context.view_layer.objects.active = original_active

        return {'FINISHED'}

class EXPORT_OT_vizor_npc_active_anim(bpy.types.Operator):
    """Export the currently selected (active) NLA track for the selected rig"""
    bl_idname = "export.vizor_npc_active_anim"
    bl_label = "NPC Export Active Anim"

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT':
            return False
        if len(context.selected_objects) != 1:
            return False
        obj = context.active_object
        return obj and obj.type == 'ARMATURE' and obj.animation_data and obj.animation_data.nla_tracks 

    def execute(self, context):
        if not context.scene.export_path:
            self.report({'ERROR'}, "Set export path first")
            return {'CANCELLED'}

        arm = context.active_object
        tracks = arm.animation_data.nla_tracks
        
        # Determine "Active" track. 
        # Blender uses tracks.active to refer to the selected row in the NLA UI
        active_track = tracks.active
        
        if not active_track or not active_track.strips:
            self.report({'ERROR'}, "No active NLA track with strips found")
            return {'CANCELLED'}

        export_path = bpy.path.abspath(context.scene.export_path)
        
        # Backup state
        original_pose_position = arm.data.pose_position
        original_frame_start = context.scene.frame_start
        original_frame_end = context.scene.frame_end
        original_nla_mutes = [(t, t.mute) for t in tracks]

        try:
            arm.data.pose_position = 'POSE'
            
            # Solo the active track
            for t in tracks:
                t.mute = True
            active_track.mute = False
            
            # Set frames to match strips
            start_f = min(s.frame_start for s in active_track.strips)
            end_f = max(s.frame_end for s in active_track.strips)
            context.scene.frame_start, context.scene.frame_end = int(start_f), int(end_f)
            
            # Clean filename
            safe_name = "".join([c for c in active_track.name if c.isalnum() or c in (' ', '.', '_')]).rstrip()
            anim_path = os.path.join(export_path, f"{safe_name}.fbx")

            # Selection: Armature Only
            bpy.ops.object.select_all(action='DESELECT')
            arm.select_set(True)

            bpy.ops.export_scene.vizor_fbx(
                filepath=anim_path,
                use_selection=True,
                object_types={'ARMATURE'},
                global_scale=1.0, # Adjust as per your GLOBAL_SCALE variable
                bake_anim=True,
                bake_anim_use_nla_strips=True,
                bake_anim_use_all_actions=False,
                armature_nodetype='REMOVE_GHOST',
                use_armature_deform_only=True,
                axis_forward='Y',
                axis_up='Z'
            )
            self.report({'INFO'}, f"Animation exported: {safe_name}")

        finally:
            # Restore state
            arm.data.pose_position = original_pose_position
            context.scene.frame_start = original_frame_start
            context.scene.frame_end = original_frame_end
            for track, mute_val in original_nla_mutes:
                track.mute = mute_val
            arm.select_set(True)

        return {'FINISHED'}


# -------------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------------


classes = (
    EXPORT_OT_vizor_active_nla_mesh,
    EXPORT_OT_vizor_model,
    EXPORT_OT_vizor_nla_separate,
    VIEW3D_PT_vizor_exporter_precise,
    EXPORT_OT_vizor_full_mesh_anim,
    EXPORT_OT_vizor_npc_combined,
    EXPORT_OT_vizor_npc_model_only,
    EXPORT_OT_vizor_save_textures,
    EXPORT_OT_vizor_npc_active_anim,
)

def register():
    for my_class in classes:
        bpy.utils.register_class(my_class)
    bpy.types.Scene.export_path = bpy.props.StringProperty(name="Export Path", subtype='DIR_PATH')
    bpy.types.Scene.vizor_global_scale = bpy.props.FloatProperty(
            name="Global Scale", 
            default=GLOBAL_SCALE, 
            precision=3, 
            update=update_global_scale
        )
    bpy.types.Scene.vizor_max_meshes = bpy.props.IntProperty(
                name="Max Meshes", 
                default=2, 
                update=update_max_meshes
            )
    bpy.types.Scene.vizor_fbx_model_name = bpy.props.StringProperty(
                name="FBX Model Name",
                default="Model"
            )
def unregister():
    for my_class in classes:
        bpy.utils.unregister_class(my_class)
    del bpy.types.Scene.export_path
    del bpy.types.Scene.vizor_global_scale
    del bpy.types.Scene.vizor_fbx_model_name

if __name__ == "__main__":
    register()