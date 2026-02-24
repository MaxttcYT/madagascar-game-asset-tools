import struct
import uuid
import json
import subprocess
import os
import copy
from pathlib import Path
from rich.pretty import Pretty
from rich.console import Console


# ===================================================================
# VGMSTREAM-INSPIRED AUDIO STREAM CLASS (Ported from C)
# ===================================================================
# Represents an audio stream with validation, state management, and cleanup
# Based on vgmstream's VGMSTREAM structure and initialization logic

class AudioStream:
    """Python equivalent of vgmstream's VGMSTREAM structure"""
    
    # Constants (from vgmstream.h)
    VGMSTREAM_MAX_CHANNELS = 32
    VGMSTREAM_MAX_NUM_SAMPLES = 0x7FFFFFFF  # 2^31 - 1
    VGMSTREAM_MIN_SAMPLE_RATE = 8000
    VGMSTREAM_MAX_SAMPLE_RATE = 384000
    VGMSTREAM_MAX_SUBSONGS = 100000
    
    def __init__(self, channels: int = 1, loop_flag: bool = False):
        """Initialize an audio stream (equivalent to allocate_vgmstream)"""
        if channels <= 0 or channels > self.VGMSTREAM_MAX_CHANNELS:
            raise ValueError(f"Invalid channels: {channels} (max {self.VGMSTREAM_MAX_CHANNELS})")
        
        # Main audio parameters
        self.channels = channels
        self.sample_rate = 0
        self.num_samples = 0
        self.loop_flag = loop_flag
        self.loop_start_sample = 0
        self.loop_end_sample = 0
        self.loop_target = 0
        
        # Codec/layout info
        self.coding_type = None
        self.layout_type = None
        self.meta_type = None
        self.codec_data = None
        self.layout_data = None
        
        # Interleave settings
        self.interleave_block_size = 0
        self.interleave_last_block_size = 0
        self.interleave_first_block_size = 0
        self.interleave_first_skip = 0
        
        # Playback control
        self.stream_index = 0
        self.num_streams = 1
        self.channel_layout = 0
        self.frame_size = 0
        self.allow_dual_stereo = False
        
        # RWS-specific
        self.block_size = 0
        self.usable_size = 0
        self.data_start = 0
        
        # State tracking for seeking/reset capability
        self.start_state = None  # Snapshot of initial state
    
    def prepare(self) -> bool:
        """Validate stream parameters before playback (based on vgmstream's prepare_vgmstream)"""
        
        # Check num_samples validity
        if self.num_samples <= 0:
            print(f"ERROR: Invalid num_samples {self.num_samples} (must be > 0)")
            return False
        
        if self.num_samples > self.VGMSTREAM_MAX_NUM_SAMPLES:
            print(f"ERROR: num_samples {self.num_samples} exceeds max {self.VGMSTREAM_MAX_NUM_SAMPLES}")
            return False
        
        # Check sample rate validity
        if self.sample_rate < self.VGMSTREAM_MIN_SAMPLE_RATE:
            print(f"ERROR: sample_rate {self.sample_rate} Hz below minimum {self.VGMSTREAM_MIN_SAMPLE_RATE}")
            return False
        
        if self.sample_rate > self.VGMSTREAM_MAX_SAMPLE_RATE:
            print(f"ERROR: sample_rate {self.sample_rate} Hz exceeds maximum {self.VGMSTREAM_MAX_SAMPLE_RATE}")
            return False
        
        # Validate and sanitize loops
        if self.loop_flag:
            if self.loop_end_sample <= self.loop_start_sample:
                print(f"WARNING: Invalid loop (end {self.loop_end_sample} <= start {self.loop_start_sample}), removing loop")
                self.loop_flag = False
                self.loop_start_sample = 0
                self.loop_end_sample = 0
                return True
            
            if self.loop_end_sample > self.num_samples:
                print(f"WARNING: Loop end {self.loop_end_sample} > num_samples {self.num_samples}, removing loop")
                self.loop_flag = False
                self.loop_start_sample = 0
                self.loop_end_sample = 0
                return True
            
            if self.loop_start_sample < 0:
                print(f"WARNING: Loop start {self.loop_start_sample} < 0, removing loop")
                self.loop_flag = False
                self.loop_start_sample = 0
                self.loop_end_sample = 0
                return True
        
        # Validate channel layout
        if self.channel_layout > 0:
            bit_count = 0
            for bit_pos in range(32):
                if (self.channel_layout >> bit_pos) & 1:
                    if bit_pos > 17:  # Unknown past standard layout
                        print(f"WARNING: Invalid channel_layout bit {bit_pos}, clearing")
                        self.channel_layout = 0
                        break
                    bit_count += 1
            
            if bit_count != self.channels:
                print(f"WARNING: channel_layout has {bit_count} bits but channels={self.channels}, clearing")
                self.channel_layout = 0
        
        # Validate subsong count
        if self.num_streams < 0 or self.num_streams > self.VGMSTREAM_MAX_SUBSONGS:
            print(f"ERROR: Invalid num_streams {self.num_streams}")
            return False
        
        # Clean up unused loop metadata
        if not self.loop_flag:
            self.loop_start_sample = 0
            self.loop_end_sample = 0
        
        return True
    
    def setup(self) -> None:
        """Final setup before playback (equivalent to setup_vgmstream)"""
        # Save initial state for seeking/reset capability
        self.start_state = copy.deepcopy(self.__dict__)
    
    def reset(self) -> None:
        """Reset to initial state (equivalent to reset_vgmstream)"""
        if self.start_state:
            self.__dict__ = copy.deepcopy(self.start_state)
    
    def close(self) -> None:
        """Clean up resources (equivalent to close_vgmstream)"""
        # Clean up any codec/layout data
        if self.codec_data:
            self.codec_data = None
        if self.layout_data:
            self.layout_data = None
    
    def force_loop(self, loop_flag: bool, loop_start: int, loop_end: int) -> bool:
        """Force enable/disable looping with validation"""
        
        # Validate parameters if enabling loop
        if loop_flag:
            if loop_start < 0 or loop_start > loop_end or loop_end > self.num_samples:
                print(f"ERROR: Invalid loop parameters (start={loop_start}, end={loop_end}, total={self.num_samples})")
                return False
            
            # Allocate loop state if not already present
            if not self.loop_flag and self.channels > 0:
                # Mark loop state as ready
                pass
        
        self.loop_flag = loop_flag
        if loop_flag:
            self.loop_start_sample = loop_start
            self.loop_end_sample = loop_end
        
        self.setup()  # Re-setup after loop modification
        return True
    
    def set_loop_target(self, loop_target: int) -> None:
        """Set number of loop iterations"""
        if self.loop_flag:
            self.loop_target = loop_target
            self.setup()
    
    def get_duration_seconds(self) -> float:
        """Calculate duration in seconds"""
        if self.sample_rate <= 0:
            return 0.0
        return self.num_samples / self.sample_rate
    
    def __repr__(self) -> str:
        return (f"AudioStream(channels={self.channels}, sample_rate={self.sample_rate}, "
                f"num_samples={self.num_samples}, duration={self.get_duration_seconds():.2f}s, "
                f"loop={self.loop_flag})")


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

    def readRWChunkHeader(self):
        return {
            "id": self.readUint32(),
            "size": self.readUint32(),
            "version": self.readUint32(),
        }


class RWSHeader:
    """Represents the RWS audio header structure"""
    def __init__(self):
        self.big_endian = False
        
        self.codec = 0
        self.channels = 0
        self.sample_rate = 0
        self.interleave = 0
        self.frame_size = 0
        
        self.file_name_offset = 0
        
        self.total_segments = 0
        self.target_segment = 0
        self.segment_offset = 0
        self.segment_layers_size = 0
        self.segment_name_offset = 0
        
        self.total_layers = 0
        self.target_layer = 0
        self.layer_start = 0
        
        self.file_size = 0
        self.header_size = 0
        self.data_size = 0
        self.data_offset = 0
        
        self.usable_size = 0
        self.block_size = 0
        self.block_layers_size = 0
        
        self.coefs_offset = 0
        self.hist_offset = 0
        
        self.readable_name = ""


def get_rws_string_size(p: Parser, offset: int) -> int:
    """RWS strings are null-terminated then padded to 0x10"""
    p.seek(offset)
    i = 0
    while i < 255:  # arbitrary max
        if p.readUint8() == 0:  # null terminator
            return i + (0x10 - (i % 0x10))  # size is padded
        i += 1
    return 0


def get_rws_string_size_from_data(data: bytes, offset: int) -> int:
    """RWS strings are null-terminated then padded to 0x10 - works directly on bytes"""
    i = 0
    while i < 255:  # arbitrary max
        if data[offset + i] == 0:  # null terminator
            return i + (0x10 - (i % 0x10))  # size is padded
        i += 1
    return 0


def guess_endian32(p: Parser, offset: int) -> bool:
    """Guess endianness based on a value at offset (returns True for big endian)"""
    p.seek(offset)
    val = p.readUint32()
    # Simple heuristic: if high byte is set and it's a reasonable sample rate
    if (val & 0xFF000000) != 0:
        return True
    return False


def readRWS(data, target_subsong=0):
    """Parse RWS audio file format - matching C code implementation"""
    p = Parser(data, endian="little")
    output = {}
    
    # File header structure: id (4), size (4), version (4)
    file_id = p.readUint32()
    file_size = p.readUint32()
    file_version = p.readUint32()  # RW version
    
    if file_id != 0x0000080d:
        print("NOT A VALID RWS AUDIO FILE!")
        return None
    
    output["file_header"] = {
        "file_id": hex(file_id),
        "file_size": file_size,
        "file_version": hex(file_version),
    }
    
    if file_size + 0x0c != len(data):
        print("GIVEN DATA IS SMALLER THAN IN HEADER DEFINED!")
        return None
    
    # Header chunk structure: id (4), size (4), version (4)
    header_chunk_id = p.readUint32()
    header_size = p.readUint32()
    header_version = p.readUint32()
    
    if header_chunk_id != 0x0000080e:
        print(f"Invalid header chunk ID! Got {hex(header_chunk_id)}, expected 0x0000080e")
        return None
    
    rws = RWSHeader()
    rws.file_size = file_size
    rws.header_size = header_size
    
    # Data chunk location: 0x0c (file header) + 0x0c (header chunk header) + header_size
    data_offset = 0x0c + 0x0c + header_size
    p.seek(data_offset)
    
    # Data chunk structure: id (4), size (4), version (4)
    data_chunk_id = p.readUint32()
    data_size = p.readUint32()
    data_version = p.readUint32()
    
    if data_chunk_id != 0x0000080f:
        print(f"Invalid data chunk ID! Got {hex(data_chunk_id)}, expected 0x0000080f")
        return None
    
    if data_size + 0x0c + data_offset != len(data):
        print("Data chunk size mismatch!")
        return None
    
    rws.data_offset = data_offset
    rws.data_size = data_size
    
    output["file_header"]["data_offset"] = data_offset
    output["file_header"]["data_size"] = data_size
    
    # Parse header chunk data (starts at 0x18)
    # Read directly from data to track offsets correctly
    offset = 0x18
    
    # Guess endianness from base header at offset+0x00
    test_val = struct.unpack_from('<I', data, offset)[0]
    rws.big_endian = (test_val & 0xFF000000) != 0
    
    if rws.big_endian:
        p.endian = ">"
        read_u32 = lambda off: struct.unpack_from('>I', data, off)[0]
        read_u16 = lambda off: struct.unpack_from('>H', data, off)[0]
        read_u8 = lambda off: struct.unpack_from('>B', data, off)[0]
    else:
        p.endian = "<"
        read_u32 = lambda off: struct.unpack_from('<I', data, off)[0]
        read_u16 = lambda off: struct.unpack_from('<H', data, off)[0]
        read_u8 = lambda off: struct.unpack_from('<B', data, off)[0]
    
    # Base header (0x50 bytes)
    rws.total_segments = read_u32(offset + 0x20)
    rws.total_layers = read_u32(offset + 0x28)
    offset += 0x50
    
    # Audio file name (null-terminated, padded to 0x10)
    rws.file_name_offset = offset
    offset += get_rws_string_size_from_data(data, offset)
    
    # Set target subsong
    if target_subsong == 0:
        target_subsong = 1
    
    rws.target_layer = ((target_subsong - 1) % rws.total_layers) + 1
    rws.target_segment = ((target_subsong - 1) // rws.total_layers) + 1
    total_subsongs = rws.total_layers * rws.total_segments
    
    if target_subsong < 0 or target_subsong > total_subsongs or total_subsongs < 1:
        print(f"Invalid subsong: {target_subsong} / {total_subsongs}")
        return None
    
    output["subsong_info"] = {
        "target_subsong": target_subsong,
        "total_subsongs": total_subsongs,
        "target_layer": rws.target_layer,
        "target_segment": rws.target_segment,
        "total_layers": rws.total_layers,
        "total_segments": rws.total_segments,
    }
    
    # Segment info (0x20 bytes per segment)
    for i in range(rws.total_segments):
        if i + 1 == rws.target_segment:
            rws.segment_layers_size = read_u32(offset + 0x18)
            rws.segment_offset = read_u32(offset + 0x1c)
        offset += 0x20
    
    # Usable layer sizes (0x04 bytes per layer*segment)
    for i in range(rws.total_segments * rws.total_layers):
        usable_size = read_u32(offset)
        if i + 1 == target_subsong:
            rws.usable_size = usable_size
        offset += 0x04
    
    # Segment UUIDs (0x10 bytes per segment)
    offset += 0x10 * rws.total_segments
    
    # Segment names (variable size, padded to 0x10)
    for i in range(rws.total_segments):
        if i + 1 == rws.target_segment:
            rws.segment_name_offset = offset
        offset += get_rws_string_size_from_data(data, offset)
    
    # Layer info (0x28 bytes per layer)
    for i in range(rws.total_layers):
        if i + 1 == rws.target_layer:
            rws.interleave = read_u16(offset + 0x18)
            rws.frame_size = read_u16(offset + 0x1a)
            rws.block_size = read_u32(offset + 0x20)
            rws.layer_start = read_u32(offset + 0x24)
        
        # Track block_layers_size for all layers
        block_size_pad = read_u32(offset + 0x10)
        rws.block_layers_size += block_size_pad
        offset += 0x28
    
    # Layer config (0x2c bytes base per layer)
    for i in range(rws.total_layers):
        if i + 1 == rws.target_layer:
            rws.sample_rate = read_u32(offset + 0x00)
            rws.channels = read_u8(offset + 0x0d)
            rws.codec = read_u32(offset + 0x1c)
        
        layer_codec = read_u32(offset + 0x1c)
        offset += 0x2c
        
        # DSP has extra 0x60 bytes
        if layer_codec == 0xF86215B0:
            if i + 1 == rws.target_layer:
                rws.coefs_offset = offset + 0x1c
                rws.hist_offset = offset + 0x40
            offset += 0x60
        
        offset += 0x04  # padding
    
    # Calculate total samples based on codec type
    stream_size = rws.usable_size
    num_samples = calculate_samples(rws.codec, stream_size, rws.channels)
    
    # Build readable name
    file_name = data[rws.file_name_offset:rws.file_name_offset+256].split(b'\x00')[0].decode('utf-8', errors='ignore')
    segment_name = data[rws.segment_name_offset:rws.segment_name_offset+256].split(b'\x00')[0].decode('utf-8', errors='ignore')
    
    if rws.total_layers > 1:
        layer_name = data[rws.layer_name_offset:rws.layer_name_offset+256].split(b'\x00')[0].decode('utf-8', errors='ignore')
        readable_name = f"{file_name}/{segment_name}/{layer_name}"
    else:
        readable_name = f"{file_name}/{segment_name}"
    
    # Build output
    data_start = rws.data_offset + 0x0c + (rws.segment_offset + rws.layer_start)
    output["audio_info"] = {
        "codec": hex(rws.codec),
        "channels": rws.channels,
        "sample_rate": rws.sample_rate,
        "total_samples": num_samples,
        "duration_seconds": num_samples / rws.sample_rate if rws.sample_rate > 0 else 0,
        "interleave": rws.interleave,
        "frame_size": rws.frame_size,
        "block_size": rws.block_size,
        "usable_size": rws.usable_size,
        "segment_offset": rws.segment_offset,
        "layer_start": rws.layer_start,
        "segment_layers_size": rws.segment_layers_size,
        "data_start": data_start,
    }
    
    output["codec_info"] = get_codec_name(rws.codec)
    output["stream_name"] = readable_name
    
    # Create and validate AudioStream (vgmstream-style)
    try:
        stream = AudioStream(channels=rws.channels, loop_flag=False)
        stream.sample_rate = rws.sample_rate
        stream.num_samples = num_samples
        stream.coding_type = get_codec_name(rws.codec)
        stream.block_size = rws.block_size
        stream.usable_size = rws.usable_size
        stream.data_start = data_start
        stream.interleave_block_size = rws.interleave
        stream.frame_size = rws.frame_size
        
        # Validate stream parameters (prepare_vgmstream equivalent)
        if not stream.prepare():
            print("WARNING: Stream validation failed, but continuing with caution")
        
        # Setup for seeking/reset capability
        stream.setup()
        output["audio_stream"] = stream
        output["stream_validated"] = True
        
    except Exception as e:
        print(f"WARNING: Could not create validated AudioStream: {e}")
        output["stream_validated"] = False
    
    return output


def calculate_samples(codec: int, stream_size: int, channels: int) -> int:
    """Calculate total samples from stream size based on codec type"""
    if codec == 0xD01BD217:  # PCM
        # PCM16 = 2 bytes per sample per channel
        return stream_size // (2 * channels)
    elif codec == 0xD9EA9798:  # PS-ADPCM
        # PS ADPCM = 16 samples per 16 bytes per channel
        return (stream_size // channels) * 2
    elif codec == 0xF86215B0:  # DSP ADPCM
        # DSP = 14 samples per 8 bytes per channel
        bytes_per_channel = stream_size // channels
        return (bytes_per_channel // 8) * 14
    elif codec == 0xEF386593 or codec == 0x632FA22B:  # IMA ADPCM (PC or Xbox)
        # IMA ADPCM = 4-bit = 2 samples per byte
        return stream_size * 2
    else:
        # Fallback: assume some generic ratio
        return stream_size


def get_codec_name(codec: int) -> str:
    """Return codec name from UUID"""
    codec_map = {
        0xD9EA9798: "PS-ADPCM",
        0xD01BD217: "PCM",
        0xDA1E4382: "Float",
        0xF86215B0: "DSP ADPCM",
        0x632FA22B: "Xbox IMA ADPCM",
        0x3F1D8147: "WMA",
        0xBACFB36E: "MP3",
        0x34D09A54: "MP2",
        0x04C15BA7: "MP1",
        0xA30DB390: "AC3",
        0xEF386593: "IMA ADPCM (PC)",
    }
    return codec_map.get(codec, f"Unknown ({hex(codec)})")


def create_wav_header(rws_info: dict, audio_data: bytes) -> bytes:
    """Create a proper WAV file header for IMA ADPCM audio (based on vgmstream's output)"""
    
    audio_info = rws_info["audio_info"]
    
    sample_rate = audio_info["sample_rate"]
    channels = audio_info["channels"]
    num_samples = audio_info["total_samples"]
    codec = audio_info["codec"]  # hex string like "0xef386593"
    block_size = audio_info["block_size"]
    frame_size = audio_info["frame_size"]
    
    # WAV format codes
    WAVE_FORMAT_IMA_ADPCM = 0x0011
    WAVE_FORMAT_PCM = 0x0001
    
    # Determine format based on codec
    if codec == "0xef386593" or codec == "0x632fa22b":  # IMA ADPCM (PC or Xbox)
        wave_format = WAVE_FORMAT_IMA_ADPCM
        bits_per_sample = 4
        
        # For IMA ADPCM: samples per block = (block_size - 4*channels) * 8 / (4*channels) + 1
        # Simplified: ((block_size - 4*channels) * 2) / channels + 1
        samples_per_block = ((block_size - 4 * channels) * 2) // channels + 1
        
    elif codec == "0xd01bd217":  # PCM
        wave_format = WAVE_FORMAT_PCM
        bits_per_sample = 16
        samples_per_block = 1
        
    else:
        # Fallback to PCM if unknown
        wave_format = WAVE_FORMAT_PCM
        bits_per_sample = 16
        samples_per_block = 1
    
    # Calculate byte rate (average bytes per second)
    byte_rate = (sample_rate * channels * bits_per_sample) // 8
    block_align = frame_size if frame_size > 0 else (channels * bits_per_sample) // 8
    
    # Build fmt chunk
    fmt_data = struct.pack("<HHIIHH",
        wave_format,           # Audio format (0x0011 for IMA ADPCM)
        channels,              # Number of channels
        sample_rate,           # Sample rate
        byte_rate,             # Bytes per second
        block_align,           # Block align (bytes per sample block)
        bits_per_sample        # Bits per sample
    )
    
    # Add cbSize and samplesPerBlock for IMA ADPCM
    if wave_format == WAVE_FORMAT_IMA_ADPCM:
        fmt_data += struct.pack("<HH",
            2,                 # cbSize (size of extra format info)
            samples_per_block  # samplesPerBlock
        )
    
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_data)) + fmt_data
    
    # Build data chunk
    data_chunk = b"data" + struct.pack("<I", len(audio_data)) + audio_data
    
    # Calculate RIFF size (everything after the "RIFF xxxx" part)
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)  # 4 for "WAVE"
    
    # Build RIFF header
    riff_header = b"RIFF" + struct.pack("<I", riff_size) + b"WAVE"
    
    return riff_header + fmt_chunk + data_chunk


def decode_rws_audio(rws_file: str, rws_info: dict, output_format: str = "wav"):
    """Extract RWS audio data to WAV file with proper format headers"""
    try:
        with open(rws_file, "rb") as f:
            data = f.read()
        
        # Check if stream was validated
        if not rws_info.get("stream_validated", False):
            print("[!] WARNING: Audio stream validation failed during parsing")
        
        audio_stream = rws_info.get("audio_stream")
        audio_info = rws_info["audio_info"]
        stream_name = rws_info.get("stream_name", "output")
        
        # Create output directory
        output_dir = Path("extracted_audio")
        output_dir.mkdir(exist_ok=True)
        
        # Create safe filename
        safe_name = "".join(c for c in stream_name if c.isalnum() or c in "/_-").replace("/", "_")
        
        # Extract raw audio data
        data_start = audio_info["data_start"]
        usable_size = audio_info["usable_size"]
        
        print(f"\n[*] Extracting audio data...")
        print(f"    Start offset: 0x{data_start:x}")
        print(f"    Size: {usable_size} bytes ({usable_size / 1024:.2f} KB)")
        print(f"    Codec: {rws_info['codec_info']}")
        print(f"    Sample Rate: {audio_info['sample_rate']} Hz")
        print(f"    Channels: {audio_info['channels']}")
        print(f"    Block Size: {audio_info['block_size']} bytes")
        print(f"    Frame Size: {audio_info['frame_size']} bytes")
        print(f"    Total Samples: {audio_info['total_samples']}")
        print(f"    Duration: {audio_info['duration_seconds']:.3f} seconds")
        
        # Validate stream if available
        if audio_stream:
            print(f"    [Audio Stream] {audio_stream}")
            print(f"    [Stream State] Validated and ready for playback")
        
        audio_data = data[data_start:data_start + usable_size]
        
        # Create WAV file
        if output_format.lower() == "wav":
            wav_file = output_dir / f"{safe_name}.wav"
            wav_data = create_wav_header(rws_info, audio_data)
            
            with open(wav_file, "wb") as f:
                f.write(wav_data)
            
            print(f"\n[SUCCESS] Audio extracted to WAV!")
            print(f"    Output: {wav_file}")
            print(f"    File Size: {len(wav_data) / 1024:.2f} KB")
            output_file = wav_file
        else:
            # Fallback to raw format
            raw_file = output_dir / f"{safe_name}.ima"
            with open(raw_file, "wb") as f:
                f.write(audio_data)
            
            print(f"\n[SUCCESS] Audio data extracted (raw)!")
            print(f"    Output: {raw_file}")
            print(f"    Size: {len(audio_data) / 1024:.2f} KB")
            output_file = raw_file
        
        # Create a metadata file
        meta_file = output_dir / f"{safe_name}.txt"
        with open(meta_file, "w") as f:
            f.write("RWS Audio Extraction Metadata\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Stream Name: {stream_name}\n")
            f.write(f"Codec: {rws_info['codec_info']} ({rws_info['audio_info']['codec']})\n")
            f.write(f"Sample Rate: {audio_info['sample_rate']} Hz\n")
            f.write(f"Channels: {audio_info['channels']}\n")
            f.write(f"Total Samples: {audio_info['total_samples']}\n")
            f.write(f"Duration: {audio_info['duration_seconds']:.3f} seconds\n")
            f.write(f"Block Size: {audio_info['block_size']} bytes\n")
            f.write(f"Frame Size: {audio_info['frame_size']} bytes\n")
            f.write(f"Raw Data Size: {len(audio_data)} bytes\n")
            
            # Add stream validation status
            if audio_stream:
                f.write(f"\nStream Validation: PASSED\n")
                f.write(f"  - Channels: {audio_stream.channels} (max {audio_stream.VGMSTREAM_MAX_CHANNELS})\n")
                f.write(f"  - Sample Rate: {audio_stream.sample_rate} Hz (min {audio_stream.VGMSTREAM_MIN_SAMPLE_RATE}, max {audio_stream.VGMSTREAM_MAX_SAMPLE_RATE})\n")
                f.write(f"  - Num Samples: {audio_stream.num_samples} (max {audio_stream.VGMSTREAM_MAX_NUM_SAMPLES})\n")
                f.write(f"  - Duration: {audio_stream.get_duration_seconds():.3f} seconds\n")
            else:
                f.write(f"\nStream Validation: NOT AVAILABLE\n")
            
            f.write(f"\nOutput File: {output_file.name}\n")
            if output_format.lower() == "wav":
                f.write(f"Format: WAV (RIFF) with IMA ADPCM encoding\n")
            else:
                f.write(f"Format: Raw audio data\n")
        
        print(f"    Metadata: {meta_file}")
        return True
            
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    with open("banquetAudioStreamUS.rws", "rb") as f:
        result = readRWS(f.read())
        if result:
            console = Console(force_terminal=True)
            console.print(Pretty(result, expand_all=True))
            
            # Extract and decode audio
            decode_rws_audio("banquetAudioStreamUS.rws", result, output_format="wav")
