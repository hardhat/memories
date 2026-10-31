# memo_dat: Compiler Prototype Specification

Specification for the tool that compiles the Memories of Ravenwood College script (JSON) and art assets into a single resource file, `memo.dat`, for the Zeal 8-bit engine. The design is modelled on the Wyvern Sorrow pipeline ([dat.h](../../wyvernsorrow/src/dat.h), [dat.c](../../wyvernsorrow/src/dat.c), [dat_gen.py](../../wyvernsorrow/tools/dat_gen.py), [script_gen.py](../../wyvernsorrow/tools/story_editor/script_gen.py)) and widened where our script is larger. Source format: [script-plan.md](script-plan.md) section 7 and [scenes/](scenes).

Status: **draft, revision 2** (art and map formats confirmed). Source tools: [gif2zeal.py](../../Zeal-VideoBoard-SDK/tools/zeal2gif/gif2zeal.py) for tiles and palettes, [tiled2zeal.py](../../Zeal-VideoBoard-SDK/tools/tiled2zeal/tiled2zeal.py) for tile maps (Tiled TMX). Section 12 records the review decisions and lists the remaining questions.

---

## 1. Scope

| In scope (prototype) | Out of scope |
|---|---|
| Validate and lint all scene JSON | Drawing art; the conversion tools themselves (`gif2zeal.py`, `tiled2zeal.py`), which the compiler can call with `--convert` but does not reimplement |
| Compile scenes to bytecode and string tables | Authoring maps (done in Tiled) |
| Pack everything into `memo.dat` with a Wyvern-style header | The engine / bytecode VM in C (we specify its contract in section 10) |
| Emit sidecars: C header of ids, symbol file, layout report, disassembly | Music/SFX file formats (ids and slots only) |
| A reference VM in Python, plus trace-equivalence tests against a JSON interpreter | Writing a compressor. We pass through gif2zeal's RLE/LZ and tiled2zeal's RLE, and decode them only to validate. |

Prototype tooling is Python 3 with the standard library only. It lives in [tools/memo/](tools/memo) with the entry point [memo_dat.py](tools/memo_dat.py); [validate.py](tools/validate.py) is now a wrapper for `memo_dat.py check`.

## 2. What we keep and change from Wyvern Sorrow

| Wyvern Sorrow | Memories | Reason |
|---|---|---|
| Flat file, header of 8-byte entries `{u32 offset, u16 size, u8 type, u8 id}`, entry 0 is a magic cookie holding the header size | **Keep** the entry layout and cookie. The `id` byte becomes `flags`. | `id` is redundant in Wyvern: `header[block_id]` is indexed by position and the generator writes `id == index`. Flags are useful, and ids become 16 bit (the index). |
| Whole header read into a fixed `DatEntry header[13]` | Header is **not resident**. `dat_open` reads entry 0; a lookup is one seek and one 8-byte read. | We expect about 200-280 entries (about 2 KB of RAM on a Z80). |
| `u16 size` per block | **Keep**. A block over 65,535 bytes is a build error. | Same loader code; our script blocks are all under 12 KB and the largest planned art block (a 320x192 8bpp tileset) is 61,440 bytes. A continuation mechanism would make block ids depend on file sizes, so it is not implemented. |
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
memo_dat.py build   [--out build/memo.dat] [--assets assets/manifest.json] [--convert] [--keep-compression] [--strict]
                    --convert           run gif2zeal.py / tiled2zeal.py for sources newer than their outputs
                    --keep-compression  pass the converter's RLE/LZ through (default: store art uncompressed)
memo_dat.py dump    build/memo.dat        independent reader: header, tables, disassembly
memo_dat.py stats   build/memo.dat        size and budget report
memo_dat.py trace   --seed N [--scene s03] run the JSON interpreter and the VM, compare
memo_dat.py ctrace  --seeds N             run the C engine (engine/) on the same plays, compare
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

* **config.json** (new): the limits currently hard-coded in validate.py, so check, compile, and the engine header share one source: dialog text `36 x 3`; choice menu budget `choice.lines_max` = 6 lines for prompt plus options together (the dialog area is 6 lines tall); 3 options; name plate at most 16 characters; the `time` list; limits from section 7.
* **audio.json** (new): `{ "music": { "town_theme": {"file": null}, ... }, "sfx": { "caw": {"file": null}, ... } }`. Today the scripts use 25 music and 27 SFX names with no registry. `memo_dat.py check --init-audio` writes the initial file from the scripts. Unknown names become errors afterwards.
* **assets.json** (new): the manifest binding logical ids to art. Entries point at converter outputs (`.zts`, `.ztp`, `.ztm`) or at their sources (`.gif`, `.tmx`) when `--convert` is used (section 5.7). Missing entries are allowed in the prototype so scripts can be built and tested before art exists.

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
* **flags** (blocks): bit 0 reserved (was `CONT`; see section 2); bit 1 `MISSING` (placeholder with size 0 and offset 0, art not supplied); bits 2-3 reserved for whole-block compression (unused; art compression is per asset, section 5.7).

Entry types:

| Type | Name | Contents |
|---|---|---|
| 0 | MAGIC | cookie |
| 1 | TILESET | 4-byte graphics header + `.zts` bytes (5.7) |
| 2 | PALETTE | 2-byte header + a slice of `.ztp` bytes (5.7) |
| 3 | SCENE_CODE | bytecode for one scene (5.3) |
| 4 | STRINGS | string table for one scene (5.4) |
| 5 | TILEMAP | 3-byte header + `.ztm` bytes (maps, layers, CGs; 5.7) |
| 6 | TABLE | engine tables: META, VARS, CHARS, INDEX (5.5) |
| 7 | MAPDEF | map definition: dimensions, layer blocks, spawns, triggers (5.8) |
| 8 | PORTRAIT | portrait descriptor: tile layout, expression heads, tileset and palette blocks (5.7) |

### 5.2 Block id plan

Fixed ids let the engine use constants, as Wyvern's `DAT_BLOCK_*` do. Assets are allocated after them and found through INDEX.

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
| 48- | assets, in the fixed order below | 1, 2, 5, 7, 8 |

**Asset allocation order** does not depend on which art exists, so supplying a file never renumbers anything:

1. for each character in `characters.json` that has expressions: `PORTRAIT`, `TILESET`, `PALETTE` (3 blocks);
2. for each CG in `cgs.json`: `TILESET`, `TILEMAP`, `PALETTE` (3 blocks; the tile map slot is `UNUSED` when the image is in raster order);
3. for each tileset in the manifest, in manifest order: `TILESET`, `PALETTE` (maps follow in M6).

Today that is 7 portraits and 19 CGs: 78 blocks, so 126 entries and a 1,008-byte header. With the 14 maps and their tilesets the header will be roughly 1.2-1.6 KB, which is why it is not resident.

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
* **Pre-wrapped at build time** with the same greedy 36-column wrap the checker uses, so the engine needs no word-wrap code. At most 127 characters plus the NUL, so a string always fits the engine's single 128-byte dialog buffer (Wyvern's `SCRIPT_MAX_STRING`); the longest today is 109.
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

**INDEX** (id 2): maps logical ids to block ids (`0` means there is no block: sprites, maps and music until their milestones). Art that is not supplied still has a block id, flagged `MISSING` (section 5.7).

```text
u8  map_count      u16 mapdef_block[map_count]                              (all 0 until M6)
u8  cg_count       { u16 tiles, u16 tilemap, u16 palette }[cg_count]   (tilemap 0 = tiles are in raster order)
u8  portrait_count u16 portrait_block[portrait_count]                    (indexed by character id; type 8; 0 = no portrait)
u8  sprite_count   { u16 tiles, u16 palette }[sprite_count]              (indexed by character id; layout TBD, all 0)
u8  tileset_count  { u16 tiles, u16 palette }[tileset_count]             (map tilesets)
u8  music_count    u16 block[music_count]                                (all 0)
u8  sfx_count      u16 block[sfx_count]                                  (all 0)
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

### 5.7 Art blocks and the manifest

The art is produced by `gif2zeal.py` (tiles and palettes) and `tiled2zeal.py` (tile maps). The compiler packs their **output bytes unchanged**, each behind a small header so the engine does not have to guess what the unlabelled file contains. Facts taken from the converters:

| File | What gif2zeal / tiled2zeal produce | Consequence |
|---|---|---|
| `.ztp` palette | RGB565 little endian, 2 bytes per colour, entries `0 .. colors-1` (`-c`, default 2/4/16/256 by bpp) | A palette that only uses entries 32-63 still has 64 entries in the file; we store the slice. |
| `.zts` tileset | 16x16 tiles in raster order of the GIF; `-b` 1/2/4/8 bpp (4bpp packs two pixels per byte, high nibble first: 128 bytes per tile; 8bpp: 256 bytes per tile); optional `-z rle` or `-z lz`, applied **per tile**, concatenated with no length field; `-u` removes duplicate tiles, `-m` writes a `.ztm` index list, `-s` strips tiles | Compressed files do not reveal their tile count, so the header carries it. Pixel values are the GIF's raw palette indices, so an asset's colours must already sit at the indices it will use. |
| `.ztm` tile map | one byte per tile (Tiled gid - 1; **empty = 255**); optional RLE (`-z`); one file per tile layer (and per screen with `-s`) | Tile ids above 254 cannot be represented; width and height are not in the file, so the header carries them. |

**Graphics headers** (new, produced by the compiler):

```text
TILESET block:  u8 bpp (1,2,4,8), u8 comp (0 none, 1 rle, 2 lz), u16 tile_count   then .zts bytes
PALETTE block:  u8 first, u8 last (inclusive; 0..255)                              then (last-first+1)*2 bytes
TILEMAP block:  u8 comp (0 none, 1 rle), u8 width, u8 height (tiles)               then .ztm bytes
```

`tile_count` is the decoded count: raw size divided by 128 or 256. A compressed file's count is found by decoding the stream at build time (the RLE and LZ formats are small and fully defined by gif2zeal's `compress` and `compress_lz`). **By default the build stores art uncompressed**: uncompressed images load very fast on Zeal even in 4 KB reads, and the engine then needs no decompressor. `--keep-compression` passes RLE/LZ files through unchanged (the `comp` byte says which). The decode also lets the build verify the tile count against the declared image size and check every pixel index (below).

**Sizes of the two image modes** (both fit one block, no `CONT` needed even uncompressed):

| Mode | Tiles | Raw tileset | Colours |
|---|---|---|---|
| 320x240, 4bpp | 20 x 15 = 300 | 38,400 bytes | 16 |
| 320x192, 8bpp | 20 x 12 = 240 | 61,440 bytes | up to 256, with its own palette (leaves a 48-pixel strip, 3 tile rows, below the image) |

`-u` plus a `.ztm` index shrinks either, if the picture repeats tiles (index bytes cap the unique tile count at 256). Both modes are supported; the choice is per CG in the manifest (`bpp`).

**Portraits.** 8bpp, a **32x80 pixel** base image (2 tiles wide, 5 tall) plus alternate heads per expression, with 32 colours per portrait including transparent. The alternate head is a **2 x 2 tile (32x32 px) region at the top of the base image** (`head` = `[0, 0, 2, 2]`, configurable in `config.json` under `art.portrait`). The `PORTRAIT` block (type 8) describes it so the engine can swap expressions by rewriting a few tile map entries:

```text
u8  base_w, base_h         tiles in the base image          (32x80 px = 2 x 5 tiles)
u8  head_x, head_y         tile position of the head inside the base image
u8  head_w, head_h         tiles per expression head
u8  expr_count             expressions, in characters.json order
u16 tiles_block            TILESET block
u16 palette_block          PALETTE block for this portrait
```

**Artist's sheet layout.** One GIF, 32 pixels wide: the 80-pixel base image (showing expression 0) at the top, then one 32x32 head per further expression stacked below it in `characters.json` order. A portrait with `n` expressions is `32 x (80 + 32 * (n - 1))` pixels (Jane: 8 expressions today, so 32x304; Brad has 10, so 32x368). Export it as `jane__B8C20.gif`.

Tile layout in the `.zts` (so no explicit tile map is stored): raster order of that sheet, which is the base image's tiles (`base_w * base_h`, including the head of expression 0) then each alternate head (`head_w * head_h` tiles). Expression `e` (1 or more) tile `j` is tile `base_w*base_h + (e-1)*head_w*head_h + j`. Total tiles: `base_w*base_h + (expr_count-1)*head_w*head_h`. The build checks this count against the GIF and reports the expected sheet size when it does not match.

**Palettes (current tooling, legacy constraints).** The palette block holds
the `.ztp` entries (`first` is 0 in practice; the header supports sub-ranges).
Current checks require decoded pixel indices below the palette colour count,
portraits at most 32 colours (`C20`), and 4bpp indices 0-15. These checks do
not yet implement the exploration allocation below.

**Exploration target contract (2026-10-30).** Shared hardware tile slots:
0 empty; 1-63 dialog; 64-113 left portrait; 114-163 right portrait;
164-255 scenery, sprites and effects (92 tiles together). Each portrait
reserves a 2x5 base and ten additional 2x2 expression heads (50 tiles).
Walking sprites are 16x32, front/back/one side, two frames each, with X-mirroring
for the opposite side: 12 unique tiles per moving character. A stationary
single pose costs two tiles. Each 16x16 sprite tile supports independent X/Y
mirroring, allowing symmetric costume halves to share tiles.

Palette entry 0 is shared transparency for sprites/layer 1 and an ordinary
visible colour on layer 0. Budget 48 colours per portrait including shared 0,
32 for dialog, and 128 for world/sprites/effects including shared 0.
Exact palette ranges and local-to-global remapping remain to be assigned.
Preserve tile indices and semantic palette roles across lighting/season
variants; use palette swaps where sufficient, replacement tiles where shapes
change. See [art-todo.md](../art/art-todo.md#exploration-tiles-and-palettes-2026-10-30-decisions)
for the production decisions and outstanding implementation work. This target
does not change the separate full-screen CG workflow.

**CG checks.** 4bpp or 8bpp only. Without a tile map the tile count must be 300 (4bpp) or 240 (8bpp). With `U` and `M` flags the `.ztm` must have 300 or 240 entries, each below the tile count. A tileset used by maps may hold at most 255 tiles (map entries are one byte and 255 means empty).

**Manifest** (`assets/manifest.json`; paths relative to it; keys must be existing character or CG names, anything else is a warning):

```json
{
  "tools": { "gif2zeal": "../../Zeal-VideoBoard-SDK/tools/zeal2gif/gif2zeal.py" },
  "tilesets": { "town": { "gif": "img/town__B8.gif" } },
  "portraits": {
    "brad": { "gif": "img/brad__B8C20.gif" }
  },
  "cgs": {
    "CG-01": { "gif": "img/cg01__B8C20.gif", "bpp": 8 },
    "CG-02": { "gif": "img/cg02__B4UMC10.gif" }
  },
  "maps": {
    "M01": { "tmx": "maps/town.tmx", "tileset": "town" }
  }
}
```

(`C20` is hexadecimal: 32 colours. The expression count of a portrait comes from `characters.json`, not the manifest. `maps` is reserved for M6 and ignored with a warning today. `tools.gif2zeal` is optional: the default is the SDK checked out next to this repository, or the `GIF2ZEAL` environment variable.)

* Each entry may give the converter outputs (`"zts"`, `"ztp"`, `"ztm"`, plus `"bpp"` and `"compression"` since there is no file name to read them from) instead of a GIF. Given a GIF, its file name **must carry the gif2zeal flags** (`B` bpp, `C` colours, `S` strip, `R`/`L` compression, `U` unique, `M` tile map), so the manifest and the artist's file name cannot disagree; a `bpp` in the manifest that contradicts the name is an error.
* The converter outputs sit next to the GIF. If one is missing or older than the GIF, a build without `--convert` reports an error and with `--convert` runs `gif2zeal.py` (the SDK tool, through the same Python).
* A logical id without art (or with art that failed a check) gets blocks flagged **`MISSING` with size 0 and offset 0**; INDEX still points to them. Missing art is reported at level "missing" and `build --strict` turns it into a failure, so scripts can be built and tested today.
* A block over 65,535 bytes is a build error (section 2).
* `.zts` is stored decoded (`comp` 0) by default; `--keep-compression` keeps the converter's RLE or LZ stream and its `comp` code. A `.ztm` is stored as the converter wrote it (uncompressed).
* The compiler records every art block's size in `memo.layout.txt`, marking missing ones.

### 5.8 Maps (Tiled)

Maps are authored in Tiled and saved as TMX with **CSV** layer encoding, as `tiled2zeal.py` requires. The converter reads only tile layers (`<layer>` elements): it ignores object layers, writes one byte per tile with 255 for empty cells, and fails on tile ids above 254. Spawn points and triggers are therefore read by the compiler itself from the TMX object layers.

**Conventions for a map `Mxx`:**

| Tiled layer | Kind | Use |
|---|---|---|
| `ground` | tile layer (required) | drawn under the player |
| `above` | tile layer (optional) | drawn over the player (roofs, tree tops) |
| `collision` | tile layer (required) | any non-empty cell blocks walking |
| `spawns` | object layer | point objects named like the spawn names in `maps.json`; custom property `facing` = `up`, `down`, `left`, `right` |
| `triggers` | object layer | rectangle objects named like the trigger names in `maps.json` |

* Tile layers are converted by calling `tiled2zeal.py -i map.tmx -l <layer id> [-z]`, using the layer id found by name, so the ZTM bytes are exactly what the SDK tool produces. `-z` (RLE) is optional per map. Maps are single large tile maps (no `-s` screen splitting) unless a map is set to `screens` in the manifest.
* The map's tileset is the image Tiled used (`gid - 1` equals the tile index in the `.zts`, so the GIF must be converted **without** `-u` or the order breaks). The manifest binds the map to its tileset.
* Exploration target: use local world atlas indices 0-91, relocated to hardware
  slots 164-255. Translate exported empty 255 to hardware tile 0 separately;
  never relocate the empty sentinel as a real tile. Collision remains logical
  data. This relocation/translation is not implemented by the converter itself.
* Pixel positions of objects are divided by 16 to give tile coordinates; rectangles are rounded outward.
* The build fails if `maps.json` lists a spawn or trigger the TMX lacks, if a tile id is above 254, or if the three tile layers differ in size. A TMX object whose name `maps.json` does not list is a warning.

**MAPDEF block** (type 8 is portraits; this is type 7):

```text
u8  width, height                 tiles
u8  tileset_id                    index in INDEX tilesets
u8  flags                         bit 0: has 'above' layer
u16 ground_block, above_block, collision_block     TILEMAP blocks (above_block 0 if none)
u8  spawn_count     { u8 x, u8 y, u8 facing }[spawn_count]          index = spawn id used by MAP
u8  trigger_count   { u8 trigger_id, u8 x, u8 y, u8 w, u8 h }[...]  global trigger id (section 5.6)
```

The maximum dimension is 255 tiles per side, a limit of the one-byte tile map header.

## 6. Bytecode

Fixed opcode numbers, one byte each. Jump, call, and branch targets are `u16` offsets in the scene code area. "Cond" is `cmp` 0 `eq`, 1 `ne`, 2 `gte`, 3 `lt`.

| Op | Mnemonic | Operands | Size | JSON op |
|---|---|---|---|---|
| 0x00 | END | | 1 | `end`: scene over; engine reads var `scene` for the next scene |
| 0x01 | SAY | `who:u8`, `ex:u8`, `str:u16` | 5 | `say`; `ex` = expression (0-30, 31 = none) or `style << 5` (0 normal, 1 phone, 2 credits) |
| 0x02 | MAP | `map:u8`, `spawn:u8`, `time:u8` | 4 | `map` |
| 0x03 | FADE | `mode:u8` (0 in/clear, 1 out/black), `t:u8` (x10 ms) | 3 | `fade`; `ms` defaults to 500 when omitted; the longest fade today is 1500 ms = 150 |
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
| 0x15 | PICKMAX | `dst:u8`, `n:u8`, `{var:u8, val:u8} x n` | 3+2n | `pick_max` (the compiler always sets `dst` to the `route` variable; writes `val` of the first maximal `var` into it) |
| 0x20 | JMP | `off:u16` | 3 | (lowering) |
| 0x21 | BRF | `cond:u8`, `var:u8`, `n:u8`, `off:u16` | 6 | `if` on a variable: branch if the test is **false** |
| 0x22 | BRFB | `bit:u8`, `off:u16` | 4 | `if` on a clue bit: branch if the bit is clear |
| 0x23 | CALL | `off:u16` | 3 | `call` (push return pc, depth at most 8) |
| 0x24 | RET | | 1 | end of a called block (depth 0 is a fault) |
| 0x25 | GOTO | `off:u16` | 3 | `goto` (discards the call stack and any explore context) |
| 0x30 | CHOICE | `prompt:u16`, `n:u8`, `{str:u16, off:u16} x n` | 4+4n | `choice`: show the menu, jump to the picked option's code |
| 0x31 | EXPLORE | `obj:u8`, `cvar:u8`, `cmax:u8`, `n:u8`, `onmax:u16`, `exit:u16`, `{trig:u8, fl:u8, off:u16} x n` | 9+4n | `explore`; `obj` = trigger id for the objective marker or 0xFF; `cvar` = clock var or 0xFF; `fl` bit 0 = once |
| 0x32 | XRET | | 1 | end of trigger code: back to the explore loop |
| 0x33 | XEXIT | | 1 | end of the clock body (`on_max`) when it falls through: leave the explore and continue at its `exit` label |
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
Lt1:    <trigger 1 code>      XRET         ; omitted when the code always ends in GOTO / END
Lt2:    <trigger 2 code>      XRET
Lmax:   <on_max code>         XEXIT        ; only when on_max can fall through
Lexit:  <next instruction>
```

Engine semantics: on `EXPLORE`, store the table address, clear the once-mask and pick a trigger; run its code; at `XRET`, if `cvar` is set and `var[cvar] >= cmax`, jump to `onmax`, otherwise continue the loop. A trigger marked `once` is disabled after firing. `GOTO` or `END` leaves the explore and discards its context. `XEXIT` leaves it too and continues at `exit`. The explore context is **explicit state, not a program-counter comparison**: a trigger may `CALL` a block that happens to begin at the exit address (Scene 1 does), so detecting the exit by address would end the explore too early. That is why the clock body ends in `XEXIT` rather than a plain `JMP exit`.

**Blocks**: emitted in JSON order; each block gets a label. A block that can fall off its end gets a trailing `RET`; a block proven to terminate (every path ends in `goto` or `end`) gets none. The scene header's `entry_pc` is the label of `entry`.

## 7. Checks and lints

Errors fail the build; warnings fail only with `--strict`.

| Check | Level | Why |
|---|---|---|
| Everything validate.py does today: JSON, ops, speakers, expressions, variables, bits, maps/spawns/CGs/blocks resolve, text fits the box, choice has 1-3 options, unique choice ids | error | existing behavior |
| Audio names exist in `audio.json`; time-of-day names exist in config | error | new registries |
| `say` text is printable ASCII, at most 3 lines and 127 bytes | error | section 5.4 |
| A choice's prompt lines plus all option lines fit `choice.lines_max` (6, the dialog area height) | warn | all 57 choices fit today (the largest uses 6 lines) |
| Art: every decoded pixel index is below the palette's colour count; a portrait palette has at most 32 colours; tile count matches the declared layout (portrait formula, CG size); tile ids at most 254 in maps | error | section 5.7 |
| Art: logical id referenced by a script (CG, portrait expression, map) has no art in the manifest | info (error with `--strict`) | art TODO list |
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
2. **Trace equivalence** (the main correctness test). Two interpreters execute the same play with the same random seed and must produce the same event trace; a third, the C engine, replays the Python VM's recorded decisions (`ctrace`, section 10):
   * `sim.py` (in the code: `interp.Sim`): interprets the scene JSON directly. It is the reference semantics; the compiled VM must match it exactly.
   * `vm.py` (`interp.VM`): interprets the compiled `memo.dat` read by the independent reader.
   * A trace is the sequence of `say(who, expr, text)`, `map`, `fade`, `cg`, `music`, `sfx`, `tutorial`, `choice(index)`, and variable writes. Run over thousands of seeds across the full ten-scene game (affection-biased and uniform choice policies); any divergence is a compiler or VM bug. Also asserts that every playthrough ends with a route and an ending (it has already caught an unreachable-ending balance bug and a stuck explore).
3. **Golden tests** in `script/tests/`: one tiny scene per construct (each op, nested `if` inside `choice`, `explore` with and without clock, `call` depth 8, `goto` out of explore) with expected hex, including the two examples in section 6.1.
4. **Budget report** (`stats`) fails CI if code, string, or call-depth limits are exceeded.
5. **Coverage report**: percentage of say lines and choice options reached by the seeded runs (guards against untestable branches).

## 10. Engine-side contract (implemented in `engine/`)

The loader is `dat.c` from Wyvern adapted; the changes follow from section 2. The C sources are in [../engine/](../engine); they need only `memo_ids.h` from the build.

| File | Contents |
|---|---|
| `dat_io.h`, `dat_io_zos.c`, `dat_io_stdio.c` | the four file calls (`open`, `close`, `seek`, `read`). The Zeal backend splits every read at 16 KB page boundaries (Wyvern's `dat_read` rule, as a loop); the desktop backend uses stdio |
| `memo_dat.h`, `memo_dat.c` | loader (below) |
| `memo_host.h` | the functions the game must provide (below) |
| `memo_vm.h`, `memo_vm.c` | the script VM, a line-for-line mirror of `interp.VM` |
| `test/trace_main.c` | desktop test harness (not part of the Zeal build) |

```c
uint8_t  dat_open(const char *path, uint32_t expected_crc);   // cookie, version, META; DAT_ERR_CRC if the file is not the build memo_ids.h came from
bool     dat_entry(uint16_t id, DatEntry *out);               // seek id*8, read 8 bytes
bool     dat_read_block(uint16_t id, uint16_t off, void *dst, uint16_t n);  // range-checked read inside a block
bool     dat_load_vars(uint8_t *max, uint8_t *init, uint8_t cap, uint8_t *count);
uint8_t  dat_load_scene(uint8_t scene);                       // code -> dat_code[]; strings stay on disk
uint8_t  dat_load_string(uint16_t id, char *dst, uint8_t cap);// seek offset, seek text; returns bytes used, 0 if it does not fit
uint8_t  dat_index_count(uint8_t table);  bool dat_index_get(uint8_t table, uint8_t i, uint16_t *out);   // CG, portrait, tileset ... block ids
bool     dat_stream_block(uint16_t id, uint8_t *buf, uint16_t chunk, dat_sink_fn sink, void *ctx);      // art, chunk by chunk; missing art succeeds with no chunks
```

The VM has no presentation code. It calls `host_say`, `host_map`, `host_fade`, `host_music`, `host_sfx`, `host_cg`, `host_cg_off`, `host_tutorial`, `host_wait`, `host_end`, `host_choose(prompt, options, n)` and `host_pick_trigger(objective, table_idx, trig_id, n)` (link-time functions the game implements), plus `host_var` when built with `MEMO_TRACE_VARS` (the harness). `memo_vm_init()`, `memo_run_scene(n)` and `memo_run_game()` return 0 or a fault code (`MEMO_ERR_*`: pc out of range or operand past the end, unknown opcode, variable or bit out of range, call overflow or `RET` without `CALL`, explore misuse, bad menu, bad string); the fault scene and pc are in `memo_fault_scene` and `memo_fault_pc`. Corrupt code therefore stops with an error and never reads outside the code buffer. Tutorials show once per game (`memo_tutorial_seen`, 32 ids) unless `memo_tutorial_once` is cleared. A menu's prompt and options share one 226-byte pool (the 6-line budget).

**What the "resident code buffer" is.** It is not application paging. The scene bytecode is just *data*: about 1.2-1.7 KB per scene that the script VM (part of the normal program) interprets. "Resident" means the whole scene's bytecode is read once into a fixed RAM array when the scene starts, so jumps and calls are plain array indexing. The alternative, closer to Wyvern, is to keep only the current block in RAM (at most 320 bytes today) and re-read the caller's block after each `call`. That would save about 3.5 KB of RAM at the cost of more reads, and is a reasonable fallback if RAM turns out tight. The spec keeps the resident buffer as the default because it is simpler and the cost is tiny; `limits.code_buf` in `config.json` (it becomes `CODE_BUF_SIZE` in `memo_ids.h`) can be lowered to 2048 (the largest scene is 1,764 bytes).

**Measured with SDCC 4.4 (`-mz80`)**: loader code 2,346 bytes, VM code 6,216 bytes, Zeal file backend 212 bytes (about 8.8 KB of code). RAM: the code buffer 4,096, the VM 512 (variables 64 + 64 maximums, dialog 128, menu pool 226, call stack 16, state), loader about 20.

Remaining RAM budget for the parts of the game that are not written yet (to confirm with the engine owner):

| Item | Bytes |
|---|---|
| Palette staging (a 256-colour palette) | 512 |
| Art streaming chunk (tile data to video RAM) | 4096 |
| Tutorial-seen mask, variables (already counted above) | 0 |
| **Total with the VM and loader** | **about 9-10 KB** (about 7-8 KB with `code_buf` 2048) |

* Reads must go through the Wyvern `dat_read` helper that splits at 16 KB virtual page boundaries (done in `dat_io_zos.c`). Art is streamed in chunks (`dat_stream_block`) rather than loaded whole: a CG tileset is up to 61,440 bytes. The sink must not touch the file while a stream is running.
* **Decompression** is not needed by default: the build stores art uncompressed (section 5.7), and Zeal reads uncompressed images very quickly even in 4 KB chunks. Only if `--keep-compression` is used must the engine decode gif2zeal's RLE or LZ for `.zts` and tiled2zeal's RLE for `.ztm`; the `comp` byte in each graphics header says which.
* All gameplay state lives in the variable array, so a save is `vars[64]` + scene + tutorial mask. Saving only at scene starts (autosave) keeps the VM state trivial; saving inside a scene is out of scope for v1.
* `MEMO_CONTENT_CRC` covers every block, art included, so any art change changes the constant and forces a recompile of whatever includes `memo_ids.h`. Pass 0 to `dat_open` (skip the check) while art is changing often.

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

Script content totals about 106 KB, plus tables (under 1 KB) and a header of about 2 KB. Art will dominate the file, and is stored uncompressed by default: one CG is 38,400 bytes (320x240 4bpp) or 61,440 bytes (320x192 8bpp), so 19 CGs are 0.73 or 1.17 MB. A portrait base of 32x80 at 8bpp is 10 tiles = 2,560 bytes, plus 256 bytes per head tile per extra expression (a 2x2-tile head costs 1,024 bytes per expression). The palettes are small (32 bytes per 16 colours, 512 bytes for 256). Strings are the second largest part.

## 12. Review decisions and open questions

**Decided in review**

1. **Art:** `gif2zeal.py` produces `.zts` (16x16 tiles) and `.ztp` (RGB565 little endian). CGs are 320x240 at 4bpp or 320x192 at 8bpp. Portraits are 8bpp, **32 pixels wide by 80 tall** (2 x 5 tiles), with alternate heads per expression and 32 colours each (including transparent).
2. **Palettes:** exploration shares hardware palette memory under the
   2026-10-30 allocation in section 5.7; the earlier independent-palette/no-slot-map
   assumption is superseded. Compiler/runtime support still needs updating.
3. **Compression:** art is stored uncompressed by default (it loads very fast); RLE/LZ pass-through is the opt-in `--keep-compression`. The engine needs no decompressor.
4. **Maps:** Tiled (TMX, CSV) converted with `tiled2zeal.py`; spawns and triggers come from TMX object layers (section 5.8).
5. **Code buffer:** a plain RAM array holding the scene's bytecode, not application paging (section 10).
6. **Dialog area:** 6 lines tall, so every choice (at most 6 lines) fits and no script trimming is needed.
7. **Portrait head:** the alternate head is a 2 x 2 tile (32x32 px) region at the top of the 2 x 5 tile base image. The artist's sheet is the 80 px base on top with each alternate head stacked below it (section 5.7).

**Open (deferred)**

1. **CG mode.** 4bpp (16 colours) or 8bpp (richer). Both are supported; per-CG decision.
2. **Audio.** Music and SFX formats and their RAM cost. The registry exists; the assets do not.
3. **Font and charset.** Is the font ASCII-only? Are `{`, `}`, `|`, `~` available? (Current text uses only printable ASCII.)
4. **Save granularity.** Scene-start autosave (recommended for v1) or mid-scene checkpoints (would require saving explore state and the call stack)?
5. **Shared tooling.** Factor the header pack/unpack code into a small module shared with Wyvern Sorrow's `dat_gen.py`, or keep independent?

## 13. Prototype milestones

| # | Deliverable | Status |
|---|---|---|
| M1 | `memo/` package: loader + checks from validate.py, config.json, audio.json registry, new lints (section 7) | **done**: `check` passes with only informational notes |
| M2 | Symbol assignment, lowering, assembler, string packer; `build` writes tables + scene blocks | **done**: `dump` round-trips; golden tests pass |
| M3 | JSON interpreter and bytecode VM with trace comparison | **done**: 5,000 playthroughs, 6.2 million events, zero divergence; 100% of say lines and choice options reached (`trace --seeds 2500`) |
| M4 | Art: manifest, graphics headers, palette checks, `--convert` driving gif2zeal; `--keep-compression` decoders | **done**: stable block allocation with `MISSING` placeholders, portrait/CG/tileset checks, 16 art tests (decoders cross-checked against the SDK encoders, end-to-end through the real `gif2zeal.py`). No art exists yet, so the build reports 26 missing assets |
| M5 | C loader adapted from Wyvern's `dat.c` plus the script VM in C, with a desktop harness | **done**: `engine/` (section 10). `ctrace --seeds 2500` runs 5,000 playthroughs (6.2 million events) through the C engine with replayed decisions: event count, trace CRC and final variables equal the Python VM's, and the C loader's header, INDEX, scene code, strings and art streaming equal the Python reader's for all 126 entries. 9 fault-injection tests; compiles warning-free for Z80 with SDCC. Not yet run on a Zeal machine or emulator |
| M6 | Maps: TMX conventions, `tiled2zeal.py` driver, object-layer reader, MAPDEF packing | not started; a sample TMX must validate against `maps.json` and its ZTM bytes must match the SDK tool's output |

## 14. Implementation notes (milestones 1-5)

Commands (from the `script/` folder; `python` is Python 3):

```text
python tools/memo_dat.py check            validate + lint (also: python tools/validate.py)
python tools/memo_dat.py check --init-audio   write common/audio.json from the names the scripts use
python tools/memo_dat.py build            write build/memo.dat, memo_ids.h, memo.sym, memo.lst, memo.layout.txt
python tools/memo_dat.py build --convert  also run gif2zeal.py on GIFs in assets/manifest.json that are new or changed
python tools/memo_dat.py build --strict   fail while any art is missing (and on warnings)
python tools/memo_dat.py dump --scene 1   header, tables and a disassembly of scene 1 (or --all)
python tools/memo_dat.py stats            code and string sizes per scene
python tools/memo_dat.py trace --seeds 500  JSON interpreter versus VM, policies uniform and first
python tools/memo_dat.py ctrace --seeds 100 builds the C engine with gcc, replays the Python VM's decisions through it, compares (needs gcc, clang or CC)
python -m unittest discover tests         golden tests (hand-computed bytes for every lowering rule)
```

Modules in `tools/memo/`: `spec` (constants), `project` (loading and id assignment), `flow` (op-tree helpers), `check` (diagnostics), `compile` (assembler and lowering), `blocks`, `gfx` (gif2zeal file name flags, RLE/LZ decoders, pixel analysis), `assets` (manifest, converter driver, art checks, block allocation), `pack` (writer), `datread` (independent reader), `disasm`, `interp` (JSON interpreter and VM), `trace` (comparison and coverage), `ctrace` (C engine comparison), `sidecar`, `estimate`, `cli`. The C engine is in `../engine/` (section 10).

Results on the current scripts: 12,746 bytes of code (largest scene 1,764), 1,813 strings in 93,657 bytes, `memo.dat` 111,968 bytes in 102 blocks (all 78 art blocks are `MISSING` placeholders) with a 1,008-byte header (126 entries).

Differences from the first draft of this spec, found while implementing:

* **`XEXIT` opcode.** The draft ended the clock body with `JMP exit` and had the engine clear its explore context when the program counter reached the exit address. The VM exposed the flaw: a trigger may call a block that starts at that address, so the explore ended early. The context is now explicit state and `XEXIT` is the way out (sections 6 and 6.1).
* **Tutorial hints were unchecked.** The old validate.py never checked tutorial text; the new checker found one 4-line hint in Scene 7, now shortened.
* **Test policies.** The comparison harness uses `uniform` (seeded random) and `first`. A "last trigger always" policy is excluded on purpose: it loops forever in Scene 1's walk-on trigger, as a real player who never does anything else would. Both interpreters stop with an error after 500 trigger activations in one explore.
* **Reaching-map lint.** The check that an explore's trigger exists on the *currently loaded* map is not implemented; today it checks that the name exists on some map in `maps.json`. It needs the map data (M6).
