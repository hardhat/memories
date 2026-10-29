# memo_dat: Compiler Prototype Specification

Specification for the tool that compiles the Memories of Ravenwood College script (JSON) and art assets into a single resource file, `memo.dat`, for the Zeal 8-bit engine. The design is modelled on the Wyvern Sorrow pipeline ([dat.h](../../wyvernsorrow/src/dat.h), [dat.c](../../wyvernsorrow/src/dat.c), [dat_gen.py](../../wyvernsorrow/tools/dat_gen.py), [script_gen.py](../../wyvernsorrow/tools/story_editor/script_gen.py)) and widened where our script is larger. Source format: [script-plan.md](script-plan.md) section 7 and [scenes/](scenes).

Status: **draft for review**. Section 12 lists the questions only you or the engine side can answer.

---

## 1. Scope

| In scope (prototype) | Out of scope |
|---|---|
| Validate and lint all scene JSON | Converting PNG art to Zeal tile/palette files |
| Compile scenes to bytecode and string tables | Authoring maps (we only define how they are packed) |
| Pack everything into `memo.dat` with a Wyvern-style header | The engine / bytecode VM in C (we specify its contract in section 10) |
| Emit sidecars: C header of ids, symbol file, layout report, disassembly | Music/SFX file formats (ids and slots only) |
| A reference VM in Python, plus trace-equivalence tests against a JSON interpreter | Compression (a flag bit is reserved) |

Prototype tooling is Python 3 with the standard library only, like [validate.py](tools/validate.py).

## 2. What we keep and change from Wyvern Sorrow

| Wyvern Sorrow | Memories | Reason |
|---|---|---|
| Flat file, header of 8-byte entries `{u32 offset, u16 size, u8 type, u8 id}`, entry 0 is a magic cookie holding the header size | **Keep** the entry layout and cookie. The `id` byte becomes `flags`. | `id` is redundant in Wyvern: `header[block_id]` is indexed by position and the generator writes `id == index`. Flags are useful, and ids become 16 bit (the index). |
| Whole header read into a fixed `DatEntry header[13]` | Header is **not resident**. `dat_open` reads entry 0; a lookup is one seek and one 8-byte read. | We expect about 200-280 entries (about 2 KB of RAM on a Z80). |
| `u16 size` per block | **Keep**. Art blocks over 65,535 bytes use a continuation flag. | Same loader code; our script blocks are all under 12 KB. |
| Script block: indexed by world-object id, linear search, bytecode at most 128 bytes, 1-byte jump targets | **Replace**: one code block per scene, 16-bit offsets, whole scene resident (4 KB cap, 1.7 KB today). | Our scenes are about 1.2 KB of bytecode, not 128 bytes, and they call blocks and branch freely. |
| String block: `u8 count`, `u16` offsets, packed NUL-terminated strings, one resident 128-byte buffer | **Keep the idea**, per scene, with `u16` count and ids. Strings are pre-wrapped at build time. | We have about 1,830 strings (94 KB). Wyvern's 255-string limit does not fit. |
| `dat_gen.py` re-declares the constants that live in `dat.h`; they are kept in sync by hand. `script_gen.py` and `dat_gen.py` duplicate the compiler. | One compiler. It **generates** `memo_ids.h` so tool and engine cannot drift. | Removes a whole class of bugs. |
| Reads must not cross a 16 KB virtual page (`dat_read` splits them) | **Keep**, as part of the loader contract. | ZOS VFS requirement discovered by Wyvern. |
| Two-pass label resolution, string de-duplication | **Keep** | Works well. |
| No format version, no integrity check | Version in entry 0 `flags`; META block with a content CRC | Detect a stale `memo.dat` against the executable. |

## 3. Pipeline

```text
script/common/*.json  --+
script/scenes/*.json  --+-> [1 load] -> [2 check+lint] -> [3 symbols] -> [4 lower] -> [5 assemble]
assets/manifest.json  --+                                                                  |
                                                                                           v
                     build/memo.dat  <-[8 pack]<-[7 tables]<-[6 strings]<-----------------+
                     build/memo_ids.h, memo.sym, memo.layout.txt, memo.lst (sidecars)
```

1. **load**: parse JSON, attach source positions (file, block, op index) for error messages.
2. **check + lint**: everything in [validate.py](tools/validate.py) plus the flow checks in section 7. Errors stop the build; warnings do not (unless `--strict`).
3. **symbols**: assign small integers to variables, characters, expressions, maps, spawns, triggers, CGs, audio, times (section 5.6).
4. **lower**: structured ops (`if`, `choice`, `explore`) to a linear IR with labels.
5. **assemble**: resolve labels to `u16` offsets, emit bytes, one code area per scene.
6. **strings**: wrap, de-duplicate, pack per scene.
7. **tables**: VARS, CHARS, INDEX, META.
8. **pack**: lay out blocks, write header, write `build/memo.dat` and sidecars.

CLI (one entry point, [tools/memo_dat.py](tools) with a `memo/` package):

```text
memo_dat.py check   [--strict]            validate + lint only (replaces validate.py as the CI gate)
memo_dat.py build   [--out build/memo.dat] [--assets assets/manifest.json] [--strict]
memo_dat.py dump    build/memo.dat        independent reader: header, tables, disassembly
memo_dat.py stats   build/memo.dat        size and budget report
memo_dat.py trace   --seed N [--scene s03] run the JSON interpreter and the VM, compare
```

`validate.py` stays as a thin wrapper around `check` so existing habits keep working.

## 4. Inputs

```text
script/
  common/
    characters.json  variables.json  maps.json  cgs.json     (exist)
    audio.json       assets.json     config.json              (new)
  scenes/s01_arrival.json ... s10_epilogue.json              (exist)
```

* **config.json** (new): the limits currently hard-coded in validate.py, so check, compile, and the engine header share one source: text box `36 x 3`; choice prompt at most 2 lines; option text at most 2 lines; 3 options; name plate at most 16 characters; `time` list; limits from section 7.
* **audio.json** (new): `{ "music": { "town_theme": {"file": null}, ... }, "sfx": { "caw": {"file": null}, ... } }`. Today the scripts use 25 music and 27 SFX names with no registry. `memo_dat.py check --init-audio` writes the initial file from the scripts. Unknown names become errors afterwards.
* **assets.json** (new): the manifest binding logical ids to converted art files (`.zts`, `.ztp`, tilemaps) as Wyvern does with `img/*.zts` and `*.ztp`. Missing entries are allowed in the prototype (section 5.7) so scripts can be built and tested before art exists.

## 5. Output file format: `memo.dat`

All multi-byte values are little-endian (as on the Z80 and in Wyvern's `struct.pack('<...')`).

### 5.1 Header

```c
#define DAT_MAGIC  0x4F4D454DUL   /* 'M','E','M','O' little-endian */

typedef struct {
    uint32_t offset;   // file byte offset of the block (entry 0: DAT_MAGIC)
    uint16_t size;     // block size in bytes (entry 0: header size in bytes)
    uint8_t  type;     // DAT_TYPE_*
    uint8_t  flags;    // see below (entry 0: format version, currently 1)
} DatEntry;            // 8 bytes, packed
```

* **Entry 0** is the cookie exactly as in Wyvern. `offset == DAT_MAGIC`, `size == entry_count * 8`, `type == 0`, `flags == 1` (format version).
* **Block id = entry index** (`u16`). The loader reads entry `n` at file offset `n * 8`.
* **flags** (blocks): bit 0 `CONT` (the asset continues in entry `n+1`, used when an asset exceeds 65,535 bytes); bit 1 `MISSING` (placeholder with size 0, art not supplied); bits 2-3 reserved for compression (0 = none).

Entry types:

| Type | Name | Contents |
|---|---|---|
| 0 | MAGIC | cookie |
| 1 | TILESET | opaque Zeal tileset blob (`.zts`), as in Wyvern |
| 2 | PALETTE | opaque palette blob (`.ztp`) |
| 3 | SCENE_CODE | bytecode for one scene (5.3) |
| 4 | STRINGS | string table for one scene (5.4) |
| 5 | TILEMAP | opaque tilemap blob (maps and CGs) |
| 6 | TABLE | engine tables: META, VARS, CHARS, INDEX (5.5) |
| 7 | MAPDEF | map definition (spawns, triggers; section 5.8, phase 2) |

### 5.2 Block id plan

Fixed ids let the engine use constants, as Wyvern's `DAT_BLOCK_*` do. Assets are allocated after them in manifest order and found through INDEX.

| Block id | Name | Type |
|---|---|---|
| 0 | MAGIC | 0 |
| 1 | META | 6 |
| 2 | INDEX | 6 |
| 3 | VARS | 6 |
| 4 | CHARS | 6 |
| 5-15 | reserved | |
| 16-31 | `SCENE_CODE(n)` = 16 + n - 1 (up to 16 scenes) | 3 |
| 32-47 | `SCENE_STR(n)` = 32 + n - 1 | 4 |
| 48- | assets, in manifest order | 1, 2, 5, 7 |

Estimated entry count: about 48 fixed (ids 0-47, unused ones are empty placeholders because the id is the index) plus 150-230 asset blocks (19 CGs at 3 blocks each, portraits, tilesets, 14 maps, sprites). That is a header of roughly 1.6-2.2 KB, which is why it is not resident.

### 5.3 SCENE_CODE block

```text
u16  code_size          bytes of code that follow
u16  entry_pc           offset of the scene's entry block (JSON "entry")
u16  reserved           0
u8   code[code_size]    bytecode; all jump/call targets are offsets into this array
```

The whole block is read into one static buffer when the scene starts (`CODE_BUF_SIZE`, default 4096; the build errors above it and warns above 3072). Current scenes are 1,120 to 1,740 bytes.

### 5.4 STRINGS block

Same idea as Wyvern's string block, with `u16` count:

```text
u16  count
u16  offset[count]      from the start of the string data area
char data[...]          NUL-terminated, packed; '\n' marks a line break
```

* One string per `say` / `tutorial` text, per choice prompt, and per choice option. Identical strings within a scene are stored once (Wyvern's `get_string_id`).
* Strings are ASCII 0x20-0x7E plus `\n`. The current scripts have no other characters; any other byte is a build error until the font charset is confirmed.
* **Pre-wrapped at build time** with the same greedy 36-column wrap that validate.py uses, so the engine needs no word-wrap code. At most 127 bytes including the NUL (the longest today is 109). The engine's single dialog buffer is 128 bytes, like Wyvern's `SCRIPT_MAX_STRING`.
* Ids are numbered in order of first appearance in the scene (stable, so rebuilds diff cleanly).

### 5.5 TABLE blocks

**META** (id 1): `u8 version (1)`, `u8 scene_count`, `u16 string_total`, `u32 content_crc32` (CRC of every block except META, so builds are reproducible: no timestamps in the DAT). The engine can refuse a `memo.dat` that does not match its `memo_ids.h` (the header carries `MEMO_CONTENT_CRC`).

**VARS** (id 3): the runtime variable array.

```text
u8   count
u8   max[count]     clamp value for ADD (flags: 1, counters: from variables.json "max", clues: 255)
u8   init[count]    initial values (all 0 today)
```

Index order: counters in declaration order (today `aff_j`=0 ... `costume`=14), then flags in declaration order (15-42), then `clues` (43). That is 44 bytes of RAM; the engine reserves 64. Names live only in the sidecar. Clue bits are bits 0-7 of `clues` (`CL1` = bit 0).

**CHARS** (id 4): one entry per speaker, in `characters.json` order (`narrator` = 0).

```text
u8   count
repeat count:  u8 side (0 none, 1 left, 2 right), u8 expr_count, u16 name_offset
char names[...]   packed NUL-terminated (name_offset is from the start of this pool)
```

Expression ids are indices into the character's list in `characters.json` (`have` first, then `todo`). The art pipeline fills expressions in that order; a missing expression renders as expression 0, matching the "engine falls back" note in characters.json. Names are limited to 16 characters (check enforces; "Icebreaker Leader" was shortened to "Leader").

**INDEX** (id 2): maps logical ids to block ids (`0` means no asset yet).

```text
u8  map_count      u16 mapdef_block[map_count]
u8  cg_count       { u16 tiles, u16 tilemap, u16 palette }[cg_count]
u8  portrait_count { u16 tiles, u16 palette }[portrait_count]     (indexed by character id)
u8  sprite_count   { u16 tiles, u16 palette }[sprite_count]       (indexed by character id)
u8  tileset_count  { u16 tiles, u16 palette }[tileset_count]
u8  music_count    u16 block[music_count]
u8  sfx_count      u16 block[sfx_count]
```

Counts today: 14 maps, 19 CGs, 25 music, 27 SFX.

### 5.6 Symbol assignment

| Symbol | Source | Encoding |
|---|---|---|
| variable | `common/variables.json` | `u8` index (5.5) |
| clue bit | `CL1..CL8` | `u8` 0-7 |
| character / expression | `characters.json` | `u8` / 5-bit index |
| map / CG | `maps.json`, `cgs.json` | `u8` index in file order |
| spawn | per map list in `maps.json` | `u8` index within that map |
| trigger | all names across `maps.json` (38 today) | `u8` **global** name id; the map data binds each name to a place on its map |
| time of day | `config.json` list: dawn, morning, noon, midday, afternoon, golden, dusk, evening, night, midnight, snow | `u8` |
| music / sfx | `audio.json` | `u8` |
| tutorial id | the `id` field in `tutorial` ops (10 today) | `u8` assigned by first use |
| scene | `scene` order in `scenes/` | `u8` (1-based); also the value of the `scene` variable |

Trigger ids are global rather than per map because trigger names such as `fountain` exist on two maps. Explore only needs "which named trigger fired", and the engine knows the active map.

### 5.7 Asset blocks and the manifest

Art is carried as **opaque blobs**, exactly like Wyvern copies `.zts` and `.ztp` files. `assets/manifest.json` binds logical ids to files:

```json
{
  "tilesets":  { "town": {"tiles": "img/town.zts", "palette": "img/town.ztp"} },
  "portraits": { "brad": {"tiles": "img/brad.zts", "palette": "img/brad.ztp"} },
  "cgs":       { "CG-01": {"tiles": "img/cg01.zts", "tilemap": "img/cg01.ztm", "palette": "img/cg01.ztp"} },
  "maps":      { "M01": "maps/M01.json" }
}
```

* A logical id without art gets an **entry with `MISSING` and size 0**; INDEX points to it. `--strict` turns missing art into an error. This lets us build and test scripts today.
* An asset over 65,535 bytes is split into consecutive entries with `CONT` set on all but the last. The INDEX points at the first.
* The prototype stores the bytes unchanged and records their sizes in `memo.layout.txt`. Interpreting them is the engine's job.

### 5.8 MAPDEF (phase 2 sketch)

Maps are not authored yet. The only rule the script compiler needs: a map defines its **spawn names** and **trigger names** (already listed in `maps.json`). When maps arrive (likely an editor export), the compiler will validate that every spawn and trigger named in `maps.json` exists in the map data, and pack:

```text
u16 width, u16 height, u8 layers
u8  spawn_count     { u8 x, u8 y, u8 facing }[spawn_count]          (index = spawn id)
u8  trigger_count   { u8 trigger_id, u8 x, u8 y, u8 w, u8 h }[...]  (global trigger id)
layer data / collision / tileset binding ...
```

Treat as provisional until the map format exists.

## 6. Bytecode

Fixed opcode numbers, one byte each. Jump, call, and branch targets are `u16` offsets in the scene code area. "Cond" is `cmp` 0 `eq`, 1 `ne`, 2 `gte`, 3 `lt`.

| Op | Mnemonic | Operands | Size | JSON op |
|---|---|---|---|---|
| 0x00 | END | | 1 | `end`: scene over; engine reads var `scene` for the next scene |
| 0x01 | SAY | `who:u8`, `ex:u8`, `str:u16` | 5 | `say`; `ex` = expression (0-30, 31 = none) or `style << 5` (0 normal, 1 phone, 2 credits) |
| 0x02 | MAP | `map:u8`, `spawn:u8`, `time:u8` | 4 | `map` |
| 0x03 | FADE | `mode:u8` (0 in/clear, 1 out/black), `t:u8` (x10 ms) | 3 | `fade`; the longest fade today is 1500 ms = 150 |
| 0x04 | MUSIC | `id:u8` | 2 | `music` |
| 0x05 | SFX | `id:u8` | 2 | `sfx` |
| 0x06 | CG | `id:u8` | 2 | `cg` |
| 0x07 | CG_OFF | | 1 | `cg_off` |
| 0x08 | TUTOR | `id:u8`, `str:u16` | 4 | `tutorial`; shown only if its bit in the saved "seen" mask is clear, then set |
| 0x09 | WAIT | `ticks:u8` | 2 | `wait` (reserved; unused today) |
| 0x10 | SET | `var:u8`, `n:u8` | 3 | `set` |
| 0x11 | ADD | `var:u8`, `n:u8` | 3 | `add`; clamps to VARS `max` |
| 0x12 | SUB | `var:u8`, `n:u8` | 3 | `sub`; floors at 0 |
| 0x13 | COPY | `dst:u8`, `src:u8` | 3 | `copy` |
| 0x14 | SETBIT | `bit:u8` | 2 | `setbit` (on `clues`) |
| 0x15 | PICKMAX | `dst:u8`, `n:u8`, `{var:u8, val:u8} x n` | 3+2n | `pick_max` (writes `val` of the first maximal `var` into `dst`) |
| 0x20 | JMP | `off:u16` | 3 | (lowering) |
| 0x21 | BRF | `cond:u8`, `var:u8`, `n:u8`, `off:u16` | 6 | `if` on a variable: branch if the test is **false** |
| 0x22 | BRFB | `bit:u8`, `off:u16` | 4 | `if` on a clue bit: branch if the bit is clear |
| 0x23 | CALL | `off:u16` | 3 | `call` (push return pc, depth at most 8) |
| 0x24 | RET | | 1 | end of a called block (depth 0 is a fault) |
| 0x25 | GOTO | `off:u16` | 3 | `goto` (discards the call stack and any explore context) |
| 0x30 | CHOICE | `prompt:u16`, `n:u8`, `{str:u16, off:u16} x n` | 4+4n | `choice`: show the menu, jump to the picked option's code |
| 0x31 | EXPLORE | `obj:u8`, `cvar:u8`, `cmax:u8`, `n:u8`, `onmax:u16`, `exit:u16`, `{trig:u8, fl:u8, off:u16} x n` | 9+4n | `explore`; `obj` = trigger id for the objective marker or 0xFF; `cvar` = clock var or 0xFF; `fl` bit 0 = once |
| 0x32 | XRET | | 1 | end of trigger code: back to the explore loop |
| 0x40-0xFF | reserved | | | future ops (`show`, `hide`, `walk`) |

Sizes check against the real scripts: 1,625 `say` ops are 8.1 KB; the other ops add about 4.5 KB, so a scene is 1.1-1.7 KB.

### 6.1 Lowering rules

**`if`** (`BRF` jumps over the `then` part):

```text
        BRF cond var n -> Lelse         ; or BRFB bit -> Lelse
        <then code>
        JMP Lend                        ; only if an else exists
Lelse:  <else code>
Lend:
```

Worked example (illustrative ids: `aff` = var 13, jane = char 4, smile = 1, serious = 2, strings 10 and 11, code at 0x0100):

```text
{"op":"if","test":{"var":"aff","cmp":"gte","n":6},
 "then":[{"op":"say","who":"jane","expr":"smile","text":"Yes."}],
 "else":[{"op":"say","who":"jane","expr":"serious","text":"No."}]}

0100: 21 02 0D 06 0E 01      BRF gte aff 6 -> 010E
0106: 01 04 01 0A 00         SAY jane smile str10
010B: 20 13 01               JMP 0113
010E: 01 04 02 0B 00         SAY jane serious str11
0113:
```

**`choice`**: the `CHOICE` instruction carries the option table; option bodies follow it in order, each ending in a `JMP` to the join point.

```text
{"op":"choice","prompt":"Georgia holds out a warm cookie.","options":[
  {"text":"Take the cookie","do":[{"op":"add","var":"aff_g","n":1}]},
  {"text":"Politely decline","do":[]}]}          (illustrative: aff_g = var 2, strings 20/21/22)

0200: 30 14 00 02 15 00 0C 02 16 00 12 02   CHOICE prompt=20 n=2 {21->020C} {22->0212}
020C: 11 02 01                              ADD aff_g 1
020F: 20 15 02                              JMP 0215
0212: 20 15 02                              JMP 0215
0215:
```

**`explore`**: the `EXPLORE` instruction holds the table; trigger bodies and the `on_max` body follow, then the exit label.

```text
        EXPLORE obj cvar cmax n onmax=Lmax exit=Lexit  {trig, fl, Lt1} {trig, fl, Lt2} ...
Lt1:    <trigger 1 code>      XRET         ; or ends in GOTO / END
Lt2:    <trigger 2 code>      XRET
Lmax:   <on_max code>         JMP Lexit    ; only when on_max can fall through
Lexit:  <next instruction>
```

Engine semantics: on entry, clear the once-mask; loop until the player activates a trigger; run its code; at `XRET`, if `cvar` is set and `var[cvar] >= cmax`, jump to `onmax`, otherwise continue the loop. A trigger marked `once` is disabled after firing. `GOTO` or `END` inside trigger code leaves the explore. Reaching `Lexit` leaves it.

**Blocks**: emitted in JSON order; each block gets a label. A block that can fall off its end gets a trailing `RET`; a block proven to terminate (every path ends in `goto` or `end`) gets none. The scene header's `entry_pc` is the label of `entry`.

## 7. Checks and lints

Errors fail the build; warnings fail only with `--strict`.

| Check | Level | Why |
|---|---|---|
| Everything validate.py does today: JSON, ops, speakers, expressions, variables, bits, maps/spawns/CGs/blocks resolve, text fits the box, choice has 1-3 options, unique choice ids | error | existing behavior |
| Audio names exist in `audio.json`; time-of-day names exist in config | error | new registries |
| `say` text is printable ASCII, at most 3 lines and 127 bytes; choice prompt and options at most 2 lines each | error | section 5.4 |
| A block reached by `goto` or as the entry must not be able to fall off its end | error | engine would hit `RET` at depth 0; found by the Python prototype, currently passes |
| `goto` must not appear in any block reachable via `call` | error | `GOTO` drops the call stack; currently passes |
| No call recursion; call depth at most 8 (today at most 2) | error | static call stack |
| `explore` must have an exit: a clock, or a trigger path that reaches `goto`/`end` | error | the Python simulator found a real instance of this (Scene 3) |
| `explore` is not nested (including through `call`) | error | one engine explore context |
| An explore's clock variable is incremented somewhere in its trigger code | warn | would never fire |
| At most 16 triggers per explore | error | once-mask size |
| Scene code over 4 KB (error) or over 3 KB (warn); more than 65,000 bytes of strings | error / warn | buffers |
| A trigger named in an explore exists on some map reachable at that point (reaching-map analysis through `map` ops and calls) | warn | spots typos; exact needs the map data |
| Unreachable blocks | warn | dead script |
| Flags written but never read | info | 9 today (`MIDTERM_PASS`, `F_DEFIED_GORD`, `F_ASKED_GORD`, `F_SKIPPED_TOUR`, `F_ARCHIVE_OPEN`, `F_MET_J`, `F_S2_S`, `F_S2_G`, `F_GAME_COMPLETE`): hooks for future callbacks |
| Flags read but never written | warn | likely a typo |
| Unused expressions, music, SFX, CGs | info | art/audio budget |

## 8. Sidecar outputs

* **`memo_ids.h`**: generated constants, so the engine never hard-codes ids: `VAR_*` indices (`VAR_ROUTE`, `VAR_ENDING`, `VAR_SCENE`, `VAR_CLUES`, ...), `CL1..CL8` bit numbers, `OP_*` opcodes, `SCENE_COUNT`, `BLOCK_*` fixed ids, `CODE_BUF_SIZE`, `MEMO_CONTENT_CRC`, and enums for characters, maps, CGs, trigger names, music, SFX, time of day.
* **`memo.sym`** (JSON): names for debugging: variable names, block label offsets per scene, choice ids to code offsets, and a table `string id -> (file, block, op index)`. A `memo_dat.py dump --sym` shows `say jane/smile "Yes."` rather than numbers.
* **`memo.lst`**: disassembly with source positions.
* **`memo.layout.txt`**: block table (id, type, offset, size, flags, name) and budget usage: header bytes, code bytes per scene versus the cap, string bytes per scene, count of `MISSING` assets.

## 9. Verification

1. **Independent reader**: `dump` parses the file with a separate code path and re-prints tables and disassembly; the build re-reads its own output and compares counts and CRC.
2. **Trace equivalence** (the main correctness test). Two interpreters execute the same play with the same random seed and must produce the same event trace:
   * `sim.py`: interprets the scene JSON directly. This is the throwaway simulator used during script authoring (random playthrough, choices by seed), promoted into the repo.
   * `vm.py`: interprets the compiled `memo.dat`.
   * A trace is the sequence of `say(who, expr, text)`, `map`, `fade`, `cg`, `music`, `sfx`, `tutorial`, `choice(index)`, and variable writes. Run over thousands of seeds across the full ten-scene game (affection-biased and uniform choice policies); any divergence is a compiler or VM bug. Also asserts that every playthrough ends with a route and an ending (it has already caught an unreachable-ending balance bug and a stuck explore).
3. **Golden tests** in `script/tests/`: one tiny scene per construct (each op, nested `if` inside `choice`, `explore` with and without clock, `call` depth 8, `goto` out of explore) with expected hex, including the two examples in section 6.1.
4. **Budget report** (`stats`) fails CI if code, string, or call-depth limits are exceeded.
5. **Coverage report**: percentage of say lines and choice options reached by the seeded runs (guards against untestable branches).

## 10. Engine-side contract (summary, for the Zeal 8-bit loader)

The loader is `dat.c` from Wyvern adapted; the changes follow from section 2.

```c
bool     dat_open(void);                              // read entry 0, check MEMO cookie + version
bool     dat_entry(uint16_t id, DatEntry *out);       // seek id*8, read 8 bytes
bool     dat_load_block(uint16_t id, void *dst, uint16_t max, uint16_t *size_out); // page-safe read
bool     dat_load_scene(uint8_t scene);               // code -> code_buf; str table kept on disk
bool     dat_load_string(uint16_t str_id);            // seek offset table, then data -> dialog[128]
```

Suggested RAM budget (to confirm with the engine owner):

| Item | Bytes |
|---|---|
| Scene code buffer | 4096 |
| Dialog buffer | 128 |
| Choice strings (prompt + 3 options, two lines each) | 4 x 80 |
| VM: pc, call stack 8 x 2, explore context (obj, cvar, cmax, once-mask, table pc) | about 32 |
| Variable array (44 used) | 64 |
| Tutorial-seen mask | 4 |
| **Total** | **about 4.6 KB** |

* Reads must go through the Wyvern `dat_read` helper that splits at 16 KB virtual page boundaries.
* The VM maps opcodes to engine calls (map view, dialog, CG, menu). All gameplay state lives in the variable array, so a save is `vars[64]` + scene + tutorial mask. Saving only at scene starts (autosave) keeps the VM state trivial; saving inside a scene is out of scope for v1.

## 11. Capacity estimate (from the current scripts)

Measured with a throwaway analysis of the ten scenes using the opcode sizes in section 6. The analysis assumed slightly smaller sizes for `tutorial` and `explore` than the final table, so the code figures are low by under 1% (about 50 bytes in total).

| Scene | Code bytes | Largest block | Strings | String bytes | Call depth |
|---|---|---|---|---|---|
| s01 | 1,147 | 252 | 172 | 7,300 | 1 |
| s02 | 1,188 | 288 | 178 | 8,897 | 2 |
| s03 | 1,186 | 236 | 168 | 8,260 | 2 |
| s04 | 1,139 | 158 | 170 | 9,323 | 1 |
| s05 | 1,120 | 215 | 178 | 9,396 | 1 |
| s06 | 1,211 | 238 | 189 | 9,569 | 1 |
| s07 | 1,430 | 170 | 202 | 10,828 | 2 |
| s08 | 1,307 | 258 | 194 | 10,186 | 1 |
| s09 | 1,738 | 289 | 203 | 11,424 | 2 |
| s10 | 1,167 | 319 | 159 | 8,510 | 1 |
| **Total** | **12,633** | | **1,813 unique (of 1,830)** | **93,693** | |

Script content totals about 106 KB, plus tables (under 1 KB) and a header of about 2 KB. The art, which the manifest will pass through, will dominate the file. Strings are the second largest part; compression is a candidate if storage matters (flag bits reserved).

## 12. Open questions

1. **Art formats and sizes.** Zeal tile and palette sizes for portraits, CGs, map tilesets. Need palette size limits (Wyvern uses a 128-byte palette buffer), CG resolution and tile bit depth, and whether CGs fit a 65,535-byte block (otherwise the continuation flag is used).
2. **Map authoring.** What format will maps be authored in (Tiled export?), and who owns the collision/trigger conventions? Section 5.8 depends on it.
3. **Audio.** Music and SFX formats and how many bytes of RAM streaming needs. The registry exists; the assets do not.
4. **Font and charset.** Is the font ASCII-only? Are `{`, `}`, `|`, `~` available? (Current text uses only printable ASCII.)
5. **Save granularity.** Scene-start autosave (recommended for v1) or mid-scene checkpoints (would require saving explore state and the call stack)?
6. **Code buffer size.** Is 4 KB resident acceptable? Alternative: load one block at a time like Wyvern (the compiler already knows block boundaries) at the cost of reloading on `call` return.
7. **Choice UI.** Two lines per option and two for the prompt (8 lines): is a full-screen menu acceptable, or should options be 1 line (36 characters) and the 43-character option in scene 1 shortened?
8. **Shared tooling.** Do you want the header pack/unpack code factored into a small module shared with Wyvern Sorrow's `dat_gen.py`, or kept independent?

## 13. Prototype milestones

| # | Deliverable | Done when |
|---|---|---|
| M1 | `memo/` package: loader + checks from validate.py, config.json, audio.json registry, new lints (section 7) | `check` passes on the current scripts with only the 9 informational findings |
| M2 | Symbol assignment, lowering, assembler, string packer; `build` writes tables + scene blocks with `MISSING` art | `dump` round-trips; golden tests (section 9.3) pass |
| M3 | `sim.py` (JSON interpreter) and `vm.py` (bytecode) with trace comparison | 10,000 seeds with zero divergence; coverage report |
| M4 | Asset manifest pass-through, `CONT` splitting, `memo_ids.h`, `memo.sym`, `memo.lst`, `stats` | a build with fake art blobs lays out and reports correctly |
| M5 | C loader skeleton adapted from Wyvern's `dat.c` plus a VM stub that executes scene 1 in a desktop test harness | VM trace matches `vm.py` |
| M6 | Map blocks (needs open question 2) | map data validates against `maps.json` |
