import struct
import os
import sys
import json
import base64

RW_CONTAINER = 1814


def write_u32(f, val):
    f.write(struct.pack("<I", val))


def main(in_dir, out_file):
    manifest_path = os.path.join(in_dir, "manifest.json")

    if not os.path.exists(manifest_path):
        print(f"Error: manifest.json not found in {in_dir}")
        sys.exit(1)

    with open(manifest_path, "r") as mf:
        manifest = json.load(mf)

    with open(out_file, "wb") as f:
        for entry in manifest["entries"]:
            filename = entry["filename"]
            filepath = os.path.join(in_dir, filename)

            if not os.path.exists(filepath):
                print(f"Warning: {filename} not found, skipping")
                continue

            with open(filepath, "rb") as df:
                file_data = df.read()

            rwType = entry["rwType"]
            rwVersion = entry["rwVersion"]

            if not entry["is_container"]:
                # Non-container: sectSize is just the file data size
                sectSize = len(file_data)

                write_u32(f, rwType)
                write_u32(f, sectSize)
                write_u32(f, rwVersion)
                f.write(file_data)

                print(f"Packed: {filename} (non-container, {sectSize} bytes)")

            else:
                # Container: rebuild the full structure
                container = entry["container"]

                name_raw = base64.b64decode(container["name_raw"])
                unknown_16_bytes = base64.b64decode(container["unknown_16_bytes"])
                rwID_raw = base64.b64decode(container["rwID_raw"])
                remaining_header = base64.b64decode(container.get("remaining_header", ""))
                trailing_data = base64.b64decode(container.get("trailing_data", ""))

                # Build container header
                # Header contains: nameSize(4) + name_raw + unknown_16_bytes(16) + rwID_Size(4) + rwID_raw + remaining
                header_content = b""
                header_content += struct.pack("<I", container["nameSize"])
                header_content += name_raw
                header_content += unknown_16_bytes
                header_content += struct.pack("<I", container["rwID_Size"])
                header_content += rwID_raw
                header_content += remaining_header

                headerSize = len(header_content)

                # Full container data: headerSize(4) + header_content + fSize(4) + file_data + trailing
                container_data = b""
                container_data += struct.pack("<I", headerSize)
                container_data += header_content
                container_data += struct.pack("<I", len(file_data))
                container_data += file_data
                container_data += trailing_data

                sectSize = len(container_data)

                write_u32(f, rwType)
                write_u32(f, sectSize)
                write_u32(f, rwVersion)
                f.write(container_data)

                print(f"Packed: {filename} (container, {sectSize} bytes)")

        print(f"\nStream saved to: {out_file}")
        print(f"Total size: {f.tell()} bytes")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python stream_repack.py <input_dir> <output.stream>")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
