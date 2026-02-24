import struct

def read_string_size(data, offset):
    i = 0
    while i < 255:
        if data[offset + i] == 0:
            return i + (0x10 - (i % 0x10))
        i += 1
    return 0

with open('banquetAudioStreamUS.rws', 'rb') as f:
    data = f.read()

# After segment UUIDs
offset = 0x553c
print(f'Segment names start at: {hex(offset)}')

# Read all segment names
total_segments = 417
all_names_size = 0
for i in range(total_segments):
    name_size = read_string_size(data, offset)
    if i < 10:
        name = data[offset:offset+name_size].rstrip(b'\x00').decode('utf-8', errors='ignore')
        print(f'  Segment {i+1}: size={hex(name_size)}, name="{name}"')
    all_names_size += name_size
    offset += name_size
    
print(f'\nTotal segment names size: {hex(all_names_size)}')
print(f'After all {total_segments} segment names: {hex(0x553c + all_names_size)}')

# Now check layer info at that location
layer_info_offset = 0x553c + all_names_size
print(f'\nLayer info should be at: {hex(layer_info_offset)}')

# Read layer info
block_size_pad = struct.unpack_from('<I', data, layer_info_offset + 0x10)[0]
interleave = struct.unpack_from('<H', data, layer_info_offset + 0x18)[0]
frame_size = struct.unpack_from('<H', data, layer_info_offset + 0x1a)[0]
block_size = struct.unpack_from('<I', data, layer_info_offset + 0x20)[0]
layer_start = struct.unpack_from('<I', data, layer_info_offset + 0x24)[0]

print(f'\nAt {hex(layer_info_offset)} (layer info):')
print(f'  block_size_pad: {block_size_pad}')
print(f'  interleave: {interleave}')
print(f'  frame_size: {frame_size}')
print(f'  block_size: {block_size}')
print(f'  layer_start: {layer_start}')

# Layer config
layer_config_offset = layer_info_offset + 0x28
sample_rate = struct.unpack_from('<I', data, layer_config_offset + 0x00)[0]
channels = struct.unpack_from('<B', data, layer_config_offset + 0x0d)[0]
codec = struct.unpack_from('<I', data, layer_config_offset + 0x1c)[0]

print(f'\nAt {hex(layer_config_offset)} (layer config):')
print(f'  sample_rate: {sample_rate}')
print(f'  channels: {channels}')
print(f'  codec: {hex(codec)}')
