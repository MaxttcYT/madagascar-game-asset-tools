import struct

def read_string_size(data, offset):
    """RWS strings are null-terminated then padded to 0x10"""
    i = 0
    while i < 255:
        if data[offset + i] == 0:
            return i + (0x10 - (i % 0x10))
        i += 1
    return 0

with open('banquetAudioStreamUS.rws', 'rb') as f:
    data = f.read()

# Parse header
file_id = struct.unpack_from('<I', data, 0x00)[0]
file_size = struct.unpack_from('<I', data, 0x04)[0]
file_version = struct.unpack_from('<I', data, 0x08)[0]

print(f"File ID: {hex(file_id)}")
print(f"File Size: {file_size}")
print(f"File Version: {hex(file_version)}")

# Parse header chunk
header_chunk_id = struct.unpack_from('<I', data, 0x0c)[0]
header_size = struct.unpack_from('<I', data, 0x10)[0]
header_version = struct.unpack_from('<I', data, 0x14)[0]

print(f"\nHeader Chunk ID: {hex(header_chunk_id)}")
print(f"Header Size: {header_size}")
print(f"Header Version: {hex(header_version)}")

# Parse data chunk
data_offset = 0x0c + 0x0c + header_size
data_chunk_id = struct.unpack_from('<I', data, data_offset)[0]
data_size = struct.unpack_from('<I', data, data_offset + 0x04)[0]
data_version = struct.unpack_from('<I', data, data_offset + 0x08)[0]

print(f"\nData Chunk offset: {hex(data_offset)}")
print(f"Data Chunk ID: {hex(data_chunk_id)}")
print(f"Data Size: {data_size}")
print(f"Data Version: {hex(data_version)}")

# Header chunk data starts at 0x18
offset = 0x18
print(f"\n=== Header Chunk Data ===")
print(f"Base header offset: {hex(offset)}")

# Base header
total_segments = struct.unpack_from('<I', data, offset + 0x20)[0]
total_layers = struct.unpack_from('<I', data, offset + 0x28)[0]
print(f"Total segments: {total_segments}")
print(f"Total layers: {total_layers}")

offset += 0x50
print(f"After base header: {hex(offset)}")

# Audio file name
file_name_size = read_string_size(data, offset)
print(f"\nFile name at {hex(offset)}, size: {file_name_size}")
file_name = data[offset:offset+file_name_size-0x10].rstrip(b'\x00').decode('utf-8', errors='ignore')
print(f"File name: {file_name}")
offset += file_name_size
print(f"After file name: {hex(offset)}")

# Segment info (0x20 bytes per segment)
print(f"\nSegment info starts at {hex(offset)}")
seg_info_start = offset
for i in range(min(3, total_segments)):  # Just show first 3
    seg_offset = struct.unpack_from('<I', data, offset + 0x1c)[0]
    seg_layers_size = struct.unpack_from('<I', data, offset + 0x18)[0]
    print(f"  Segment {i+1}: offset={seg_offset}, layers_size={seg_layers_size}")
    offset += 0x20

print(f"After all segment info ({total_segments} segments): {hex(offset)}")

# Usable layer sizes
print(f"\nUsable layer sizes at {hex(offset)}")
for i in range(min(5, total_segments * total_layers)):
    usable = struct.unpack_from('<I', data, offset)[0]
    print(f"  Usable {i+1}: {usable}")
    offset += 0x04

print(f"After usable sizes ({total_segments * total_layers}): {hex(offset)}")

# Segment UUIDs
print(f"\nSegment UUIDs at {hex(offset)} ({0x10 * total_segments} bytes)")
offset += 0x10 * total_segments
print(f"After segment UUIDs: {hex(offset)}")

# Segment names
print(f"\nSegment names at {hex(offset)}")
for i in range(min(3, total_segments)):
    seg_name_size = read_string_size(data, offset)
    seg_name = data[offset:offset+seg_name_size-0x10].rstrip(b'\x00').decode('utf-8', errors='ignore')
    print(f"  Segment {i+1} name: '{seg_name}' (size={seg_name_size})")
    offset += seg_name_size

print(f"After all segment names: {hex(offset)}")

# Layer info
print(f"\nLayer info at {hex(offset)}")
for i in range(total_layers):
    block_size_pad = struct.unpack_from('<I', data, offset + 0x10)[0]
    interleave = struct.unpack_from('<H', data, offset + 0x18)[0]
    frame_size = struct.unpack_from('<H', data, offset + 0x1a)[0]
    block_size = struct.unpack_from('<I', data, offset + 0x20)[0]
    layer_start = struct.unpack_from('<I', data, offset + 0x24)[0]
    print(f"  Layer {i+1}: block_size_pad={block_size_pad}, interleave={interleave}, frame_size={frame_size}, block_size={block_size}, layer_start={layer_start}")
    offset += 0x28

print(f"After layer info: {hex(offset)}")

# Layer config
print(f"\nLayer config at {hex(offset)}")
for i in range(total_layers):
    sample_rate = struct.unpack_from('<I', data, offset + 0x00)[0]
    channels = struct.unpack_from('<B', data, offset + 0x0d)[0]
    codec = struct.unpack_from('<I', data, offset + 0x1c)[0]
    print(f"  Layer {i+1}: sample_rate={sample_rate}, channels={channels}, codec={hex(codec)}")
    offset += 0x2c
    
    # Check for DSP
    if codec == 0xF86215B0:
        offset += 0x60
    
    offset += 0x04  # padding

print(f"After layer config: {hex(offset)}")
