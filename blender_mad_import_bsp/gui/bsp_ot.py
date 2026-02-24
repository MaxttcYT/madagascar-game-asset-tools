from bpy.types import Operator
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, FloatProperty, BoolProperty 

from mad_import_bsp.bspLib import parse_file as parse_bsp_file
from mad_import_bsp.bspLib import collect_atomic_sectors

class IMPORT_OT_bsp(Operator, ImportHelper):
    bl_idname = "import_scene.bsp"
    bl_label = "Import BSP"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".bsp"
    filter_glob: StringProperty(default="*.bsp", options={'HIDDEN'}) # type: ignore

    scale: FloatProperty(
        name="Scale",
        description="Scale factor for imported geometry",
        default=3,
        min=0.000001,
        max=1000.0,
    ) # type: ignore

    center_geometry: BoolProperty(
        name="Center Geometry",
        description="Move all geometry to be centered at the origin",
        default=True,
    ) # type: ignore

    cluster_distance: FloatProperty(
        name="Cluster Distance",
        description="Sectors farther apart than this are imported as separate meshes (0 = single mesh)",
        default=10000.0,
        min=0.0,
        max=100000000.0,
    ) # type: ignore

    distribute_zones: BoolProperty(
        name="Distribute Zones",
        description="Arrange zones in a circle around the origin for easy viewing",
        default=False,
    ) # type: ignore

    distribute_radius: FloatProperty(
        name="Distribution Radius",
        description="Radius of the circle for zone distribution",
        default=1000.0,
        min=0.0,
        max=100000.0,
    ) # type: ignore

    texture_prefix: StringProperty(
        name="Texture Prefix",
        description="Path prefix for textures relative to BSP location (e.g., 'textures/' or '../shared/')",
        default="",
    ) # type: ignore

    def execute(self, context):
        import os

        if os.path.isdir(self.filepath):
            self.report({'ERROR'}, "Selected path is a folder, please select a BSP file.")
            return {'CANCELLED'}

        self.import_bsp(context, self.filepath, self.scale, self.center_geometry,
                        self.cluster_distance, self.distribute_zones, self.distribute_radius,
                        self.texture_prefix)
        return {'FINISHED'}

    def import_bsp(self, context, filepath, scale=0.01, center_geometry=True,
                   cluster_distance=10000.0, distribute_zones=False, distribute_radius=1000.0,
                   texture_prefix=""):
        import bpy
        import math
        import random
        import os

        parsed_bsp = parse_bsp_file(filepath)
        sectors = collect_atomic_sectors(parsed_bsp.get("worldChunk", []))
        if not sectors:
            print("No geometry found in BSP")
            self.report({'ERROR'}, "No geometry found in BSP")
            return {'CANCELLED'}

        # Get materials from BSP
        materials = parsed_bsp.get("materialList", {}).get("materials", [])
        mat_suffix = str(random.randint(1000, 9999))
        bsp_name = os.path.splitext(os.path.basename(filepath))[0]
        bsp_dir = os.path.dirname(filepath)

        # Create Blender materials
        blender_materials = []
        for i, mat in enumerate(materials):
            mat_name = f"{bsp_name}_mat_{i}_{mat_suffix}"
            bl_mat = bpy.data.materials.new(name=mat_name)
            bl_mat.use_nodes = True

            # Get the principled BSDF node
            nodes = bl_mat.node_tree.nodes
            links = bl_mat.node_tree.links
            bsdf = nodes.get("Principled BSDF")

            if bsdf:
                # Set color
                color = mat.get("color", {})
                r = color.get("r", 255) / 255.0
                g = color.get("g", 255) / 255.0
                b = color.get("b", 255) / 255.0
                a = color.get("a", 255) / 255.0
                bsdf.inputs["Base Color"].default_value = (r, g, b, 1.0)

                # Set specular/roughness
                specular = mat.get("specular", 0.0)
                bsdf.inputs["Roughness"].default_value = 1.0 - specular

                # Handle alpha
                if a < 1.0:
                    bl_mat.blend_method = 'BLEND'
                    bsdf.inputs["Alpha"].default_value = a

                # Handle texture
                if mat.get("isTextured") and mat.get("texture"):
                    tex_name = mat["texture"].get("diffuseTextureName", "")
                    if tex_name:
                        # Create image texture node (always, even if file missing)
                        tex_node = nodes.new(type="ShaderNodeTexImage")
                        tex_node.location = (-300, 300)
                        tex_node.label = tex_name
                        tex_node.interpolation = 'Closest'

                        # Connect to Base Color
                        links.new(tex_node.outputs["Color"], bsdf.inputs["Base Color"])
                        links.new(tex_node.outputs["Alpha"], bsdf.inputs["Alpha"])

                        # Load texture file (let Blender handle missing files)
                        tex_path = os.path.join(bsp_dir, texture_prefix, f"{tex_name}.png")
                        try:
                            image = bpy.data.images.load(tex_path, check_existing=True)
                        except Exception:
                            # Create placeholder image with filepath set
                            image = bpy.data.images.new(name=tex_name, width=1, height=1)
                            image.filepath = tex_path
                            image.source = 'FILE'
                        tex_node.image = image
                        if image.channels == 4:
                            bl_mat.blend_method = 'BLEND'

            blender_materials.append(bl_mat)

        # Step 1: Merge ALL geometry into single lists
        all_verts = []  # (x, y, z) raw coordinates
        all_faces = []  # (v1, v2, v3) indices into all_verts
        all_face_materials = []  # material index per face
        all_uvs = []    # (u, v) per vertex
        vertex_offset = 0

        for sector in sectors:
            if sector.get("isNativeData"):
                continue
            vertices = sector.get("vertices", [])
            uvs = sector.get("uvs", [])
            triangles = sector.get("triangles", [])
            mat_base = sector.get("matListWindowBase", 0)
            if not vertices:
                continue

            for i, v in enumerate(vertices):
                all_verts.append((v["x"], v["y"], v["z"]))
                if uvs and i < len(uvs):
                    all_uvs.append((uvs[i]["u"], 1.0 - uvs[i]["v"]))
                else:
                    all_uvs.append((0, 0))

            for tri in triangles:
                all_faces.append((
                    tri["vertex1"] + vertex_offset,
                    tri["vertex2"] + vertex_offset,
                    tri["vertex3"] + vertex_offset,
                ))
                # Calculate actual material index
                mat_idx = mat_base + tri.get("materialIndex", 0)
                all_face_materials.append(mat_idx)
            vertex_offset += len(vertices)

        if not all_faces:
            self.report({'ERROR'}, "No geometry found")
            return {'CANCELLED'}

        # Step 2: Find connected components of faces using union-find on vertices
        n_verts = len(all_verts)
        parent = list(range(n_verts))

        def find(x):
            root = x
            while parent[root] != root:
                root = parent[root]
            # Path compression
            while parent[x] != root:
                next_x = parent[x]
                parent[x] = root
                x = next_x
            return root

        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        # Connect vertices that share a face
        for face in all_faces:
            union(face[0], face[1])
            union(face[1], face[2])

        # Step 3: Group faces by their connected component
        component_faces = {}  # root -> list of face indices
        for face_idx, face in enumerate(all_faces):
            root = find(face[0])
            if root not in component_faces:
                component_faces[root] = []
            component_faces[root].append(face_idx)

        # Step 4: Calculate bounding box for each component
        components = []
        for root, face_indices in component_faces.items():
            # Get all vertices in this component
            vert_indices = set()
            for fi in face_indices:
                vert_indices.update(all_faces[fi])

            xs = [all_verts[vi][0] for vi in vert_indices]
            ys = [all_verts[vi][1] for vi in vert_indices]
            zs = [all_verts[vi][2] for vi in vert_indices]

            components.append({
                "face_indices": face_indices,
                "vert_indices": vert_indices,
                "bbox": (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)),
            })

        # Step 5: Cluster components by bounding box distance
        n_comp = len(components)
        comp_parent = list(range(n_comp))

        def find_comp(x):
            root = x
            while comp_parent[root] != root:
                root = comp_parent[root]
            # Path compression
            while comp_parent[x] != root:
                next_x = comp_parent[x]
                comp_parent[x] = root
                x = next_x
            return root

        def union_comp(x, y):
            px, py = find_comp(x), find_comp(y)
            if px != py:
                comp_parent[px] = py

        def bbox_distance(b1, b2):
            def axis_dist(min1, max1, min2, max2):
                if max1 < min2:
                    return min2 - max1
                elif max2 < min1:
                    return min1 - max2
                return 0
            dx = axis_dist(b1[0], b1[1], b2[0], b2[1])
            dy = axis_dist(b1[2], b1[3], b2[2], b2[3])
            dz = axis_dist(b1[4], b1[5], b2[4], b2[5])
            return (dx*dx + dy*dy + dz*dz) ** 0.5

        if cluster_distance > 0:
            for i in range(n_comp):
                for j in range(i + 1, n_comp):
                    dist = bbox_distance(components[i]["bbox"], components[j]["bbox"])
                    if dist <= cluster_distance:
                        union_comp(i, j)

        # Step 6: Group components into final zones
        zones = {}
        for i in range(n_comp):
            root = find_comp(i)
            if root not in zones:
                zones[root] = []
            zones[root].append(components[i])

        # Create parent empty
        world_parent = bpy.data.objects.new(bsp_name, None)
        context.collection.objects.link(world_parent)
        # Rotate 90 degrees on X axis (convert from Z-up to Y-up coordinate system)
        world_parent.rotation_euler[0] = math.radians(90)

        # Step 7: Create mesh for each zone
        n_zones = len(zones)
        for zone_idx, zone_components in enumerate(zones.values()):
            # Collect all vertex indices and face indices for this zone
            zone_vert_indices = set()
            zone_face_indices = []
            for comp in zone_components:
                zone_vert_indices.update(comp["vert_indices"])
                zone_face_indices.extend(comp["face_indices"])

            # Calculate center offset for this zone
            center_offset = (0, 0, 0)
            if center_geometry:
                xs = [all_verts[vi][0] for vi in zone_vert_indices]
                ys = [all_verts[vi][1] for vi in zone_vert_indices]
                zs = [all_verts[vi][2] for vi in zone_vert_indices]
                center_offset = (
                    (min(xs) + max(xs)) / 2,
                    (min(ys) + max(ys)) / 2,
                    (min(zs) + max(zs)) / 2,
                )

            # Remap vertex indices to new local indices
            old_to_new = {}
            zone_verts = []
            zone_uvs = []
            for old_idx in sorted(zone_vert_indices):
                old_to_new[old_idx] = len(zone_verts)
                v = all_verts[old_idx]
                zone_verts.append((
                    (v[0] - center_offset[0]) * scale,
                    (v[1] - center_offset[1]) * scale,
                    (v[2] - center_offset[2]) * scale,
                ))
                zone_uvs.append(all_uvs[old_idx])

            # Remap faces and collect material indices
            zone_faces = []
            zone_face_mats = []
            for fi in zone_face_indices:
                face = all_faces[fi]
                zone_faces.append((
                    old_to_new[face[0]],
                    old_to_new[face[1]],
                    old_to_new[face[2]],
                ))
                zone_face_mats.append(all_face_materials[fi])

            # Create mesh
            mesh = bpy.data.meshes.new(f"Zone_{zone_idx}_Mesh")
            obj = bpy.data.objects.new(f"Zone_{zone_idx}", mesh)
            context.collection.objects.link(obj)

            mesh.from_pydata(zone_verts, [], zone_faces)
            mesh.update()

            # Add materials to mesh and assign to faces
            # First, find which materials are used in this zone
            used_mats = sorted(set(zone_face_mats))
            mat_to_slot = {}  # maps global mat index -> slot index in this mesh

            for mat_idx in used_mats:
                if mat_idx < len(blender_materials):
                    slot_idx = len(obj.data.materials)
                    obj.data.materials.append(blender_materials[mat_idx])
                    mat_to_slot[mat_idx] = slot_idx

            # Assign materials to faces
            for face_idx, mat_idx in enumerate(zone_face_mats):
                if mat_idx in mat_to_slot:
                    mesh.polygons[face_idx].material_index = mat_to_slot[mat_idx]

            # Apply UVs
            if zone_uvs:
                uv_layer = mesh.uv_layers.new(name="UVMap")
                for face_idx, face in enumerate(zone_faces):
                    for loop_idx, vert_idx in enumerate(face):
                        if vert_idx < len(zone_uvs):
                            uv_layer.data[face_idx * 3 + loop_idx].uv = zone_uvs[vert_idx]

            obj.parent = world_parent

            # Position zone on circle if distribution is enabled
            if distribute_zones and n_zones > 1:
                angle = (2 * math.pi * zone_idx) / n_zones
                obj.location = (
                    math.cos(angle) * distribute_radius,
                    math.sin(angle) * distribute_radius,
                    0,
                )

        world_parent.select_set(True)
        context.view_layer.objects.active = world_parent

        self.report({'INFO'}, f"Imported {len(zones)} zone(s) from {len(components)} connected components")
        return {'FINISHED'}
