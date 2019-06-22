#====================== BEGIN GPL LICENSE BLOCK ======================
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#======================= END GPL LICENSE BLOCK ========================

# <pep8 compliant>
bl_info = {
    "name": "Blender PyMesh Utils",
    "author": "Raffaele Di Blasi",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "Tool Shelf",
    "description": "Interface to use PyMesh library for advanced operations",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
    "category": "3D View"}


if "bpy" in locals():
    import importlib
    #importlib.reload(ui)
    #importlib.reload(operators)
    #importlib.reload(mesh_helpers)
else:
    import bpy

    from bpy.props import (
            BoolProperty,
            EnumProperty,
            FloatProperty,
            IntProperty,
            StringProperty,
            PointerProperty,
            CollectionProperty,
            )

    from bpy.types import (
            Operator,
            Panel,
            PropertyGroup,
            AddonPreferences,
            )

    import math

    import pymesh
    import numpy
    import mathutils

# Props

class PyMesh_Scene_Props(PropertyGroup):
    boolean_library: EnumProperty(
        name="Format",
        description="Format type to export to",
        items=(
            ('igl', "IGL", ""),
            ('cgal', "CGAL", ""),
            ('carve', "Carve", ""),
            ('cork', "Cork", ""),
            ('corefinement', "Corefinement", ""),
            ('bsp', "BSP", ""),
            #('clipper', "Clipper (2D)", ""),
        ),
        default='carve',
    )
    '''
    boolean_operation: EnumProperty(
        name="Boolean Operation",
        description="Type of boolean operation",
        items=(
            ('union', "Union", ""),
            ('difference', "Difference", ""),
            ('intersection', "Intersection", ""),
            #('symmetric_difference', "Symmetric Difference", ""),
        ),
        default='union',
    )
    '''
    add_to_collection: BoolProperty(
        name="Add to Collection",
        description="Add original objects to a separate collection",
        default=True,
    )
    delete_orig: BoolProperty(
        name="Delete",
        description="Delete original objects",
        default=False,
    )
    hide_orig: BoolProperty(
        name="Hide",
        description="Hide original objects",
        default=True,
    )
# ############################################################
# User Interface
# ############################################################

class PyMesh_Panel(Panel):
    bl_label = "PyMesh Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'PyMesh'

    boolean_operations = [
        ('union',           "Union",        ""),
        ('difference',      "Difference",   ""),
        ('intersection',    "Intersection", ""),
        #('symmetric_difference', "Symmetric Difference", ""),
    ]


    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        
        scene = context.scene
        pymesh_props = scene.pymesh

        #row = layout.row()
        #row.label(text="Objects:")
        #rowsub = layout.row(align=True)
        #rowsub.operator("mesh.print3d_info_volume", text="Volume")
        #rowsub.operator("mesh.print3d_info_area", text="Area")

        col = layout.column(align=True)
        col.label(text="Boolean Tools:")
        col.separator()
        
        col.label(text="Library:")
        col.prop(pymesh_props, "boolean_library", text="")
        col.separator()

        col.label(text="Original Objects Options:")
        if not pymesh_props.delete_orig:
            col.prop(pymesh_props, "add_to_collection", text="Add to Collection")
            col.prop(pymesh_props, "hide_orig", text="Hide")
        col.prop(pymesh_props, "delete_orig", text="Delete")

        #col.label(text="Operation:")
        #col.prop(pymesh_props, "boolean_operation", text="")

        #if len(context.selected_objects) == 2 and pymesh_props.boolean_operation == 'difference':
        if len(context.selected_objects) == 2:
            obj_a = context.active_object
            obj_b = context.selected_objects[0] if context.selected_objects[0] != obj_a else context.selected_objects[1]
            if obj_a and obj_a.type == 'MESH' and obj_b and obj_b.type == 'MESH':
                row = layout.row(align=True)
                row.label(text="M: " + obj_a.name)
                row.separator()
                #col.label(text="Op: "+ obj_b.name)
                row.operator("view3d.invert_selection", text="Invert")

                col = layout.column(align=True)
                for o in self.boolean_operations:
                    col.operator("view3d.pymesh_exec", text=o[1], icon='MOD_BOOLEAN').operation=o[0]

        if len(context.selected_objects) == 1:
            obj_a = context.active_object
            if obj_a and obj_a.type == 'MESH':
                col = layout.column(align=True)
                col.separator()
                col.label(text="PyMesh Tools:")
                #col.separator()
                #col.operator("view3d.pymesh_resolve_self_intersection", text="Resolve Self-Intersections")
                col.operator("view3d.pymesh_remesh", text="Remesh")
                col.operator("view3d.compute_outer_hull", text="Compute Outer Hull")
                col.operator("view3d.convex_hull", text="Compute Convex Hull")
                #col.operator("view3d.pymesh_testing", text="Test")
        #col.operator("view3d.carve_mesh_help", text="", icon='QUESTION', emboss=False).show_help = True


# ############################################################
# Operators
# ############################################################
def enum_members_from_type(rna_type, prop_str):
    prop = rna_type.bl_rna.properties[prop_str]
    return [e.identifier for e in prop.enum_items]

def enum_members_from_instance(rna_item, prop_str):
    return enum_members_from_type(type(rna_item), prop_str)

def import_object(context, obj):
    APPLY_MODIFIERS = True
    global_matrix = mathutils.Matrix()
    depsgraph = context.evaluated_depsgraph_get()
    tmesh = obj.evaluated_get(depsgraph).to_mesh()
    tmesh.transform(global_matrix @ obj.matrix_world)
    tmesh.calc_loop_triangles()
    vertices = []
    faces = []
    for n, v in enumerate(tmesh.vertices):
        vertices.append(v.co[:])
    for n, f in enumerate(tmesh.loop_triangles):
        faces.append(f.vertices[:])
    return pymesh.form_mesh(numpy.array(vertices), numpy.array(faces))

def export_mesh(context, mesh, off_name):
    result = bpy.data.meshes.new(name=off_name)
    #edges = []
    #for f in mesh.faces:
    #    edges.append((f[0], f[1]))
    #    edges.append((f[1], f[2]))
    #    edges.append((f[2], f[0]))
    result.from_pydata(mesh.vertices.tolist(), [], mesh.faces.tolist())
    result.validate()
    result.update()
    return result

def boolean_operation(context, obj_a, obj_b, library, operation):
    mesh_a = import_object(context, obj_a)
    mesh_b = import_object(context, obj_b)
    #add_to_scene(context, export_mesh(context, mesh_a))
    #add_to_scene(context, export_mesh(context, mesh_b))
    try:
        pymesh_r = pymesh.boolean(mesh_a, mesh_b, operation=operation, engine=library)
    except:
        return None
    off_name="Py.Bool."+operation+"."+library
    mesh_r = export_mesh(context, pymesh_r, off_name)
    return add_to_scene(context, mesh_r)

def add_to_scene(context, mesh):
    scene = context.scene
    pymesh_props = scene.pymesh

    if pymesh_props.delete_orig:
        bpy.ops.object.delete()

    else:
        for obj in context.selected_objects:
            if pymesh_props.add_to_collection:
                for user_col in obj.users_collection:
                    if user_col.name[:4] == "Orig":
                        continue
                    new_col = None
                    for child in user_col.children:
                        if child.name[:4] == "Orig":
                            new_col = child
                            break
                    if not new_col:
                        new_col = bpy.data.collections.new('Orig')
                        context.collection.children.link(new_col)
                    new_col.objects.link(obj)
                    user_col.objects.unlink(obj)

            if pymesh_props.hide_orig:
                obj.hide_set(True)
                # obj.hide_render = True
            obj.select_set(False)

    obj = bpy.data.objects.new(mesh.name, mesh)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj
    obj.select_set(True)
    context.view_layer.update()
    return obj

def check_errors(objects):
    if len(objects) != 2:
       raise NumberSelectionException

    for obj in objects:
       if obj.type != 'MESH':
          raise NonMeshSelectedException(obj)

def fix_mesh(mesh, detail="normal"):
    bbox_min, bbox_max = mesh.bbox;
    diag_len = numpy.linalg.norm(bbox_max - bbox_min);
    if detail == "normal":
        target_len = diag_len * 5e-3;
    elif detail == "high":
        target_len = diag_len * 2.5e-3;
    elif detail == "low":
        target_len = diag_len * 1e-2;
    print("Target resolution: {} mm".format(target_len));

    count = 0;
    mesh, __ = pymesh.remove_degenerated_triangles(mesh, 100);
    mesh, __ = pymesh.split_long_edges(mesh, target_len);
    num_vertices = mesh.num_vertices;
    while True:
        mesh, __ = pymesh.collapse_short_edges(mesh, 1e-6);
        mesh, __ = pymesh.collapse_short_edges(mesh, target_len,
                preserve_feature=True);
        mesh, __ = pymesh.remove_obtuse_triangles(mesh, 150.0, 100);
        if mesh.num_vertices == num_vertices:
            break;

        num_vertices = mesh.num_vertices;
        print("#v: {}".format(num_vertices));
        count += 1;
        if count > 10: break;

    mesh = pymesh.resolve_self_intersection(mesh);
    mesh, __ = pymesh.remove_duplicated_faces(mesh);
    mesh = pymesh.compute_outer_hull(mesh);
    mesh, __ = pymesh.remove_duplicated_faces(mesh);
    mesh, __ = pymesh.remove_obtuse_triangles(mesh, 179.0, 5);
    mesh, __ = pymesh.remove_isolated_vertices(mesh);

    return mesh;

def help_draw(_self, context):
    layout = _self.layout
    col = layout.column()

    col.label(text="This operator works from the selected to the active objects")
    col.label(text="The active must be a single plane")

    col.separator()
    col.label(text="Union")
    col.label(text="Compute the Boolean union of in0 and in1, and output the result")

    col.separator()
    col.label(text="Difference")
    col.label(text="Compute the Boolean difference of in0 and in1, and output the result")

    col.separator()
    col.label(text="Intersect")
    col.label(text="Compute the Boolean intersection of in0 and in1, and output the result")

    col.separator()
    col.label(text="XOR")
    col.label(text="Compute the Boolean XOR of in0 and in1, and output the result")

    col.separator()
    col.label(text="Resolve")
    col.label(text="Intersect the two meshes in0 and in1, and output the connected mesh with those")
    col.label(text="intersections made explicit and connected")

class PYMESH_OT_Boolean_Operation(Operator):
    """PyMesh boolean operation"""
    bl_idname = "view3d.pymesh_exec"
    bl_label = "PyMesh boolean execute"

    ev = []
    operation = StringProperty(default="union")

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) == 2

    def invoke(self, context, event):
        self.ev = []
        if event.ctrl:
            self.ev.append("Ctrl")
        if event.shift:
            self.ev.append("Shift")
        if event.alt:
            self.ev.append("Alt")
        if event.oskey:
            self.ev.append("OS")
        return self.execute(context)

    def execute(self, context):
        try:
            check_errors(context.selected_objects)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        obj_b = context.selected_objects[0] if context.selected_objects[0] != obj_a else context.selected_objects[1]
        library = pymesh_props.boolean_library
        #operation = pymesh_props.boolean_operation
        operation = self.operation

        # TESTING MOD
        if "Ctrl" in self.ev:
            libs = enum_members_from_instance(pymesh_props, "boolean_library")
            coords = 0
            for l in libs:
                obj = boolean_operation(context, obj_a, obj_b, l, operation)
                coords = coords + 2
                if obj:
                    obj.location.x = coords
            return {'FINISHED'}

        if boolean_operation(context, obj_a, obj_b, library, operation):
            return {'FINISHED'}
        self.report({'ERROR'}, "Boolean Operation Failed")
        return {'CANCELLED'}

class PYMESH_OT_Invert_Selection(Operator):
    """PyMesh invert selection"""
    bl_idname = "view3d.invert_selection"
    bl_label = "PyMesh invert selection"

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) == 2

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        obj_b = context.selected_objects[0] if context.selected_objects[0] != obj_a else context.selected_objects[1]

        context.view_layer.objects.active = obj_b
        return {'FINISHED'}

class PYMESH_OT_Resolve_Self_Intersection(Operator):
    """PyMesh resolve self intersection"""
    bl_idname = "view3d.pymesh_resolve_self_intersection"
    bl_label = "PyMesh resolve self intersection"

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        mesh_a = import_object(context, obj_a)
        pymesh_si = pymesh.detect_self_intersection(mesh_a)
        if pymesh_si.size == 0:
            self.report({'ERROR'}, "This mesh has no self-intersections")
            return {'CANCELLED'}
        pymesh_r = pymesh.resolve_self_intersection(mesh_a)
        off_name="Py.SI."+obj_a.name
        mesh_r = export_mesh(context, pymesh_r, off_name)
        add_to_scene(context, mesh_r)

        return {'FINISHED'}

class PYMESH_OT_Testing(Operator):
    """PyMesh testing"""
    bl_idname = "view3d.pymesh_testing"
    bl_label = "PyMesh testing"

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        mesh_a = import_object(context, obj_a)
        pymesh_r = fix_mesh(mesh_a)
        off_name="Py.Test."+obj_a.name
        mesh_r = export_mesh(context, pymesh_r, off_name)
        add_to_scene(context, mesh_r)

        return {'FINISHED'}

class PYMESH_OT_Compute_Outer_Hull(Operator):
    """PyMesh compute_outer_hull"""
    bl_idname = "view3d.compute_outer_hull"
    bl_label = "PyMesh compute_outer_hull"

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        mesh_a = import_object(context, obj_a)
        pymesh_r = pymesh.compute_outer_hull(mesh_a)
        off_name="Py.OH."+obj_a.name
        mesh_r = export_mesh(context, pymesh_r, off_name)
        add_to_scene(context, mesh_r)

        return {'FINISHED'}

class PYMESH_OT_Convex_Hull(Operator):
    """PyMesh convex_hull"""
    bl_idname = "view3d.convex_hull"
    bl_label = "PyMesh convex_hull"

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        mesh_a = import_object(context, obj_a)
        pymesh_r = pymesh.convex_hull(mesh_a)
        off_name="Py.CU."+obj_a.name
        mesh_r = export_mesh(context, pymesh_r, off_name)
        add_to_scene(context, mesh_r)

        return {'FINISHED'}

class PYMESH_OT_Remesh(Operator):
    """PyMesh Remesh"""
    bl_idname = "view3d.pymesh_remesh"
    bl_label = "PyMesh mesh remesh"

    def execute(self, context):
        scene = context.scene
        pymesh_props = scene.pymesh

        obj_a = context.active_object
        mesh_a = import_object(context, obj_a)
        pymesh_r, info = pymesh.remove_degenerated_triangles(mesh_a)
        pymesh_r, info = pymesh.remove_obtuse_triangles(pymesh_r)
        pymesh_r, info = pymesh.remove_duplicated_faces(pymesh_r)
        pymesh_r, info = pymesh.collapse_short_edges(pymesh_r)
        pymesh_r, info = pymesh.remove_duplicated_vertices(pymesh_r)
        pymesh_r, info = pymesh.remove_isolated_vertices(pymesh_r)
        off_name="Py.Clean."+obj_a.name
        mesh_r = export_mesh(context, pymesh_r, off_name)
        add_to_scene(context, mesh_r)

        return {'FINISHED'}


class PyMeshHelp(Operator):
    """Carve boolean help operation"""
    bl_idname = "view3d.carve_mesh_help"
    bl_label = "cork boolean help"

    show_help: BoolProperty(
            name="Help",
            description="",
            default=False,
            options={'HIDDEN', 'SKIP_SAVE'},
            )

    def execute(self, context):
        if self.show_help:
            context.window_manager.popup_menu(help_draw, title='Help', icon='QUESTION')
            return {'CANCELLED'}

# ############################################################
# Registration
# ############################################################

classes = ( PyMesh_Panel,
            PYMESH_OT_Invert_Selection,
            PYMESH_OT_Boolean_Operation,
            PYMESH_OT_Resolve_Self_Intersection,
            PYMESH_OT_Compute_Outer_Hull,
            PYMESH_OT_Convex_Hull,
            PYMESH_OT_Remesh,
            PYMESH_OT_Testing,
            PyMeshHelp,
            PyMesh_Scene_Props,
            )

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.pymesh = PointerProperty(type=PyMesh_Scene_Props)


def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.pymesh


if __name__ == '__main__':
    register()
