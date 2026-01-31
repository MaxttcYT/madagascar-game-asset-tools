#!/usr/bin/env python3

import struct
import sys
import json
from typing import Any, Dict, Optional
import random

class BinaryReader:
    """Helper class to read binary data with offset tracking."""

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def read_uint8(self) -> int:
        val = struct.unpack_from("<B", self.data, self.offset)[0]
        self.offset += 1
        return val

    def read_int8(self) -> int:
        val = struct.unpack_from("<b", self.data, self.offset)[0]
        self.offset += 1
        return val

    def read_uint16(self) -> int:
        val = struct.unpack_from("<H", self.data, self.offset)[0]
        self.offset += 2
        return val

    def read_int16(self) -> int:
        val = struct.unpack_from("<h", self.data, self.offset)[0]
        self.offset += 2
        return val

    def read_uint32(self) -> int:
        val = struct.unpack_from("<I", self.data, self.offset)[0]
        self.offset += 4
        return val

    def read_int32(self) -> int:
        val = struct.unpack_from("<i", self.data, self.offset)[0]
        self.offset += 4
        return val

    def read_uint64(self) -> int:
        val = struct.unpack_from("<Q", self.data, self.offset)[0]
        self.offset += 8
        return val

    def read_int64(self) -> int:
        val = struct.unpack_from("<q", self.data, self.offset)[0]
        self.offset += 8
        return val

    def read_float32(self) -> float:
        val = struct.unpack_from("<f", self.data, self.offset)[0]
        self.offset += 4
        return val

    def read_float64(self) -> float:
        val = struct.unpack_from("<d", self.data, self.offset)[0]
        self.offset += 8
        return val

    def read_color32(self) -> Dict[str, int]:
        r = self.read_uint8()
        g = self.read_uint8()
        b = self.read_uint8()
        a = self.read_uint8()
        return {"r": r, "g": g, "b": b, "a": a}

    def read_bytes(self, count: int) -> bytes:
        val = self.data[self.offset : self.offset + count]
        self.offset += count
        return val

    def read_string(self, size: int) -> str:
        raw = self.read_bytes(size)
        null_idx = raw.find(b"\x00")
        if null_idx >= 0:
            raw = raw[:null_idx]
        return raw.decode("ascii", errors="replace")


def parse_section_header(reader: BinaryReader) -> Dict[str, int]:
    """Parse a standard RW section header."""
    return {
        "identifier": reader.read_uint32(),
        "size": reader.read_int32(),
        "version": reader.read_int32(),
    }


def parse_texture(reader: BinaryReader) -> Dict[str, Any]:
    """Parse a Texture section (0x0006)."""
    texture = {}

    # Texture Header
    header = parse_section_header(reader)
    texture["header"] = header

    # TextureStruct Header
    struct_header = parse_section_header(reader)
    texture["structHeader"] = struct_header

    # TextureStruct Data
    texture["filterMode"] = reader.read_uint8()
    texture["addressModes"] = reader.read_uint8()
    texture["useMipLevels"] = reader.read_uint16()

    # Diffuse Texture Name (0x0002)
    diffuse_header = parse_section_header(reader)
    texture["diffuseNameHeader"] = diffuse_header
    texture["diffuseTextureName"] = reader.read_string(diffuse_header["size"])

    # Alpha Texture Name (0x0002)
    alpha_header = parse_section_header(reader)
    texture["alphaNameHeader"] = alpha_header
    texture["alphaTextureName"] = reader.read_string(alpha_header["size"])

    # Texture Extension Header
    tex_ext_header = parse_section_header(reader)
    texture["extensionHeader"] = tex_ext_header
    texture["extensionData"] = reader.read_bytes(tex_ext_header["size"]).hex()

    return texture


def parse_material(reader: BinaryReader) -> Dict[str, Any]:
    """Parse a Material section (0x0007)."""
    material = {}

    # Material Header
    header = parse_section_header(reader)
    material["header"] = header

    # MaterialStruct Header
    struct_header = parse_section_header(reader)
    material["structHeader"] = struct_header

    # MaterialStruct Data
    material["unusedFlags"] = reader.read_int32()
    material["color"] = reader.read_color32()
    material["unusedInt2"] = reader.read_int32()
    material["isTextured"] = reader.read_int32()
    material["ambient"] = reader.read_float32()
    material["specular"] = reader.read_float32()
    material["diffuse"] = reader.read_float32()

    # Texture (if textured)
    if material["isTextured"] != 0:
        material["texture"] = parse_texture(reader)

    # Material Extension Header
    ext_header = parse_section_header(reader)
    material["extensionHeader"] = ext_header
    material["extensionData"] = reader.read_bytes(ext_header["size"]).hex()

    return material


def parse_material_list(reader: BinaryReader) -> Dict[str, Any]:
    """Parse a MaterialList section (0x0008)."""
    mat_list = {}

    # MaterialList Header
    header = parse_section_header(reader)
    mat_list["header"] = header

    # MaterialListStruct Header
    struct_header = parse_section_header(reader)
    mat_list["structHeader"] = struct_header

    # MaterialListStruct Data
    material_count = reader.read_int32()
    mat_list["materialCount"] = material_count
    mat_list["materialIndices"] = [reader.read_int32() for _ in range(material_count)]

    # Materials
    mat_list["materials"] = [parse_material(reader) for _ in range(material_count)]

    return mat_list


def parse_atomic_sector(
    reader: BinaryReader, is_collision: bool = False,
) -> Dict[str, Any]:
    """Parse an AtomicSector section (0x0009)."""
    atomic = {}

    # AtomicSector Header (identifier already read by caller)
    atomic["size"] = reader.read_int32()
    atomic["version"] = reader.read_int32()

    # AtomicSectorStruct Header
    struct_header = parse_section_header(reader)
    atomic["structHeader"] = struct_header
    struct_size = struct_header["size"]
    start_struct_position = reader.offset

    # AtomicSectorStruct Data
    atomic["matListWindowBase"] = reader.read_int32()
    num_triangles = reader.read_int32()
    num_vertices = reader.read_int32()
    atomic["numTriangles"] = num_triangles
    atomic["numVertices"] = num_vertices
    atomic["boxMax"] = {
        "x": reader.read_float32(),
        "y": reader.read_float32(),
        "z": reader.read_float32(),
    }
    atomic["boxMin"] = {
        "x": reader.read_float32(),
        "y": reader.read_float32(),
        "z": reader.read_float32(),
    }
    atomic["collSectorPresent"] = reader.read_int32()
    atomic["unused"] = reader.read_int32()

    # Check for native data (data stored elsewhere, struct only contains header)
    header_size = 11 * 4  # 11 int32/float32 fields
    if reader.offset == start_struct_position + struct_size:
        if num_vertices != 0 and num_triangles != 0:
            atomic["isNativeData"] = True
            # Skip to extension
            ext_header = parse_section_header(reader)
            atomic["extensionHeader"] = ext_header
            atomic["extensionData"] = reader.read_bytes(ext_header["size"]).hex()
            return atomic

    atomic["isNativeData"] = False

    # Reset to after header and read vertex data
    reader.offset = start_struct_position + header_size

    # Vertex Data 
    atomic["vertices"] = [
        {
            "x": reader.read_float32(),
            "y": reader.read_float32(),
            "z": reader.read_float32(),
        }
        for _ in range(num_vertices)
    ]

    if not is_collision:
        # Check for two vertex color arrays
        # Expected size: header(44) + vertices(12*n) + colors(4*n) + uvs(8*n) + triangles(8*t)
        supposed_total_length = (
            header_size + (12 + 4 + 8) * num_vertices + 8 * num_triangles
        )
        two_vcolor_arrays = False

        extra_size = struct_size - supposed_total_length
        if extra_size == num_vertices * 4:
            two_vcolor_arrays = True
        elif extra_size == num_vertices * 12:
            two_vcolor_arrays = True

        atomic["twoColorArrays"] = two_vcolor_arrays

        # Skip first color array if there are two
        if two_vcolor_arrays:
            reader.offset += 4 * num_vertices

        # Color Data
        atomic["colors"] = [reader.read_color32() for _ in range(num_vertices)]

        # Reset position for UV data
        if two_vcolor_arrays:
            reader.offset = start_struct_position + header_size + 20 * num_vertices
        else:
            reader.offset = start_struct_position + header_size + 16 * num_vertices

        # UV Data
        atomic["uvs"] = [
            {"u": reader.read_float32(), "v": reader.read_float32()}
            for _ in range(num_vertices)
        ]
    else:
        atomic["colors"] = []
        atomic["uvs"] = []

    # Triangle data is at the end of the struct
    reader.offset = start_struct_position + struct_size - 8 * num_triangles

    # Triangle Data - order differs between shadow and heroes format
    atomic["triangles"] = [
        {
            "vertex1": reader.read_uint16(),
            "vertex2": reader.read_uint16(),
            "vertex3": reader.read_uint16(),
            "materialIndex": reader.read_uint16(),
        }
        for _ in range(num_triangles)
    ]

    # Ensure we're at the end of struct
    reader.offset = start_struct_position + struct_size

    # AtomicSector Extension Header
    ext_header = parse_section_header(reader)
    atomic["extensionHeader"] = ext_header
    atomic["extensionData"] = reader.read_bytes(ext_header["size"]).hex()

    return atomic


def parse_plane_sector(
    reader: BinaryReader, is_collision: bool = False
) -> Dict[str, Any]:
    """Parse a PlaneSector section (0x000A) recursively."""
    plane = {}

    # PlaneSector Header (identifier already read by caller)
    plane["size"] = reader.read_int32()
    plane["version"] = reader.read_int32()

    # PlaneStruct Header
    struct_header = parse_section_header(reader)
    plane["structHeader"] = struct_header

    # PlaneStruct Data
    plane["type"] = reader.read_int32()
    plane["value"] = reader.read_float32()
    left_is_atomic = reader.read_int32()
    right_is_atomic = reader.read_int32()
    plane["leftIsAtomic"] = left_is_atomic
    plane["rightIsAtomic"] = right_is_atomic
    plane["leftValue"] = reader.read_float32()
    plane["rightValue"] = reader.read_float32()

    # Left child
    left_section_id = reader.read_uint32()
    if left_is_atomic == 1:
        if left_section_id != 0x0009:
            raise ValueError(
                f"Expected AtomicSector (0x0009) for left child, got 0x{left_section_id:04X}"
            )
        plane["leftSection"] = {
            "type": "AtomicSector",
            "data": parse_atomic_sector(reader, is_collision),
        }
    else:
        if left_section_id != 0x000A:
            raise ValueError(
                f"Expected PlaneSector (0x000A) for left child, got 0x{left_section_id:04X}"
            )
        plane["leftSection"] = {
            "type": "PlaneSector",
            "data": parse_plane_sector(reader, is_collision),
        }

    # Right child
    right_section_id = reader.read_uint32()
    if right_is_atomic == 1:
        if right_section_id != 0x0009:
            raise ValueError(
                f"Expected AtomicSector (0x0009) for right child, got 0x{right_section_id:04X}"
            )
        plane["rightSection"] = {
            "type": "AtomicSector",
            "data": parse_atomic_sector(reader, is_collision),
        }
    else:
        if right_section_id != 0x000A:
            raise ValueError(
                f"Expected PlaneSector (0x000A) for right child, got 0x{right_section_id:04X}"
            )
        plane["rightSection"] = {
            "type": "PlaneSector",
            "data": parse_plane_sector(reader, is_collision),
        }

    return plane


def parse_world_chunk(
    reader: BinaryReader,
    num_atomic_sectors: int,
    num_plane_sectors: int,
    is_collision: bool = False,
) -> Optional[Dict[str, Any]]:
    """Parse the first world chunk (AtomicSector or PlaneSector)."""
    section_id = reader.read_uint32()

    if num_atomic_sectors == 1 and num_plane_sectors == 0:
        if section_id != 0x0009:
            raise ValueError(f"Expected AtomicSector (0x0009), got 0x{section_id:04X}")
        return {
            "type": "AtomicSector",
            "data": parse_atomic_sector(reader, is_collision),
        }
    elif num_plane_sectors > 0:
        if section_id != 0x000A:
            raise ValueError(f"Expected PlaneSector (0x000A), got 0x{section_id:04X}")
        return {
            "type": "PlaneSector",
            "data": parse_plane_sector(reader, is_collision),
        }

    return None


def parse(
    data: bytes, is_collision: bool = False
) -> Dict[str, Any]:
    """
    Parse binary data according to the World (0x000B) BinDef structure.

    Args:
        data: Binary data to parse
        is_collision: If True, skip color and UV data in AtomicSectors
        use triangle format v1,v2,v3,mat

    Returns:
        Dictionary containing all parsed values
    """
    reader = BinaryReader(data)
    result = {}

    # World Header (0x000B)
    result["sectionIdentifier"] = reader.read_uint32()
    if result["sectionIdentifier"] != 0x000B:
        raise ValueError(
            f"Expected World section (0x000B), got 0x{result['sectionIdentifier']:04X}"
        )
    result["sectionSize"] = reader.read_int32()
    result["renderWareVersion"] = reader.read_int32()

    # WorldStruct Header (0x0001)
    result["worldStructIdentifier"] = reader.read_uint32()
    world_struct_size = reader.read_int32()
    result["worldStructSize"] = world_struct_size
    result["worldStructVersion"] = reader.read_int32()

    # WorldStruct Data (varies based on size)
    result["rootIsWorldSector"] = reader.read_int32()
    result["inverseOrigin"] = {
        "x": reader.read_float32(),
        "y": reader.read_float32(),
        "z": reader.read_float32(),
    }

    if world_struct_size == 0x40:
        result["numTriangles"] = reader.read_uint32()
        result["numVertices"] = reader.read_uint32()
        result["numPlaneSectors"] = reader.read_uint32()
        result["numAtomicSectors"] = reader.read_uint32()
        result["colSectorSize"] = reader.read_uint32()
        result["worldFlags"] = reader.read_uint32()
        result["boxMax"] = {
            "x": reader.read_float32(),
            "y": reader.read_float32(),
            "z": reader.read_float32(),
        }
        result["boxMin"] = {
            "x": reader.read_float32(),
            "y": reader.read_float32(),
            "z": reader.read_float32(),
        }
    elif world_struct_size == 0x34:
        result["boxMax"] = {
            "x": reader.read_float32(),
            "y": reader.read_float32(),
            "z": reader.read_float32(),
        }
        result["numTriangles"] = reader.read_uint32()
        result["numVertices"] = reader.read_uint32()
        result["numPlaneSectors"] = reader.read_uint32()
        result["numAtomicSectors"] = reader.read_uint32()
        result["colSectorSize"] = reader.read_uint32()
        result["worldFlags"] = reader.read_uint32()
    else:
        raise ValueError(f"Unknown worldStructSize: 0x{world_struct_size:X}")

    # MaterialList
    result["materialList"] = parse_material_list(reader)

    # First World Chunk (AtomicSector or PlaneSector tree)
    result["worldChunk"] = parse_world_chunk(
        reader,
        result["numAtomicSectors"],
        result["numPlaneSectors"],
        is_collision,
    )

    # World Extension Header (0x0003)
    result["worldExtIdentifier"] = reader.read_uint32()
    world_ext_size = reader.read_int32()
    result["worldExtSize"] = world_ext_size
    result["worldExtVersion"] = reader.read_int32()
    result["worldExtData"] = reader.read_bytes(world_ext_size).hex()

    return result


def parse_file(
    filepath: str, is_collision: bool = False
) -> Dict[str, Any]:
    """
    Parse a binary file.

    Args:
        filepath: Path to the binary file
        is_collision: If True, skip color and UV data in AtomicSectors

    Returns:
        Dictionary containing all parsed values
    """
    with open(filepath, "rb") as f:
        data = f.read()
    return parse(data, is_collision)


def collect_atomic_sectors(chunk: Optional[Dict[str, Any]]) -> list:
    """Recursively collect all AtomicSector data from the BSP tree."""
    if chunk is None:
        return []

    sectors = []
    if chunk["type"] == "AtomicSector":
        sectors.append(chunk["data"])
    elif chunk["type"] == "PlaneSector":
        plane_data = chunk["data"]
        sectors.extend(collect_atomic_sectors(plane_data.get("leftSection")))
        sectors.extend(collect_atomic_sectors(plane_data.get("rightSection")))

    return sectors


def write_mtl(filepath: str, materials: list, texture_prefix: str = "", mat_suffix: str = ""):
    """Write materials to MTL file."""
    with open(filepath, "w") as f:
        for i, mat in enumerate(materials):
            f.write(f"newmtl material_{i}_{mat_suffix}\n")

            # Color (convert 0-255 to 0-1)
            color = mat.get("color", {})
            r = color.get("r", 255) / 255.0
            g = color.get("g", 255) / 255.0
            b = color.get("b", 255) / 255.0

            f.write(f"Kd {r:.6f} {g:.6f} {b:.6f}\n")
            f.write(
                f"Ka {mat.get('ambient', 0.1):.6f} {mat.get('ambient', 0.1):.6f} {mat.get('ambient', 0.1):.6f}\n"
            )
            f.write(
                f"Ks {mat.get('specular', 0.0):.6f} {mat.get('specular', 0.0):.6f} {mat.get('specular', 0.0):.6f}\n"
            )

            # Alpha
            a = color.get("a", 255) / 255.0
            if a < 1.0:
                f.write(f"d {a:.6f}\n")

            # Texture
            if mat.get("isTextured") and mat.get("texture"):
                tex_name = mat["texture"].get("diffuseTextureName", "")
                if tex_name:
                    f.write(f"map_Kd {texture_prefix}{tex_name}.png\n")

            f.write("\n")


def write_obj(output_path: str, filename: str, world_data: dict, texture_prefix: str = "", scale: float = 1.0):
    """Write parsed world data to OBJ file, optionally scaling geometry."""
    import os
    
    mat_suffix = str(random.randint(1000, 9999))

    sectors = collect_atomic_sectors(world_data.get("worldChunk", []))
    if not sectors:
        print("No geometry found in BSP")
        return

    materials = world_data.get("materialList", {}).get("materials", [])
    obj_path = os.path.join(output_path, f"{filename}.obj")
    mtl_path = os.path.join(output_path, f"{filename}.mtl")

    write_mtl(mtl_path, materials, texture_prefix, mat_suffix)

    vertex_offset = 0
    uv_offset = 0

    with open(obj_path, "w") as f:
        f.write("# RenderWare World BSP Export\n")
        f.write(f"# Vertices: {world_data.get('numVertices', 0)}\n")
        f.write(f"# Triangles: {world_data.get('numTriangles', 0)}\n")
        f.write(f"mtllib {filename}.mtl\n\n")

        for sector_idx, sector in enumerate(sectors):
            if sector.get("isNativeData"):
                continue

            vertices = sector.get("vertices", [])
            uvs = sector.get("uvs", [])
            triangles = sector.get("triangles", [])

            if not vertices:
                continue

            f.write(f"# Sector {sector_idx}\n")
            f.write(f"g sector_{sector_idx}\n")

            # Write vertices with scaling
            for v in vertices:
                f.write(f"v {v['x']*scale:.6f} {v['y']*scale:.6f} {v['z']*scale:.6f}\n")

            # Write UVs (V flipped)
            for uv in uvs:
                f.write(f"vt {uv['u']:.6f} {1.0 - uv['v']:.6f}\n")

            # Group triangles by material (add matListWindowBase to get actual material index)
            mat_base = sector.get("matListWindowBase", 0)
            tris_by_mat = {}
            for tri in triangles:
                mat_idx = mat_base + tri["materialIndex"]
                tris_by_mat.setdefault(mat_idx, []).append(tri)

            # Write faces grouped by material
            for mat_idx in sorted(tris_by_mat.keys()):
                f.write(f"usemtl material_{mat_idx}_{mat_suffix}\n")
                for tri in tris_by_mat[mat_idx]:
                    v1 = tri["vertex1"] + vertex_offset + 1
                    v2 = tri["vertex2"] + vertex_offset + 1
                    v3 = tri["vertex3"] + vertex_offset + 1

                    if uvs:
                        vt1 = tri["vertex1"] + uv_offset + 1
                        vt2 = tri["vertex2"] + uv_offset + 1
                        vt3 = tri["vertex3"] + uv_offset + 1
                        f.write(f"f {v1}/{vt1} {v2}/{vt2} {v3}/{vt3}\n")
                    else:
                        f.write(f"f {v1} {v2} {v3}\n")

            vertex_offset += len(vertices)
            uv_offset += len(uvs)
            f.write("\n")

    print(f"Wrote {obj_path}")
    print(f"Wrote {mtl_path}")
