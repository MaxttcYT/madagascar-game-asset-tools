import struct
import os
import sys
import json
import base64

RW_CONTAINER = 1814


def read_u32(f):
    return struct.unpack("<I", f.read(4))[0]


def read_string_raw(f, size):
    data = f.read(size)
    if b"\x00" in data:
        data = data[:data.index(b"\x00")]
    return data.decode("ascii", errors="ignore")


def remove_ext(name, ext):
    if name.lower().endswith(ext.lower()):
        return name[:-len(ext)]
    return name


def main(in_file, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    manifest = {
        "source_file": os.path.basename(in_file),
        "entries": []
    }

    with open(in_file, "rb") as f:
        f.seek(0, os.SEEK_END)
        sSize = f.tell()
        f.seek(0)

        Index = 0

        while True:
            Index += 1

            try:
                rwType = read_u32(f)
            except struct.error:
                break

            fName = str(Index) + "_"

            sectSize = read_u32(f)
            rwVersion = read_u32(f)
            sectOffset = f.tell()
            print(rwVersion)

            print(f"INDEX: {Index} RWTYPE: {rwType}")

            if rwType != RW_CONTAINER:
                fName += str(rwType)
                fName += ".UNK"

                f.seek(sectOffset)
                data = f.read(sectSize)

                with open(os.path.join(out_dir, fName), "wb") as out:
                    out.write(data)

                manifest["entries"].append({
                    "index": Index,
                    "filename": fName,
                    "rwType": rwType,
                    "sectSize": sectSize,
                    "rwVersion": rwVersion,
                    "is_container": False
                })

            else:
                memory_file = f.read(sectSize)
                mem = memory_file
                mem_pos = 0

                def mem_u32():
                    nonlocal mem_pos
                    val = struct.unpack("<I", mem[mem_pos:mem_pos + 4])[0]
                    mem_pos += 4
                    return val

                def mem_string(size):
                    nonlocal mem_pos
                    data = mem[mem_pos:mem_pos + size]
                    mem_pos += size
                    if b"\x00" in data:
                        data = data[:data.index(b"\x00")]
                    return data.decode("ascii", errors="ignore")

                headerSize = mem_u32()
                headerStart = mem_pos

                nameSize = mem_u32()

                name_raw = mem[mem_pos:mem_pos + nameSize]
                mem_pos += nameSize

                if b"\x00" in name_raw:
                    rwName = name_raw[:name_raw.index(b"\x00")].decode("ascii", errors="ignore")
                else:
                    rwName = name_raw.decode("ascii", errors="ignore")

                fName += rwName

                # 16 unknown bytes
                unknown_16_bytes = mem[mem_pos:mem_pos + 16]
                mem_pos += 16

                rwID_Size = mem_u32()
                rwID_raw = mem[mem_pos:mem_pos + rwID_Size]
                rwID = mem_string(rwID_Size)

                # Capture any remaining header bytes after rwID
                header_end = headerStart + headerSize
                remaining_header = mem[mem_pos:header_end]

                print(f"INDEX: {Index} RWID: {rwID}")

                if rwID == "rwID_TEXDICTIONARY":
                    fName = remove_ext(fName, ".txd")
                    fName = remove_ext(fName, ".TXD")
                    fName += ".txd"
                elif rwID == "rwaID_WAVEDICT":
                    fName = remove_ext(fName, ".rws")
                    fName = remove_ext(fName, ".RWS")
                    fName += ".rws"
                elif rwID == "rwID_WORLD":
                    fName = remove_ext(fName, ".bsp")
                    fName = remove_ext(fName, ".BSP")
                    fName += ".bsp"
                elif rwID == "TextStringDict":
                    fName = remove_ext(fName, ".txl")
                    fName = remove_ext(fName, ".TXL")
                    fName += ".txl"
                elif rwID == "rwID_CLUMP":
                    fName = remove_ext(fName, ".dff")
                    fName = remove_ext(fName, ".DFF")
                    fName += ".dff"
                elif rwID == "rwID_HANIMANIMATION":
                    fName = remove_ext(fName, ".anm")
                    fName = remove_ext(fName, ".ANM")
                    fName += ".anm"
                elif rwID == "SCRIPT":
                    fName = remove_ext(fName, ".ai")
                    fName = remove_ext(fName, ".AI")
                    fName += ".ai"
                elif rwID == "TEXT":
                    fName += ".TEXT"
                elif rwID == "rwID_2DFONT":
                    fName = remove_ext(fName, ".fnt")
                    fName = remove_ext(fName, ".FNT")
                    fName += ".fnt"
                elif rwID == "KFset":
                    fName = remove_ext(fName, ".lpa")
                    fName = remove_ext(fName, ".LPA")
                    fName += ".lpa"
                else:
                    fName += "."
                    fName += rwID

                mem_pos = headerStart
                mem_pos += headerSize

                fSize = struct.unpack("<I", mem[mem_pos:mem_pos + 4])[0]
                mem_pos += 4
                fOffset = mem_pos

                with open(os.path.join(out_dir, fName), "wb") as out:
                    out.write(mem[fOffset:fOffset + fSize])

                # Capture any trailing bytes after file data
                trailing_data = mem[fOffset + fSize:]

                manifest["entries"].append({
                    "index": Index,
                    "filename": fName,
                    "rwType": rwType,
                    "sectSize": sectSize,
                    "rwVersion": rwVersion,
                    "is_container": True,
                    "container": {
                        "headerSize": headerSize,
                        "nameSize": nameSize,
                        "name_raw": base64.b64encode(name_raw).decode("ascii"),
                        "unknown_16_bytes": base64.b64encode(unknown_16_bytes).decode("ascii"), # Probably GUID
                        "rwID_Size": rwID_Size,
                        "rwID_raw": base64.b64encode(rwID_raw).decode("ascii"),
                        "rwID": rwID,
                        "remaining_header": base64.b64encode(remaining_header).decode("ascii"),
                        "fSize": fSize,
                        "trailing_data": base64.b64encode(trailing_data).decode("ascii")
                    }
                })

            f.seek(sectOffset + sectSize)

            checkPos = f.tell()
            if checkPos == sSize:
                print(f"Files Extracted: {Index}")
                print(hex(f.tell()), hex(sSize))
                break

    # Save manifest
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w") as mf:
        json.dump(manifest, mf, indent=2)
    print(f"Manifest saved to: {manifest_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stream_unpack.py <input.stream> <output_dir>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
