import struct


class Parser:
    def __init__(self, data: bytes, endian: str = "little"):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("data must be bytes or bytearray")

        self.data = data
        self.offset = 0

        if endian == "little":
            self.endian = "<"
        elif endian == "big":
            self.endian = ">"
        else:
            raise ValueError("endian must be 'little' or 'big'")

    # -------------------------
    # Core helpers
    # -------------------------

    def _read(self, fmt: str):
        size = struct.calcsize(fmt)
        if self.offset + size > len(self.data):
            raise EOFError("Attempt to read past end of buffer")

        value = struct.unpack_from(fmt, self.data, self.offset)
        self.offset += size
        return value[0] if len(value) == 1 else value

    def seek(self, offset: int):
        if offset < 0 or offset > len(self.data):
            raise ValueError("Invalid seek offset")
        self.offset = offset

    def tell(self) -> int:
        return self.offset

    def skip(self, size: int):
        self.seek(self.offset + size)

    # -------------------------
    # Integer reads
    # -------------------------

    def readUint8(self):
        return self._read(self.endian + "B")

    def readInt8(self):
        return self._read(self.endian + "b")

    def readUint16(self):
        return self._read(self.endian + "H")

    def readInt16(self):
        return self._read(self.endian + "h")

    def readUint32(self):
        return self._read(self.endian + "I")

    def readInt32(self):
        return self._read(self.endian + "i")

    def readUint64(self):
        return self._read(self.endian + "Q")

    def readInt64(self):
        return self._read(self.endian + "q")

    # -------------------------
    # Floating point
    # -------------------------

    def readFloat(self):
        return self._read(self.endian + "f")

    def readDouble(self):
        return self._read(self.endian + "d")

    # -------------------------
    # Raw / strings
    # -------------------------

    def readBytes(self, size: int) -> bytes:
        if self.offset + size > len(self.data):
            raise EOFError("Attempt to read past end of buffer")

        b = self.data[self.offset : self.offset + size]
        self.offset += size
        return b

    def readCString(self, encoding="utf-8") -> str:
        start = self.offset
        while self.offset < len(self.data) and self.data[self.offset] != 0:
            self.offset += 1

        if self.offset >= len(self.data):
            raise EOFError("Unterminated C string")

        s = self.data[start : self.offset].decode(encoding)
        self.offset += 1  # skip null byte
        return s


data = bytes.fromhex(
    "0D 00 0F 0F 01 02 00 00 03 00 00 00 02 00 00 00 05 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01",
)
p = Parser(data, endian="little")

out = {}

effectType = p.readUint32()
print("effect type: ", effectType)