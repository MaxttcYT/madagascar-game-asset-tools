#!/usr/bin/env python3
"""
TFB Script Bytecode Decompiler - FIXED VERSION

Key fixes over original:
1. String parsing: format is length(1 byte) + data(N bytes) + 4 null/pad bytes
   (NOT alignment-based padding)
2. Improved bytecode instruction decoding with variable-length instructions
3. Better pseudo-code reconstruction with reference/symbol resolution
"""

import struct
import sys
from typing import List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TFBString:
    length: int
    value: str


@dataclass
class TFBInstruction:
    offset: int
    opcode: bytes
    operands: bytes
    mnemonic: str = ""
    comment: str = ""


class TFBScriptDecompiler:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.opcodes = []
        self.symbols = []
        self.references = []
        self.instructions = []
        self.bytecode_count = 0

    def can_read(self, num_bytes: int) -> bool:
        return self.offset + num_bytes <= len(self.data)

    def read_byte(self) -> int:
        if not self.can_read(1):
            raise EOFError(f"Cannot read byte at offset 0x{self.offset:X}")
        val = self.data[self.offset]
        self.offset += 1
        return val

    def read_uint16(self) -> int:
        if not self.can_read(2):
            raise EOFError(f"Cannot read uint16 at offset 0x{self.offset:X}")
        val = struct.unpack('<H', self.data[self.offset:self.offset + 2])[0]
        self.offset += 2
        return val

    def read_uint32(self) -> int:
        if not self.can_read(4):
            raise EOFError(f"Cannot read uint32 at offset 0x{self.offset:X}")
        val = struct.unpack('<I', self.data[self.offset:self.offset + 4])[0]
        self.offset += 4
        return val

    def read_int32(self) -> int:
        if not self.can_read(4):
            raise EOFError(f"Cannot read int32 at offset 0x{self.offset:X}")
        val = struct.unpack('<i', self.data[self.offset:self.offset + 4])[0]
        self.offset += 4
        return val

    def read_bytes(self, count: int) -> bytes:
        if not self.can_read(count):
            raise EOFError(f"Cannot read {count} bytes at offset 0x{self.offset:X}")
        val = self.data[self.offset:self.offset + count]
        self.offset += count
        return val

    def read_string(self) -> TFBString:
        """Read a TFB string: length(1 byte) + data(N bytes) + 4 null/pad bytes."""
        length = self.read_byte()
        if length == 0:
            text = ""
        else:
            string_data = self.read_bytes(length)
            text = string_data.decode('ascii', errors='replace')
        self.read_bytes(4)
        return TFBString(length, text)

    def parse_header(self) -> dict:
        version = self.read_byte()
        magic = self.read_bytes(10).decode('ascii', errors='replace').rstrip('\x00')
        header_size = self.read_uint32()
        return {'version': version, 'magic': magic, 'header_size': header_size}

    def parse_string_table(self, label: str) -> List[TFBString]:
        count = self.read_uint32()
        if count > 10000:
            raise ValueError(f"{label} table count {count} unreasonably large at 0x{self.offset-4:X}")
        entries = []
        for _ in range(count):
            entries.append(self.read_string())
        return entries

    def parse_bytecode(self) -> List[TFBInstruction]:
        self.bytecode_count = self.read_uint32()
        bytecode_start = self.offset
        instructions = []

        while self.offset < len(self.data):
            inst_offset = self.offset - bytecode_start
            b = self.read_byte()

            if b == 0xFF:
                if not self.can_read(1):
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'INCOMPLETE'))
                    break
                b2 = self.read_byte()
                operand = self.read_bytes(4) if self.can_read(4) else b''
                opcode_bytes = bytes([b, b2])
                if b2 == 0x09 and len(operand) == 4:
                    val = struct.unpack('<I', operand)[0]
                    inst = TFBInstruction(inst_offset, opcode_bytes, operand, 'PUSH', f'{val} (0x{val:X})')
                else:
                    val = struct.unpack('<I', operand)[0] if len(operand) == 4 else 0
                    inst = TFBInstruction(inst_offset, opcode_bytes, operand, f'EXT_{b2:02X}', f'{val}')
                instructions.append(inst)

            elif b == 0x00:
                if self.can_read(1) and self.data[self.offset] == 0x08:
                    self.read_byte()
                    instructions.append(TFBInstruction(inst_offset, b'\x00\x08', b'', 'LOAD_CHECK', ''))
                elif self.can_read(1) and self.data[self.offset] == 0x0A:
                    self.read_byte()
                    operand = self.read_bytes(4) if self.can_read(4) else b''
                    val = struct.unpack('<I', operand)[0] if len(operand) == 4 else 0
                    instructions.append(TFBInstruction(inst_offset, b'\x00\x0A', operand, 'BRANCH_IF', f'offset={val}'))
                else:
                    pass

            elif b == 0x01:
                if self.can_read(1) and self.data[self.offset] == 0x01:
                    self.read_byte()
                    instructions.append(TFBInstruction(inst_offset, b'\x01\x01', b'', 'END_BLOCK', ''))
                elif self.can_read(4):
                    operand = self.read_bytes(4)
                    val = struct.unpack('<I', operand)[0]
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, 'STORE', f'{val}'))
                else:
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'OP_01'))

            elif b < len(self.opcodes) and b not in (0x00, 0x01):
                name = self.opcodes[b].value.replace('::op-code', '')
                instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'CALL', f'[{b}] "{name}"'))

            elif b == 0x02:
                if self.can_read(1):
                    idx = self.read_byte()
                    operand = bytes([idx])
                    if idx < len(self.opcodes):
                        name = self.opcodes[idx].value.replace('::op-code', '')
                        comment = f'[{idx}] "{name}"'
                    else:
                        comment = f'[{idx}]'
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, 'CALL', comment))
                else:
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'CALL', '?'))

            elif b == 0x04:
                if self.can_read(4):
                    operand = self.read_bytes(4)
                    val = struct.unpack('<i', operand)[0]
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, 'CONST', f'{val}'))
                else:
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'CONST', '?'))

            elif b == 0x08:
                if self.can_read(1):
                    arg = self.read_byte()
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), bytes([arg]), 'CMP', f'{arg}'))
                else:
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'CMP', '?'))

            elif b == 0x09:
                instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'RETURN', ''))

            elif b == 0x0A:
                if self.can_read(4):
                    operand = self.read_bytes(4)
                    val = struct.unpack('<I', operand)[0]
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, 'JUMP', f'0x{val:X}'))
                else:
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), b'', 'JUMP', '?'))

            else:
                if self.can_read(4):
                    operand = self.read_bytes(4)
                    val = struct.unpack('<I', operand)[0]
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, f'OP_{b:02X}', f'{val}'))
                else:
                    operand = self.read_bytes(len(self.data) - self.offset)
                    instructions.append(TFBInstruction(inst_offset, bytes([b]), operand, f'OP_{b:02X}', ''))

        return instructions

    def format_instruction(self, inst: TFBInstruction) -> str:
        raw = inst.opcode.hex().upper()
        if inst.operands:
            raw += ' ' + inst.operands.hex().upper()
        comment = inst.comment if inst.comment else ''
        return f"  0x{inst.offset:04X}:  {raw:<24s}  {inst.mnemonic:<14s} {comment}"

    def _get_opcode_name(self, idx: int) -> str:
        """Get clean opcode name by index, normalized to valid identifier."""
        if idx < len(self.opcodes):
            name = self.opcodes[idx].value.replace('::op-code', '')
            return name.replace(' ', '_')
        return f'opcode_{idx}'

    def _resolve_ref(self, idx: int) -> str:
        """Resolve a reference index to its name."""
        if idx < len(self.references):
            return self.references[idx].value
        return f'ref[{idx}]'

    def _resolve_symbol(self, idx: int) -> str:
        """Resolve a symbol index to its name."""
        if idx < len(self.symbols):
            return self.symbols[idx].value
        return f'symbol[{idx}]'

    def _build_block_structure(self) -> dict:
        """Pre-scan instructions to identify if/else block boundaries.

        Returns a dict mapping instruction_index -> block_type where
        block_type is one of: 'else_start', 'block_end'.
        Also detects empty IF bodies so we can invert the condition and
        emit a single block instead of an empty-if / else pair.
        """
        markers = {}
        end_blocks = [i for i, inst in enumerate(self.instructions)
                      if inst.mnemonic == 'END_BLOCK']
        cmp_indices = [i for i, inst in enumerate(self.instructions)
                       if inst.mnemonic == 'CMP']

        # Track which CMP has an empty IF body so we can invert it
        self._inverted_conditions = set()

        for cmp_idx in cmp_indices:
            following_ends = [e for e in end_blocks if e > cmp_idx]
            if len(following_ends) >= 2:
                if_end = following_ends[0]
                else_end = following_ends[1]

                # Check if the IF body (between CMP+BRANCH and first END_BLOCK) is empty
                # Look for real instructions between the BRANCH and the first END_BLOCK
                branch_idx = None
                for j in range(cmp_idx + 1, if_end):
                    if self.instructions[j].mnemonic == 'BRANCH_IF':
                        branch_idx = j
                        break

                body_start = (branch_idx + 1) if branch_idx is not None else (cmp_idx + 1)
                if_body = [inst for inst in self.instructions[body_start:if_end]
                           if inst.mnemonic not in ('', 'NOP')]

                # Check ELSE body
                else_body = [inst for inst in self.instructions[if_end + 1:else_end]
                             if inst.mnemonic not in ('', 'NOP')]

                if not if_body and else_body:
                    # Empty IF body, real ELSE body → invert condition
                    self._inverted_conditions.add(cmp_idx)
                    markers[if_end] = 'skip'       # suppress the first END_BLOCK
                    markers[else_end] = 'block_end'
                elif if_body and else_body:
                    # Both bodies present → normal if/else
                    markers[if_end] = 'else_start'
                    markers[else_end] = 'block_end'
                else:
                    # Only IF body (no else)
                    markers[if_end] = 'block_end'
            elif len(following_ends) == 1:
                markers[following_ends[0]] = 'block_end'

        return markers

    def reconstruct_pseudocode(self) -> str:
        lines = []

        # ── Header comments ──
        if self.opcodes:
            lines.append('// Opcode table:')
            for i, op in enumerate(self.opcodes):
                lines.append(f'//   [{i}] {op.value.replace("::op-code", "")}')
            lines.append('')
        if self.symbols:
            lines.append('// Symbols:')
            for i, sym in enumerate(self.symbols):
                lines.append(f'//   [{i}] {sym.value}')
            lines.append('')
        if self.references:
            lines.append('// References:')
            for i, ref in enumerate(self.references):
                lines.append(f'//   [{i}] {ref.value}')
            lines.append('')

        # ── Pre-scan for block structure ──
        block_markers = self._build_block_structure()

        # ── Collect pending target reference for the next CALL ──
        # EXT_01 sets the target object for the following opcode call
        # (e.g., which actor to animate, which behavior to remove)
        pending_target = None

        lines.append('function main() {')
        IND = '    '
        depth = 1
        stack = []          # value stack (strings for display)

        for idx, inst in enumerate(self.instructions):
            ind = IND * depth

            # ── PUSH / CONST: accumulate values on stack ──
            if inst.mnemonic == 'PUSH':
                val = struct.unpack('<I', inst.operands[:4])[0]
                stack.append(val)

            elif inst.mnemonic == 'CONST':
                val = struct.unpack('<i', inst.operands[:4])[0]
                stack.append(val)

            # ── LOAD_CHECK: invoke "check value" with stacked args ──
            elif inst.mnemonic == 'LOAD_CHECK':
                sym = self._resolve_symbol(0)
                args = list(reversed(stack))
                stack.clear()
                arg_str = ', '.join([sym] + [str(a) for a in args])
                lines.append(f'{ind}result = check_value({arg_str});')

            # ── CMP: start an IF block ──
            elif inst.mnemonic == 'CMP':
                arg = inst.operands[0] if inst.operands else 0
                cmp_map = {0: '==', 1: '!=', 2: '<', 3: '>', 4: '<=', 5: '>=', 8: '=='}
                op_str = cmp_map.get(arg, f'cmp_{arg}')

                # If this IF has an empty body, invert the condition
                if idx in self._inverted_conditions:
                    inv_map = {'==': '!=', '!=': '==', '<': '>=', '>': '<=',
                               '<=': '>', '>=': '<'}
                    op_str = inv_map.get(op_str, op_str)

                rhs = stack.pop() if stack else 0
                lines.append(f'{ind}if (result {op_str} {rhs}) {{')
                depth += 1

            # ── BRANCH_IF: note the branch (already inside IF) ──
            elif inst.mnemonic == 'BRANCH_IF':
                pass  # structure is handled by block_markers

            # ── EXT_01: set target reference for next call ──
            elif inst.mnemonic.startswith('EXT_'):
                ext_code = inst.opcode[1] if len(inst.opcode) > 1 else 0
                val = struct.unpack('<I', inst.operands[:4])[0] if len(inst.operands) >= 4 else 0
                if ext_code == 0x01:
                    pending_target = self._resolve_ref(val)
                else:
                    pending_target = None
                    lines.append(f'{ind}// ext_op(0x{ext_code:02X}, {val});')

            # ── CALL: invoke an opcode with accumulated args + target ──
            elif inst.mnemonic == 'CALL':
                if '"' in inst.comment:
                    name = inst.comment.split('"')[1].replace(' ', '_')
                else:
                    name = f'opcode_{inst.opcode[0]}'

                # Build argument list: target first (if set), then stack values
                call_args = []
                if pending_target:
                    call_args.append(f'target="{pending_target}"')
                    pending_target = None
                if stack:
                    for v in reversed(stack):
                        call_args.append(str(v))
                    stack.clear()

                arg_str = ', '.join(call_args)
                lines.append(f'{ind}{name}({arg_str});')

            # ── STORE: assign value to a reference ──
            elif inst.mnemonic == 'STORE':
                val = struct.unpack('<I', inst.operands[:4])[0] if len(inst.operands) >= 4 else 0
                src = stack.pop() if stack else '?'
                ref_name = self._resolve_ref(val)
                lines.append(f'{ind}{ref_name} = {src};')

            # ── JUMP ──
            elif inst.mnemonic == 'JUMP':
                val = struct.unpack('<I', inst.operands[:4])[0] if len(inst.operands) >= 4 else 0
                lines.append(f'{ind}goto 0x{val:X};')

            # ── END_BLOCK: close IF body / start ELSE / close ELSE ──
            elif inst.mnemonic == 'END_BLOCK':
                marker = block_markers.get(idx, 'block_end')
                if marker == 'skip':
                    # Suppressed END_BLOCK (empty IF body was inverted)
                    pass
                elif marker == 'else_start':
                    depth = max(1, depth - 1)
                    ind = IND * depth
                    lines.append(f'{ind}}} else {{')
                    depth += 1
                else:
                    depth = max(1, depth - 1)
                    ind = IND * depth
                    lines.append(f'{ind}}}')

            # ── RETURN ──
            elif inst.mnemonic == 'RETURN':
                lines.append(f'{ind}return;')

            # ── Fallback ──
            else:
                lines.append(f'{ind}// {inst.mnemonic} {inst.comment}')

        # Close any remaining open blocks
        while depth > 1:
            depth -= 1
            lines.append(f'{IND * depth}}}')
        lines.append('}')
        return '\n'.join(lines)

    def decompile(self) -> str:
        out = []
        out.append('=' * 80)
        out.append('TFB SCRIPT DECOMPILER (FIXED)')
        out.append('=' * 80)
        out.append(f'File size: {len(self.data)} bytes')
        out.append('')

        try:
            header = self.parse_header()
            out.append('[HEADER]')
            out.append(f"  Version:     0x{header['version']:02X}")
            out.append(f"  Magic:       {header['magic']}")
            out.append(f"  Header Size: 0x{header['header_size']:08X}")
            out.append('')

            self.opcodes = self.parse_string_table('Opcode')
            out.append(f'[OPCODE TABLE] ({len(self.opcodes)} entries)')
            for i, s in enumerate(self.opcodes):
                out.append(f'  [{i}] "{s.value}"')
            out.append('')

            self.symbols = self.parse_string_table('Symbol')
            out.append(f'[SYMBOL TABLE] ({len(self.symbols)} entries)')
            for i, s in enumerate(self.symbols):
                out.append(f'  [{i}] "{s.value}"')
            out.append('')

            self.references = self.parse_string_table('Reference')
            out.append(f'[REFERENCE TABLE] ({len(self.references)} entries)')
            for i, s in enumerate(self.references):
                out.append(f'  [{i}] "{s.value}"')
            out.append('')

            self.instructions = self.parse_bytecode()
            out.append(f'[BYTECODE] (count field: {self.bytecode_count}, '
                       f'{len(self.instructions)} decoded instructions)')
            out.append('')
            for inst in self.instructions:
                out.append(self.format_instruction(inst))
            out.append('')

            out.append('=' * 80)
            out.append('[PSEUDO-CODE]')
            out.append('=' * 80)
            out.append('')
            out.append(self.reconstruct_pseudocode())

        except Exception as e:
            out.append(f'\nERROR at offset 0x{self.offset:X}: {e}')
            import traceback
            out.append(traceback.format_exc())

        return '\n'.join(out)


def main():
    if len(sys.argv) < 2:
        print("Usage: python tfb_decomp_fixed.py <file.ai> [output.txt]")
        sys.exit(1)
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    decompiler = TFBScriptDecompiler(data)
    result = decompiler.decompile()
    print(result)
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"\nSaved to: {sys.argv[2]}")

if __name__ == '__main__':
    main()