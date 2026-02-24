import struct
from enum import Enum
import uuid


def MAKECHUNKID(vendorID, chunkID):
    return ((vendorID & 0xFFFFFF) << 8) | (chunkID & 0xFF)


class strfunc_func(Enum):
    strfunc_VersionNumber = -1

    strfunc_Reset = 0

    strfunc_Reserved1 = 1
    strfunc_Reserved2 = 2

    strfunc_SetDirectorsCameraMatrix = 3

    strfunc_CreateEntity = 4
    strfunc_UpdateEntityAttributes = 5

    strfunc_SetFrozenMode = 6
    strfunc_SetRunningMode = 7

    strfunc_EnableDirectorsCamera = 8
    strfunc_DisableDirectorsCamera = 9

    strfunc_TextComment = 10

    strfunc_StartSystem = 11
    strfunc_StopSystem = 12

    strfunc_DeleteEntity = 13
    strfunc_DeleteAllEntities = 14

    strfunc_UnLoadAsset = 15

    strfunc_Shutdown = 16
    strfunc_CloseConnection = 17
    strfunc_SendTestEvent = 18

    strfunc_Reserved3 = 19
    strfunc_Reserved3b = 20

    strfunc_LoadAsset = 21

    strfunc_LoadEmbeddedAsset = 22

    strfunc_Reserved4 = 23

    strfunc_GetEntityMatrix = 24

    strfunc_CustomData = 25

    strfunc_FunctionProfiler = 26

    strfunc_ResetEntity = 27

    strFunc_PlacementNew = 28

    strfunc_Initialize = 29

    strfunc_UpdateAsset = 30

    strfunc_DynamicSequence = 31


rwVENDORID_CORE = 0x000000
rwVENDORID_CRITERIONRM = 0x000007

rwID_STRUCT = MAKECHUNKID(rwVENDORID_CORE, 0x01)
rwID_STRING = MAKECHUNKID(rwVENDORID_CORE, 0x02)
rwID_EXTENSION = MAKECHUNKID(rwVENDORID_CORE, 0x03)
rwID_CAMERA = MAKECHUNKID(rwVENDORID_CORE, 0x05)
rwID_TEXTURE = MAKECHUNKID(rwVENDORID_CORE, 0x06)
rwID_MATERIAL = MAKECHUNKID(rwVENDORID_CORE, 0x07)
rwID_MATLIST = MAKECHUNKID(rwVENDORID_CORE, 0x08)
rwID_ATOMICSECT = MAKECHUNKID(rwVENDORID_CORE, 0x09)
rwID_PLANESECT = MAKECHUNKID(rwVENDORID_CORE, 0x0A)
rwID_WORLD = MAKECHUNKID(rwVENDORID_CORE, 0x0B)
rwID_MATRIX = MAKECHUNKID(rwVENDORID_CORE, 0x0D)
rwID_FRAMELIST = MAKECHUNKID(rwVENDORID_CORE, 0x0E)
rwID_GEOMETRY = MAKECHUNKID(rwVENDORID_CORE, 0x0F)
rwID_CLUMP = MAKECHUNKID(rwVENDORID_CORE, 0x10)
rwID_LIGHT = MAKECHUNKID(rwVENDORID_CORE, 0x12)
rwID_UNICODESTRING = MAKECHUNKID(rwVENDORID_CORE, 0x13)
rwID_ATOMIC = MAKECHUNKID(rwVENDORID_CORE, 0x14)
rwID_GEOMETRYLIST = MAKECHUNKID(rwVENDORID_CORE, 0x1A)


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

    def read(self, size: int) -> bytes:
        """
        Equivalent to RwStreamRead(stream, buffer, size)
        Returns bytes read (may be shorter only at EOF).
        """
        if self.offset + size > len(self.data):
            return b""

        chunk = self.data[self.offset : self.offset + size]
        self.offset += size
        return chunk

    def seek(self, offset: int):
        if offset < 0 or offset > len(self.data):
            raise ValueError("Invalid seek offset")
        self.offset = offset

    def tell(self) -> int:
        return self.offset

    def skip(self, size: int):
        self.seek(self.offset + size)

    def canRead(self, size: int) -> bool:
        return self.offset + size <= len(self.data)

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

    def readPaddedCString(self, alignment=4, encoding="utf-8") -> str:
        start = self.offset
        s = self.readCString(encoding)
        byte_length = self.offset - start  # actual bytes consumed including null
        remainder = byte_length % alignment
        if remainder:
            self.offset += alignment - remainder
        return s

    def readGUID(self):
        guid_bytes = self.readBytes(16)
        return uuid.UUID(bytes=guid_bytes)

    def readBool(self):
        return self.readUint32() != 0


def chunk_is_complex(chunk_header_info) -> bool:
    t = chunk_header_info.get("type", "")

    if t in (
        rwID_STRUCT,
        rwID_STRING,
        rwID_EXTENSION,
        rwID_MATRIX,
        rwID_UNICODESTRING,
    ):
        return False

    if t in (
        rwID_CAMERA,
        rwID_TEXTURE,
        rwID_MATERIAL,
        rwID_MATLIST,
        rwID_ATOMICSECT,
        rwID_PLANESECT,
        rwID_WORLD,
        rwID_FRAMELIST,
        rwID_GEOMETRY,
        rwID_CLUMP,
        rwID_LIGHT,
        rwID_ATOMIC,
        rwID_GEOMETRYLIST,
    ):
        return True

    return False


def rw_library_id_unpack_version(library_id: int) -> int:
    return (library_id >> 16) & 0xFFFF


def rw_library_id_unpack_build_num(library_id: int) -> int:
    return library_id & 0xFFFF


def _rw_stream_read_chunk_header(parser):
    """
    Reads a RenderWare chunk header.

    Returns:
        (type, length, version, build_num) on success
        None on failure
    """

    # sizeof(_rwMark) == 12 bytes (3 uint32)
    raw = parser.read(12)
    if raw is None or len(raw) != 12:
        return None

    # RwMemNative32 equivalent: assume little-endian
    mark_type, mark_length, library_id = struct.unpack("<III", raw)

    chunk_hdr_info = {"type": mark_type, "length": mark_length}

    # Old vs new library ID
    if (library_id & 0xFFFF0000) == 0:
        chunk_hdr_info["version"] = library_id << 8
        chunk_hdr_info["buildNum"] = 0
    else:
        chunk_hdr_info["version"] = rw_library_id_unpack_version(library_id)
        chunk_hdr_info["buildNum"] = rw_library_id_unpack_build_num(library_id)

    chunk_hdr_info["isComplex"] = chunk_is_complex(chunk_hdr_info)

    return (
        chunk_hdr_info["type"],
        chunk_hdr_info["length"],
        chunk_hdr_info["version"],
        chunk_hdr_info["buildNum"],
    )


def RwStreamReadChunkHeaderInfo(parser):
    """
    Python equivalent of RwStreamReadChunkHeaderInfo.

    Returns:
        chunk_header_info on success
        None on failure
    """
    chunk_header_info = {}

    if parser is None:
        raise AssertionError("parser must not be None")

    result = _rw_stream_read_chunk_header(parser)
    if result is None:
        return None

    read_type, read_length, read_version, read_build_num = result

    chunk_header_info["type"] = read_type
    chunk_header_info["length"] = read_length
    chunk_header_info["version"] = read_version
    chunk_header_info["buildNum"] = read_build_num
    chunk_header_info["isComplex"] = chunk_is_complex(chunk_header_info)

    return chunk_header_info


class UsageCounter:
    def __init__(self):
        self.counterDict = {}

    def plusOne(self, key):
        if key in self.counterDict:
            self.counterDict[key] += 1
        else:
            self.counterDict[key] = 1

    def get(self):
        return self.counterDict

    def getKey(self, key):
        return self.counterDict.get(key, 0)


def PrintPlacementNewParams(parser: Parser, chunkHeaderInfo):
    print(f"{hex(parser.offset)} - strFunc_PlacementNew")

    # read entire chunk into a sub-buffer, advancing the stream past it
    buf = Parser(parser.readBytes(chunkHeaderInfo["length"]), endian="little")

    elementCount = buf.readUint32()

    for element in range(0, elementCount):
        behaviour = buf.readPaddedCString()
        entityCount = buf.readUint32()
        print(f"    {behaviour} Count:{entityCount}")


def PrintUploadResources(parser: Parser, chunkHeaderInfo):
    print(f"{hex(parser.offset)} - strfunc_LoadEmbeddedAsset")

    headerSize = parser.readUint32()

    # read entire chunk into a sub-buffer
    buf = Parser(parser.readBytes(headerSize), endian="little")

    dataSize = parser.readUint32()

    nameLength = buf.readUint32()
    name = buf.readPaddedCString(nameLength)

    guid = buf.readGUID()

    typeLength = buf.readUint32()
    assetType = buf.readPaddedCString(typeLength)

    fileLength = buf.readUint32()
    file = buf.readPaddedCString(fileLength)

    depsSize = buf.readUint32()
    dependecies = buf.readPaddedCString(depsSize)
    
    print(f"\tHeader Size: {headerSize}")
    print(f"\tData Size: {dataSize}")
    print(f"\tName: {name}")
    print(f"\tID: {{{guid}}}")  # ID: {abc-abc-abc-abc}
    print(f"\tType: {assetType}")
    print(f"\tFile: {file}")
    print(f"\tDependencies: {dependecies}")

    # Skip the file contents
    parser.skip(dataSize)

    # Skip any extra padding
    extraPadding = (
        chunkHeaderInfo.get("length", 0) - dataSize - headerSize - 2 * 4
    )  # 4 being sizeof (RwUInt32)
    parser.skip(extraPadding)


def PrintSectionHeader(chunkHeaderInfo):
    print(
        f"Length: {chunkHeaderInfo.get('length', 0)} Type: {chunkHeaderInfo.get('type', 0)}"
    )


def ParseMatrix4x4(data):
    buf = Parser(data, endian="little")

    matrix = [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    
    matrix[0][0] = buf.readFloat()
    matrix[0][1] = buf.readFloat()
    matrix[0][2] = buf.readFloat()
    matrix[0][3] = buf.readFloat()
    
    matrix[1][0] = buf.readFloat()
    matrix[1][1] = buf.readFloat()
    matrix[1][2] = buf.readFloat()
    matrix[1][3] = buf.readFloat()
    
    matrix[2][0] = buf.readFloat()
    matrix[2][1] = buf.readFloat()
    matrix[2][2] = buf.readFloat()
    matrix[2][3] = buf.readFloat()
    
    matrix[3][0] = buf.readFloat()
    matrix[3][1] = buf.readFloat()
    matrix[3][2] = buf.readFloat()
    matrix[3][3] = buf.readFloat()
    
    return matrix


def HandleAttribute(command, data, strCurrentClass):
    if command == 1 and strCurrentClass == "CSystemCommands":
        matrix = ParseMatrix4x4(data)
        with open("entities.txt", "a") as f:
            f.write(str(matrix)+"\n")
        print(f"\t\t{matrix} Attribute {command:>3}")
        return

    output = f"\t\tAttribute {command:>3}"

    if data:
        textChars = data

        # Text view: alpha chars kept, others replaced with space, padded to 15
        textView = ""
        for b in textChars:
            if (65 <= b <= 90) or (97 <= b <= 122):
                textView += chr(b)
            else:
                textView += " "

        # Hex view: uppercase, 2-digit, space separated
        hexParts = [f"{b:02X}" for b in textChars]
        hexView = " ".join(hexParts)

        output += f": [{textView}][{hexView}]"

    print(output)


def HandleAttributes(data, ussageCounter_behaviour: UsageCounter):
    RWSPH_CLASSID = 0x80000000
    RWSPH_INSTANCEID = 0x40000000
    RWSPH_CREATECLASSID = 0x20000000
    strCurrentClass = ""

    buf = Parser(data, endian="little")

    while buf.canRead(4):
        packetStart = buf.tell()
        packetSize = buf.readUint32()
        if packetSize == 0:
            break

        command = buf.readUint32()
        dataSize = packetSize - 2 * 4  # subtract the two uint32s (size + command)

        if command == RWSPH_CLASSID:
            dataBytes = buf.readBytes(dataSize)
            strCurrentClass = dataBytes.split(b"\x00")[0].decode(
                "ascii", errors="replace"
            )
            print(f"\tClass:\t{strCurrentClass}")
            
        elif command == RWSPH_INSTANCEID:
            entityID = uuid.UUID(bytes=buf.readBytes(16))
            print(f"\tEntity ID:\t{{{entityID}}}")
            
        elif command == RWSPH_CREATECLASSID:
            dataBytes = buf.readBytes(dataSize)
            
            behaviour = dataBytes.split(b"\x00")[0].decode("ascii", errors="replace")
            print(f"\tBehaviour:\t{behaviour}")
            ussageCounter_behaviour.plusOne(behaviour.strip())
            
        else:
            if command == 0 and strCurrentClass == "CSystemCommands":
                assetID = uuid.UUID(bytes=buf.readBytes(16))
                print(f"\t\tAttach asset, ID:\t{{{assetID}}}")
            else:
                HandleAttribute(command, buf.readBytes(dataSize), strCurrentClass)

        # Advance to next packet (ensures correct alignment regardless of how much data was consumed)
        buf.seek(packetStart + packetSize)

    print()


def PrintCreateEntity(parser: Parser, chunkHeaderInfo, ussageCounter_behaviour):
    print(f"{hex(parser.offset)} - strfunc_CreateEntity")

    buf = Parser(parser.readBytes(chunkHeaderInfo["length"]), endian="little")

    isGlobal = buf.readBool()

    attributePacket = buf.readBytes(
        chunkHeaderInfo["length"] - 4
    )  # 4 bytes for the RwBool

    HandleAttributes(attributePacket, ussageCounter_behaviour)

    print(f"\tGlobal Flag:\t{isGlobal}")


def ReadStreamContents(data):
    global rwVENDORID_CRITERIONRM

    p = Parser(data, endian="little")
    ussageCounter_strfunc = UsageCounter()
    ussageCounter_behaviour = UsageCounter()

    while True:
        chunkHeaderInfo = RwStreamReadChunkHeaderInfo(p)
        if not chunkHeaderInfo:
            print("End of stream encountered\r\n")
            break

        print()
        PrintSectionHeader(chunkHeaderInfo)
        chunk_type = chunkHeaderInfo["type"]
        if chunk_type == MAKECHUNKID(
            rwVENDORID_CRITERIONRM, strfunc_func.strfunc_CreateEntity.value
        ):
            PrintCreateEntity(p, chunkHeaderInfo, ussageCounter_behaviour)
            ussageCounter_strfunc.plusOne("strfunc_CreateEntity")
        elif chunk_type == MAKECHUNKID(
            rwVENDORID_CRITERIONRM, strfunc_func.strFunc_PlacementNew.value
        ):
            PrintPlacementNewParams(p, chunkHeaderInfo)
            ussageCounter_strfunc.plusOne("strFunc_PlacementNew")
        elif chunk_type == MAKECHUNKID(
            rwVENDORID_CRITERIONRM, strfunc_func.strfunc_LoadEmbeddedAsset.value
        ):
            PrintUploadResources(p, chunkHeaderInfo)
            ussageCounter_strfunc.plusOne("strfunc_LoadEmbeddedAsset")
        else:
            p.skip(chunkHeaderInfo["length"])
            print("UNKNOWN strfunc!!")
            ussageCounter_strfunc.plusOne(f"UNKNOWN_{chunkHeaderInfo['type']}")

    print("-" * 20)
    print("str_functions used: ")
    ussage = ussageCounter_strfunc.get()
    for key, value in ussage.items():
        print(f"    {key}: {value}")

    print()

    print("behaviours used: ")
    ussage = ussageCounter_behaviour.get()
    for key, value in ussage.items():
        print(f"    {key}: {value}")


with open("MADAGASCAR.mem", "rb") as f:
    f.seek(0)
    data = f.read()

print("Read a file stream")

ReadStreamContents(data)
