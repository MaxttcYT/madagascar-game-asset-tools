#!/usr/bin/env python3
"""
RenderWare-style Object Storage Parser
Parses binary data that appears to store level objects in a tree structure
with entity components, transforms, and tree node links.
"""

import struct
from dataclasses import dataclass, field
from typing import Optional, List, BinaryIO
from enum import IntFlag
import io


class NodeFlags(IntFlag):
    """Flags that may indicate node type or RB-tree color"""
    NONE = 0x00000000
    TYPE_A = 0x20000000  # Possibly root/entity marker
    TYPE_B = 0x40000000  # Possibly data node
    TYPE_C = 0x80000000  # Possibly RED node or component marker


@dataclass
class Matrix4x4:
    """4x4 transformation matrix (stored as 4x4 = 64 bytes in this format)"""
    m: List[List[float]] = field(default_factory=lambda: [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]])
    
    @classmethod
    def read(cls, f: BinaryIO) -> 'Matrix4x4':
        """Read 4x4 matrix (64 bytes - full 4x4 matrix)
        
        RenderWare typically uses:
        - 3x3 rotation in upper-left
        - Translation in the 4th row (or column depending on convention)
        """
        m = []
        for row in range(4):
            m.append(list(struct.unpack('<4f', f.read(16))))
        return cls(m=m)
    
    @property
    def position(self) -> tuple:
        """Extract translation from matrix (4th row in this format)"""
        return (self.m[3][0], self.m[3][1], self.m[3][2])
    
    @property
    def is_identity_rotation(self) -> bool:
        """Check if rotation part is identity"""
        return (self.m[0][:3] == [1.0, 0.0, 0.0] and
                self.m[1][:3] == [0.0, 1.0, 0.0] and
                self.m[2][:3] == [0.0, 0.0, 1.0])
    
    def __repr__(self):
        lines = []
        for row in self.m:
            lines.append(f"  [{row[0]:8.3f} {row[1]:8.3f} {row[2]:8.3f} {row[3]:8.3f}]")
        return "Matrix4x4:\n" + "\n".join(lines)


@dataclass
class TreeNodeLink:
    """Tree node link structure (offset, index, child pointer)"""
    offset: int
    index: int
    child_ptr: int  # -1 (0xFFFFFFFF) means NULL
    
    @classmethod
    def read(cls, f: BinaryIO) -> 'TreeNodeLink':
        offset, index, child_ptr = struct.unpack('<3I', f.read(12))
        # Convert to signed for -1 comparison
        if child_ptr == 0xFFFFFFFF:
            child_ptr = -1
        return cls(offset=offset, index=index, child_ptr=child_ptr)
    
    def __repr__(self):
        child = "NULL" if self.child_ptr == -1 else f"{self.child_ptr}"
        return f"TreeNodeLink(offset={self.offset}, index={self.index}, child={child})"


@dataclass
class ComponentEntry:
    """A component/class entry in the object storage"""
    size: int
    padding: int
    flags: int
    name: Optional[str] = None
    guid: Optional[bytes] = None
    
    @property
    def flag_type(self) -> str:
        """Interpret flags"""
        if self.flags & NodeFlags.TYPE_C:
            return "COMPONENT/RED"
        elif self.flags & NodeFlags.TYPE_B:
            return "DATA"
        elif self.flags & NodeFlags.TYPE_A:
            return "ENTITY/ROOT"
        return "NONE"
    
    def __repr__(self):
        if self.name:
            return f"ComponentEntry(name='{self.name}', size={self.size}, flags=0x{self.flags:08X} [{self.flag_type}])"
        elif self.guid:
            return f"ComponentEntry(guid={self.guid.hex()}, size={self.size}, flags=0x{self.flags:08X} [{self.flag_type}])"
        return f"ComponentEntry(size={self.size}, flags=0x{self.flags:08X})"


@dataclass
class EntityInstance:
    """An entity instance with transform and tree links"""
    size: int
    index: int
    transform: Matrix4x4
    tree_links: List[TreeNodeLink] = field(default_factory=list)


@dataclass
class ObjectStorage:
    """Root container for the object storage format"""
    sentinel: int
    root_size: int
    root_flags: int
    root_name: str
    components: List[ComponentEntry] = field(default_factory=list)
    entities: List[EntityInstance] = field(default_factory=list)


class RWObjectParser:
    """Parser for RenderWare-style object storage binary format"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.stream = io.BytesIO(data)
        self.components: List[ComponentEntry] = []
        self.entities: List[EntityInstance] = []
        
    def read_cstring(self, max_len: int = 256) -> str:
        """Read null-terminated string"""
        chars = []
        for _ in range(max_len):
            b = self.stream.read(1)
            if not b or b == b'\x00':
                break
            chars.append(b.decode('ascii', errors='replace'))
        return ''.join(chars)
    
    def peek(self, size: int) -> bytes:
        """Peek at bytes without advancing position"""
        pos = self.stream.tell()
        data = self.stream.read(size)
        self.stream.seek(pos)
        return data
    
    def read_u32(self) -> int:
        """Read unsigned 32-bit integer"""
        return struct.unpack('<I', self.stream.read(4))[0]
    
    def read_i32(self) -> int:
        """Read signed 32-bit integer"""
        return struct.unpack('<i', self.stream.read(4))[0]
    
    def read_f32(self) -> float:
        """Read 32-bit float"""
        return struct.unpack('<f', self.stream.read(4))[0]
    
    def is_printable_string(self, data: bytes) -> bool:
        """Check if data looks like a C string"""
        if not data:
            return False
        # Check if starts with printable ASCII and contains null
        for i, b in enumerate(data):
            if b == 0:
                return i > 0  # Has at least one char before null
            if b < 32 or b > 126:
                return False
        return False
    
    def parse_component_entry(self) -> Optional[ComponentEntry]:
        """Parse a component/class entry"""
        start_pos = self.stream.tell()
        
        size = self.read_u32()
        if size == 0:
            return None
            
        padding = self.read_u32()
        flags = self.read_u32()
        
        # Determine content type by peeking
        peek_data = self.peek(24)
        
        if self.is_printable_string(peek_data):
            # It's a class name
            name = self.read_cstring()
            return ComponentEntry(size=size, padding=padding, flags=flags, name=name)
        else:
            # It's likely a GUID (16 bytes)
            guid = self.stream.read(16)
            return ComponentEntry(size=size, padding=padding, flags=flags, guid=guid)
    
    def parse_entity_instance(self) -> Optional[EntityInstance]:
        """Parse an entity instance with transform"""
        size = self.read_u32()
        if size != 0x48:  # Expected size for entity with transform
            self.stream.seek(self.stream.tell() - 4)
            return None
            
        index = self.read_u32()
        transform = Matrix4x4.read(self.stream)
        
        # Read tree links until we hit zeros or end
        tree_links = []
        while self.stream.tell() < len(self.data) - 12:
            peek = self.peek(12)
            if peek == b'\x00' * 12:
                self.stream.read(12)  # consume zeros
                break
            
            offset, idx, child = struct.unpack('<3I', peek)
            if offset == 0x0C and idx < 100:  # Looks like a valid tree link
                self.stream.read(12)
                child_signed = -1 if child == 0xFFFFFFFF else child
                tree_links.append(TreeNodeLink(offset=offset, index=idx, child_ptr=child_signed))
            else:
                break
        
        return EntityInstance(size=size, index=index, transform=transform, tree_links=tree_links)
    
    def parse(self) -> ObjectStorage:
        """Parse the entire object storage structure"""
        # Read sentinel
        sentinel = self.read_i32()
        
        # Read root entry
        root_size = self.read_u32()
        root_padding = self.read_u32()
        root_flags = self.read_u32()
        root_name = self.read_cstring()
        
        storage = ObjectStorage(
            sentinel=sentinel,
            root_size=root_size,
            root_flags=root_flags,
            root_name=root_name
        )
        
        # Parse remaining entries
        while self.stream.tell() < len(self.data) - 4:
            pos = self.stream.tell()
            peek = self.peek(4)
            
            if peek == b'\x00\x00\x00\x00':
                # Skip zero padding
                self.stream.read(4)
                continue
            
            if peek == b'\xBF\xBF':
                # Skip sentinel bytes
                self.stream.read(2)
                continue
            
            # Try to parse as component entry
            size_val = struct.unpack('<I', peek)[0]
            
            if size_val == 0x48:
                # Likely an entity instance
                entity = self.parse_entity_instance()
                if entity:
                    storage.entities.append(entity)
                    self.entities.append(entity)
                    continue
            
            if size_val in (0x0C, 0x10, 0x18, 0x1C, 0x20, 0x24):
                # Likely a component entry
                comp = self.parse_component_entry()
                if comp:
                    storage.components.append(comp)
                    self.components.append(comp)
                    continue
            
            # Check if it's a tree link
            if size_val == 0x0C:
                full_peek = self.peek(12)
                offset, idx, child = struct.unpack('<3I', full_peek)
                if idx < 100:  # Reasonable index
                    self.stream.read(12)
                    continue
            
            # Skip unknown byte
            self.stream.read(1)
        
        return storage
    
    def print_hex_dump(self, start: int = 0, length: int = 256):
        """Print hex dump of data for debugging"""
        print(f"\nHex dump (offset {start}, length {length}):")
        print("-" * 70)
        
        for i in range(0, min(length, len(self.data) - start), 16):
            offset = start + i
            hex_part = ' '.join(f'{self.data[offset+j]:02X}' for j in range(min(16, len(self.data) - offset)))
            ascii_part = ''.join(
                chr(self.data[offset+j]) if 32 <= self.data[offset+j] < 127 else '.'
                for j in range(min(16, len(self.data) - offset))
            )
            print(f"{offset:04X}: {hex_part:<48} {ascii_part}")


def find_first_ascii_string(data, min_length=1):
    ascii_chars = []
    for b in data:
        if 32 <= b <= 126:  # Printable ASCII range
            ascii_chars.append(chr(b))
        else:
            if len(ascii_chars) >= min_length:
                return ''.join(ascii_chars)
            ascii_chars = []
    # Check at the end in case string is at the end
    if len(ascii_chars) >= min_length:
        return ''.join(ascii_chars)
    return None

def main():
    import os
    directory = "banquet"
    
    ussage_dict = {}
    ussage_dict_nonparseable = {}
    
    counter_parseable = 0
    counter_full = 0
    
    for filename in os.listdir(directory):
        if "_1796" in filename:
            file_path = os.path.join(directory, filename)

            if os.path.isfile(file_path):
                with open(file_path, "rb") as f:
                    data = f.read()


                    # Create parser and parse
                    parser = RWObjectParser(data)
                    storage = parser.parse()
                    
                    counter_full += 1
                    if len(storage.entities) > 0 and find_first_ascii_string(data).strip() not in ["CTFBSound", "CTFBWorld"]:
                        counter_parseable += 1
                        print(file_path)
                        print("=" * 70)
                        print("RenderWare Object Storage Parser")
                        print("=" * 70)
                        # Print results
                        print(f"\n[ROOT]")
                        print(f"  Sentinel: 0x{storage.sentinel & 0xFFFFFFFF:08X} ({storage.sentinel})")
                        print(f"  Size: {storage.root_size}")
                        print(f"  Flags: 0x{storage.root_flags:08X}")
                        print(f"  Name: '{storage.root_name}'")

                        print(f"\n[COMPONENTS] ({len(storage.components)} found)")
                        for i, comp in enumerate(storage.components):
                            print(f"  [{i}] {comp}")

                        print(f"\n[ENTITIES] ({len(storage.entities)} found)")
                        for i, entity in enumerate(storage.entities):
                            pos = entity.transform.position
                            print(f"  [{i}] EntityInstance(index={entity.index}, size={entity.size})")
                            print(f"       Position: ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")
                            print(f"       Identity Rotation: {entity.transform.is_identity_rotation}")
                            print(f"       {entity.transform}")
                            if entity.tree_links:
                                print(f"       Tree Links (RB-Tree nodes):")
                                for link in entity.tree_links:
                                    color = "BLACK" if link.child_ptr == -1 else "RED?"
                                    print(f"         - {link} [{color}]")
                                    
                                    
                            if not ussage_dict.get(find_first_ascii_string(data)):
                                ussage_dict[find_first_ascii_string(data)] = 1
                            else:
                                ussage_dict[find_first_ascii_string(data)] += 1
                            
                                
                            with open("test.txt", "a") as f:
                                f.write(f"UNK_FP_{file_path} - {find_first_ascii_string(data)}\n") # FILE PATH AND FIRST ASCII STRING
                                f.write(f"EN_P_{pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}\n") # ENTITY POS
                                f.write(f"{entity.transform}\n\n") # ENTITY MATRIX
                                f.write("--------------------------\n")
                            

                        # Print hex dump for reference
                        #parser.print_hex_dump(0, len(data))

                        print("\n" + "=" * 70)
                        print("Analysis Complete")
                        print("=" * 70)
                    
                    else:
                        if not ussage_dict_nonparseable.get(find_first_ascii_string(data)):
                                ussage_dict_nonparseable[find_first_ascii_string(data)] = 1
                        else:
                                ussage_dict_nonparseable[find_first_ascii_string(data)] += 1
    print(ussage_dict)
    print(ussage_dict_nonparseable)
    print("PARSEABLE: ", counter_parseable)
    print("FULL: ", counter_full)
    
    with open("test.txt", "a") as f:
        f.write(f"ENTITY TYPES: {ussage_dict}\n")
        f.write(f"UNPARSED TYPES: {ussage_dict_nonparseable}\n")
        f.write(f"PARSEABLE COUNT: {counter_parseable}\n")
        f.write(f"FULL COUNT: {counter_full}\n")
        f.write(f"PARSEABLE %: {counter_parseable/counter_full*100}%\n")


if __name__ == "__main__":
    main()