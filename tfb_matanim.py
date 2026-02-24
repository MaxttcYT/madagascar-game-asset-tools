"""
Toys for Bob UV Animation Plugin Parser (0x800000F6)
Madagascar (2005) - RenderWare Custom Extension

This plugin handles animated materials like:
- Water (UV scrolling, brightness pulsing)
- Treadmills/conveyors (brightness/scale)
"""

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import List


class EffectType(IntEnum):
    UV_SCROLL = 5
    BRIGHTNESS = 8


class PulseMode(IntEnum):
    NO_PULSE = 0
    PULSE = 1
    UNKNOWN = 2


@dataclass
class TFBUvAnimPlugin:
    """Toys for Bob UV Animation Plugin (0x800000F6)"""

    # Header
    magic: int              # 0x000D
    flags: int              # 0x0F0F

    # Config
    has_animation: int      # 01=static(33b), 03=animated(65b)
    sub_type: int           # 00=brightness, 02=uvScroll
    layer_count: int        # 0-3
    unknown1: int           # 0 or 2
    effect_type: int        # 5=UV, 8=Brightness

    # Animation params (only if has_animation == 3)
    scroll_params: List[float]  # UV scroll speeds per layer (X,Y pairs)
    intensity: float            # ~0.87
    speed: float                # ~0.5
    brightness: float           # For effect type 8

    # Trailing
    pulse_mode: int         # 00=no pulse, 01=pulse, 02=unknown

    # Section info
    section_size: int
    rw_version: int


def parse_tfb_uvanim(data: bytes) -> TFBUvAnimPlugin:
    """
    Parse TFB UV Anim plugin from bytes.

    Args:
        data: Raw bytes (with or without 12-byte section header)

    Returns:
        Parsed TFBUvAnimPlugin dataclass
    """

    offset = 0
    section_size = 0
    rw_version = 0

    # Check if starts with section header (0x800000F6)
    if len(data) >= 12:
        section_id = struct.unpack_from('<I', data, 0)[0]
        if section_id == 0x800000F6:
            section_size = struct.unpack_from('<I', data, 4)[0]
            rw_version = struct.unpack_from('<I', data, 8)[0]
            offset = 12

    # Parse header
    magic = struct.unpack_from('<H', data, offset)[0]
    flags = struct.unpack_from('<H', data, offset + 2)[0]

    # Config bytes
    has_animation = data[offset + 4]
    sub_type = data[offset + 5]
    # 2 bytes padding at offset + 6

    layer_count = struct.unpack_from('<I', data, offset + 8)[0]
    unknown1 = struct.unpack_from('<I', data, offset + 12)[0]
    effect_type = struct.unpack_from('<I', data, offset + 16)[0]

    # Initialize optional fields
    scroll_params = []
    intensity = 0.0
    speed = 0.0
    brightness = 0.0
    pulse_mode = 0

    if has_animation == 0x03:
        # Animated version (65 bytes of data)
        float_offset = offset + 20

        if effect_type == EffectType.UV_SCROLL:
            # Read scroll params based on layer count
            num_floats = min(layer_count * 2, 6)  # Max 3 layers * 2
            for i in range(num_floats):
                val = struct.unpack_from('<f', data, float_offset + i * 4)[0]
                scroll_params.append(val)

            # Intensity and speed after scroll params
            base = float_offset + 24  # After max 6 floats
            if base + 8 <= len(data):
                intensity = struct.unpack_from('<f', data, base)[0]
                speed = struct.unpack_from('<f', data, base + 4)[0]

        elif effect_type == EffectType.BRIGHTNESS:
            brightness = struct.unpack_from('<f', data, float_offset)[0]

        # Trailing byte at end
        if offset + 64 < len(data):
            pulse_mode = data[offset + 64]

    else:
        # Static version (33 bytes of data)
        # Trailing byte at end
        if offset + 32 < len(data):
            pulse_mode = data[offset + 32]

    return TFBUvAnimPlugin(
        magic=magic,
        flags=flags,
        has_animation=has_animation,
        sub_type=sub_type,
        layer_count=layer_count,
        unknown1=unknown1,
        effect_type=effect_type,
        scroll_params=scroll_params,
        intensity=intensity,
        speed=speed,
        brightness=brightness,
        pulse_mode=pulse_mode,
        section_size=section_size,
        rw_version=rw_version
    )


def write_tfb_uvanim(plugin: TFBUvAnimPlugin, include_header: bool = True) -> bytes:
    """
    Serialize TFBUvAnimPlugin back to bytes.

    Args:
        plugin: The plugin data to serialize
        include_header: Whether to include the 12-byte section header

    Returns:
        Serialized bytes
    """

    data = bytearray()

    # Section header
    if include_header:
        data += struct.pack('<I', 0x800000F6)  # Section ID
        # Size will be filled in later
        size_offset = len(data)
        data += struct.pack('<I', 0)  # Placeholder
        data += struct.pack('<I', plugin.rw_version or 0x1C020016)

    data_start = len(data)

    # Plugin header
    data += struct.pack('<H', plugin.magic or 0x000D)
    data += struct.pack('<H', plugin.flags or 0x0F0F)

    # Config
    data += bytes([plugin.has_animation, plugin.sub_type, 0, 0])

    data += struct.pack('<I', plugin.layer_count)
    data += struct.pack('<I', plugin.unknown1)
    data += struct.pack('<I', plugin.effect_type)

    if plugin.has_animation == 0x03:
        # Animated version - 65 bytes total

        if plugin.effect_type == EffectType.UV_SCROLL:
            # Write scroll params (pad to 6 floats)
            for i in range(6):
                if i < len(plugin.scroll_params):
                    data += struct.pack('<f', plugin.scroll_params[i])
                else:
                    data += struct.pack('<f', 0.0)

            # Intensity and speed
            data += struct.pack('<f', plugin.intensity)
            data += struct.pack('<f', plugin.speed)

            # Padding to reach 64 bytes of data
            while len(data) - data_start < 64:
                data += struct.pack('<f', 0.0)

        elif plugin.effect_type == EffectType.BRIGHTNESS:
            # Brightness value
            data += struct.pack('<f', plugin.brightness)

            # Padding to reach 64 bytes of data
            while len(data) - data_start < 64:
                data += struct.pack('<f', 0.0)

        else:
            # Unknown effect type - pad with zeros
            while len(data) - data_start < 64:
                data += struct.pack('<f', 0.0)

        # Trailing byte
        data += bytes([plugin.pulse_mode])

    else:
        # Static version - 33 bytes total
        # Pad to 32 bytes
        while len(data) - data_start < 32:
            data += bytes([0])

        # Trailing byte
        data += bytes([plugin.pulse_mode])

    # Update size in header
    if include_header:
        data_size = len(data) - data_start
        struct.pack_into('<I', data, size_offset, data_size)

    return bytes(data)


def format_plugin(p: TFBUvAnimPlugin) -> str:
    """Pretty print the plugin data."""

    effect_name = EffectType(p.effect_type).name if p.effect_type in (5, 8) else f'UNKNOWN({p.effect_type})'
    pulse_name = PulseMode(p.pulse_mode).name if p.pulse_mode <= 2 else f'UNKNOWN({p.pulse_mode})'

    lines = [
        "TFB UV Anim Plugin (0x800000F6)",
        "=" * 40,
        f"Magic: 0x{p.magic:04X}  Flags: 0x{p.flags:04X}",
        f"Has Animation: {p.has_animation} ({'animated' if p.has_animation == 3 else 'static'})",
        f"Sub Type: {p.sub_type} ({'UV scroll' if p.sub_type == 2 else 'brightness'})",
        f"Layer Count: {p.layer_count}",
        f"Unknown1: {p.unknown1}",
        f"Effect Type: {p.effect_type} ({effect_name})",
    ]

    if p.scroll_params:
        lines.append(f"Scroll Params:")
        for i in range(0, len(p.scroll_params), 2):
            x = p.scroll_params[i] if i < len(p.scroll_params) else 0
            y = p.scroll_params[i+1] if i+1 < len(p.scroll_params) else 0
            lines.append(f"  Layer {i//2 + 1}: X={x:.4f}, Y={y:.4f}")

    if p.intensity:
        lines.append(f"Intensity: {p.intensity:.4f}")
    if p.speed:
        lines.append(f"Speed: {p.speed:.4f}")
    if p.brightness:
        lines.append(f"Brightness: {p.brightness:.4f}")

    lines.append(f"Pulse Mode: {p.pulse_mode} ({pulse_name})")

    if p.section_size:
        lines.append(f"Section Size: {p.section_size} bytes")
        lines.append(f"RW Version: 0x{p.rw_version:08X}")

    return "\n".join(lines)


def parse_hex(hex_string: str) -> bytes:
    """Convert hex string to bytes."""
    return bytes.fromhex(hex_string.replace(" ", "").replace("\n", ""))


# Test with samples
if __name__ == "__main__":
    samples = {
        "Water (3-layer scroll, moves bottom-left)":
            "F6 00 00 80 41 00 00 00 16 00 02 1C "
            "0D 00 0F 0F 03 02 00 00 03 00 00 00 02 00 00 00 05 00 00 00 "
            "0A D7 23 3C 0A D7 23 3C 0A D7 A3 3C CD CC 4C 3D CD CC 4C 3D CD CC CC 3D "
            "52 B8 5E 3F 00 00 00 3F "
            "00 00 00 00 00 00 00 00 00 00 00 00 00",

        "Water (1-layer, 1.1f intensity, pulses)":
            "F6 00 00 80 41 00 00 00 16 00 02 1C "
            "0D 00 0F 0F 03 02 00 00 01 00 00 00 02 00 00 00 05 00 00 00 "
            "00 00 00 00 CD CC 8C 3F 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 01",

        "Treadmill (brightness 1.5)":
            "F6 00 00 80 41 00 00 00 16 00 02 1C "
            "0D 00 0F 0F 03 00 00 00 00 00 00 00 00 00 00 00 08 00 00 00 "
            "00 00 00 00 00 00 C0 3F "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "00 00 00 00 00",

        "Static (no animation)":
            "F6 00 00 80 21 00 00 00 16 00 02 1C "
            "0D 00 0F 0F 01 02 00 00 03 00 00 00 02 00 00 00 05 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00",

        "Opaque (brightness type, static)":
            "F6 00 00 80 21 00 00 00 16 00 02 1C "
            "0D 00 0F 0F 01 00 00 00 00 00 00 00 00 00 00 00 08 00 00 00 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00",
    }

    print("=" * 60)
    print("TFB UV Anim Plugin Parser - Madagascar (2005)")
    print("=" * 60)

    for name, hex_data in samples.items():
        print(f"\n### {name} ###\n")
        data = parse_hex(hex_data)
        plugin = parse_tfb_uvanim(data)
        print(format_plugin(plugin))

        # Test round-trip
        rewritten = write_tfb_uvanim(plugin, include_header=True)
        original = data[:len(rewritten)]
        if rewritten == original:
            print("\n[Round-trip: OK]")
        else:
            print(f"\n[Round-trip: MISMATCH]")
            print(f"  Original:  {original.hex()}")
            print(f"  Rewritten: {rewritten.hex()}")

        print()
