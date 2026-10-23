import bpy


def _is_deform_bone(bone):
	"""Return whether a bone is explicitly part of the deform skeleton."""
	return bone.name.startswith("DEF-") or bone.use_deform


def _floating_bones(armature_object):
	"""Return the unique top-level roots reached by deform bones."""
	bones = list(armature_object.data.bones)
	deform_bones = [bone for bone in bones if _is_deform_bone(bone)]
	roots = set()

	def find_root(bone):
		current = bone
		while current.parent is not None:
			current = current.parent
		return current

	for bone in deform_bones:
		roots.add(find_root(bone))

	return roots


class ARMATURE_OT_check_deform_connections(bpy.types.Operator):
	"""Check that selected armatures have one connected deform hierarchy."""

	bl_idname = "armature.check_deform_connections"
	bl_label = "Check Deform Bone Connections"
	bl_description = "Check selected armatures for floating deform bones and multiple roots"
	bl_options = {'REGISTER'}

	@classmethod
	def poll(cls, context):
		return any(obj.type == 'ARMATURE' for obj in context.selected_objects)

	def execute(self, context):
		armatures = [obj for obj in context.selected_objects if obj.type == 'ARMATURE']
		invalid_armatures = 0

		for armature in armatures:
			roots = _floating_bones(armature)
			root_count = len(roots)
			if root_count != 1:
				invalid_armatures += 1
				root_names = sorted(root.name for root in roots)
				print(
					f"{armature.name} root bones ({root_count}): "
					f"{', '.join(root_names)}"
				)
				self.report(
					{'WARNING'},
					f"{armature.name}: found {root_count} root bones, "
					"root names printed to console",
				)


		if invalid_armatures:
			self.report({'WARNING'}, f"Found connection issues in {invalid_armatures} armature check(s)")
		else:
			self.report({'INFO'}, "All selected armatures have one connected deform hierarchy")

		return {'FINISHED'}


class VIEW3D_PT_armature_check_tools(bpy.types.Panel):
	bl_space_type = 'VIEW_3D'
	bl_region_type = 'UI'
	bl_category = 'Batch Export'
	bl_label = 'Armature Checks'

	def draw(self, context):
		self.layout.operator(
			ARMATURE_OT_check_deform_connections.bl_idname,
			text='Check Deform Bone Connections',
			icon='ARMATURE_DATA',
		)


classes = (
	ARMATURE_OT_check_deform_connections,
	VIEW3D_PT_armature_check_tools,
)


def register():
	for cls in classes:
		bpy.utils.register_class(cls)


def unregister():
	for cls in reversed(classes):
		bpy.utils.unregister_class(cls)
