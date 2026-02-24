import os
import argparse
import binascii

def search_guid(folder, guid, ascii_mode=False):
    if ascii_mode:
        search_bytes = guid.encode("ascii")
    else:
        # Remove dashes if user passes a dashed GUID
        guid = guid.replace("-", "")
        search_bytes = binascii.unhexlify(guid)

    for root, _, files in os.walk(folder):
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, "rb") as f:
                    data = f.read()
                    offset = data.find(search_bytes)
                    if offset != -1:
                        mode = "ASCII" if ascii_mode else "BYTES"
                        print(
                            f"[{mode}] Found in {path} at byte offset {offset} (0x{offset:X})"
                        )
            except Exception:
                pass  # skip unreadable files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search folder for RenderWare GUID")
    parser.add_argument("folder", help="Folder to search")
    parser.add_argument(
        "guid",
        help="GUID (32-char hex for byte search or literal string for --ascii)",
    )
    parser.add_argument(
        "--ascii",
        action="store_true",
        help="Search for GUID as an ASCII string instead of raw bytes",
    )

    args = parser.parse_args()
    search_guid(args.folder, args.guid, ascii_mode=args.ascii)
