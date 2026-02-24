import struct  # noqa: E402


# -----------------------------
# BSP READER
# -----------------------------

class BSPReader:
    def __init__(self, filepath):
        self.filepath = filepath
        self.file = None

    def open(self):
        self.file = open(self.filepath, "rb")

    def close(self):
        if self.file:
            self.file.close()

    def read_u32(self):
        return struct.unpack("<I", self.file.read(4))[0]

    def read_i32(self):
        return struct.unpack("<i", self.file.read(4))[0]

    def read_f32(self):
        return struct.unpack("<f", self.file.read(4))[0]

    def read_bytes(self, size):
        return self.file.read(size)

    def read_header(self):
        # Very generic header read
        magic = self.read_bytes(4)
        version = self.read_i32()

        print("=== BSP HEADER ===")
        print("Magic  :", magic)
        print("Version:", version)
        self.report({'INFO'}, "Hello world!")
        self.report({'INFO'}, "Hello world!")

        return magic, version