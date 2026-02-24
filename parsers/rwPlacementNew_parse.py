import struct
import argparse

BF = 0xBF

def read_u32(f):
    data = f.read(4)
    if len(data) != 4:
        raise EOFError("Unexpected EOF while reading u32")
    return struct.unpack("<I", data)[0]

def read_cstring(f):
    data = bytearray()
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("EOF while reading cstring")
        if b == b'\x00':
            break
        data.append(b[0])
    return data.decode("ascii", errors="replace")

def parse_file(path):
    result = {
        "numEntries": 0,
        "entries": []
    }

    with open(path, "rb") as f:
        num_entries = read_u32(f)
        result["numEntries"] = num_entries

        for i in range(num_entries):
            name = read_cstring(f)

            bf_count = 0
            while True:
                pos = f.tell()
                b = f.read(1)
                if not b:
                    raise EOFError("EOF while skipping BF bytes")
                if b[0] == BF:
                    bf_count += 1
                else:
                    f.seek(pos)
                    break

            count = read_u32(f)

            result["entries"].append({
                "name": name,
                "bf_padding": bf_count,
                "count": count
            })

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="file.rwPlacementNew")
    args = parser.parse_args()

    data = parse_file(args.file)
    print(data)


if __name__ == "__main__":
    main()
