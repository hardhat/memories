"""Format constants for memo.dat. Shared by the writer, the reader and the VM.

See script/compiler-spec.md sections 5 and 6. Keep this file the single source of
truth for numbers; memo_ids.h is generated from it.
"""
import struct

MAGIC = 0x4F4D454D  # 'M','E','M','O' little-endian
VERSION = 1
ENTRY = struct.Struct("<IHBB")  # offset, size, type, flags

# Entry types
T_MAGIC, T_TILESET, T_PALETTE, T_SCENE_CODE, T_STRINGS = 0, 1, 2, 3, 4
T_TILEMAP, T_TABLE, T_MAPDEF, T_PORTRAIT = 5, 6, 7, 8
T_UNUSED = 0xFF

# Entry flags
F_CONT = 0x01
F_MISSING = 0x02

# Fixed block ids
BLOCK_MAGIC, BLOCK_META, BLOCK_INDEX, BLOCK_VARS, BLOCK_CHARS = 0, 1, 2, 3, 4
SCENE_CODE_BASE = 16
SCENE_STR_BASE = 32
ASSET_BASE = 48
MAX_SCENES = 16

# Opcodes
OP = {
    "END": 0x00, "SAY": 0x01, "MAP": 0x02, "FADE": 0x03, "MUSIC": 0x04, "SFX": 0x05,
    "CG": 0x06, "CG_OFF": 0x07, "TUTOR": 0x08, "WAIT": 0x09,
    "SET": 0x10, "ADD": 0x11, "SUB": 0x12, "COPY": 0x13, "SETBIT": 0x14, "PICKMAX": 0x15,
    "JMP": 0x20, "BRF": 0x21, "BRFB": 0x22, "CALL": 0x23, "RET": 0x24, "GOTO": 0x25,
    "CHOICE": 0x30, "EXPLORE": 0x31, "XRET": 0x32, "XEXIT": 0x33,
}
OP_NAME = {v: k for k, v in OP.items()}

CMP = {"eq": 0, "ne": 1, "gte": 2, "lt": 3}
CMP_NAME = {v: k for k, v in CMP.items()}
STYLE = {None: 0, "phone": 1, "credits": 2}
STYLE_NAME = {v: k for k, v in STYLE.items()}
EXPR_NONE = 31
NO_TRIGGER = 0xFF
NO_VAR = 0xFF
FADE_MODE = {"clear": 0, "black": 1}
DEFAULT_FADE_MS = 500
SIDE = {None: 0, "none": 0, "left": 1, "right": 2}

# Run-time limits (also in common/config.json)
CALL_DEPTH_MAX = 8
