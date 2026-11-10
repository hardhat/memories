# Screen specification

How the 320x240 screen is divided between the map, CGs, portraits and the dialog box,
and how the engine draws it. It records the decisions made on 2026-11-03 and the
current state of the code. The data formats stay in [compiler-spec.md](compiler-spec.md);
this file covers what the engine does with them. Source: [../engine/](../engine).

Status legend: **done** is implemented and covered by the desktop tests and a Z80
compile; **planned** is decided but not written. Nothing here has run on an emulator or
on hardware yet; timing figures are estimates until measured.

## 1. Decisions

| # | Decision |
|---|---|
| D1 | One 320x240 8bpp mode: a 20x15 grid of 16x16 tiles, two tile layers (0 behind, 1 in front) and sprites. 8bpp tilemap entries are one byte, so there are exactly **256 tile slots** for everything. The layers have separate scroll registers. |
| D2 | Slot map (section 2) and palette map (section 3) are fixed. Asset tools **bake** the final slot and palette indices into the art; the engine never remaps at run time (the SDK's `pal_offset` path is a per-byte loop and would also move index 0). |
| D3 | **Map mode**: layer 0 shows the map full screen, 15 rows. The dialog box is three rows on layer 1 (rows 12-14). With no text, the map is simply full screen. |
| D4 | **Portraits** are layer 1 tiles, 2 wide by 4 tall (a 32x64 waist-up bust), in rows 8-11 (0-based), directly above the box: Brad on the left (columns 0-1), everyone else on the right (columns 18-19). `characters.json` fixes each character's side, so no horizontal flip is needed and tiles suffice. An expression change rewrites four tilemap cells (the 2x2 head at the top); it uploads nothing. A portrait with `n` expressions uses `8 + 4*(n-1)` tiles, at most 48 of its 50 slots. Changed from 2x5 on 2026-11-10: the generator makes busts, and a 2x4 base keeps the face large. |
| D5 | **CG mode**: the 320x192 CG occupies tile rows 0-11 of layer 0. Rows 12-14 are black. The text box moves up to rows 9-11, **over the CG's bottom three rows**. |
| D6 | **No portraits during a CG.** The speaker's name shows on the first text line instead. |
| D7 | **Text is not drawn onto the CG image.** It would be too busy to read; the box replaces the pixels. |
| D8 | **Frame protocol.** `host_*` calls (which run in `game_update`, outside vblank) only record state. All VRAM writes happen in `game_draw`, right after vblank starts. A frame performs at most **one tile upload**. A visible tile cell is never pointed at slots being rewritten: stage invisibly, then reveal. |
| D9 | `gfx_initialize()` runs before `memo_host_initialize()`, because the host's screen module writes VRAM and opens `memo.dat`. |
| D10 | **Sprites** carry `SPRITE_FLAG_PRIORITY` (the hardware "behind FG" bit) and flips through `add_sprite`'s `flags`. 16x32 characters use one hardware sprite (`SPRITE_FLAG_TALL`, tile and tile+1) instead of two. |
| D11 | **The map's `above` layer** shares layer 1 with the dialog overlay. While a dialog is open the camera must be tile-aligned; the overlay cells are restored from the map data when the box is hidden. If the `above` tiles on a map are sparse enough, drawing them as sprites instead is to be evaluated per map. |
| D12 | Speaker names come from the `CHARS` block (`dat_load_char`), not from a table compiled into the engine. The placeholder trigger picker is the exception: its place names come from `MEMO_TRIGGER_NAMES` in `memo_ids.h`, because they exist only for play-testing before the maps do. |

### Why the CG and the box overlap (D5)

All 23 approved CGs have **240 unique tiles** (measured: no deduplication is possible).
The dialog needs 60 resident tiles and slot 0 stays empty, which leaves 195 slots, fewer
than a full CG needs. While text is shown, only 180 CG tiles (the top nine rows) can be
resident. The box therefore must cover the remaining three rows.

In CG mode the CG's top nine rows live in slots 64-243. The bottom three rows (60 tiles)
live in the dialog slots 1-60, which the text also uses. Both layers' cells for those
three rows point at slots 1-60, so showing text is "upload the text tiles", and hiding
it is "stream the CG's bottom 60 tiles back into slots 1-60" (about 15 KB, a few frames).

A side effect: 37 of the 80 say-lines that occur while a CG is up (a linear walk of the
scene scripts) are spoken by characters that have portraits. Those lines show the name
only (D6), because a 50-tile portrait cannot fit beside 180 + 60 CG and text tiles.

## 2. Tile slots and rows

| Slots | Count | Map mode | CG mode |
|---|---:|---|---|
| 0 | 1 | Empty tile (all index 0) | Same |
| 1-60 | 60 | Text box tiles | Text box tiles, or CG rows 9-11 |
| 61 | 1 | Continue arrow | Same |
| 62-63 | 2 | Spare | Spare |
| 64-113 | 50 | Left portrait (2x4 base + up to ten 2x2 heads, 48 tiles) | CG rows 0-8 (slots 64-243) |
| 114-163 | 50 | Right portrait (same) | (CG) |
| 164-255 | 92 | Scenery, sprites, effects | (CG up to 243, then 12 spare) |

| Tile rows | Map mode | CG mode |
|---|---|---|
| 0-7 | Map | CG |
| 8 | Map; portraits start (2x4 tiles, rows 8-11) | CG |
| 9-11 | Map; portraits | Text box, over the CG's bottom three rows |
| 12-14 | Text box | Black |

Constants live in [layout.h](../engine/layout.h).

## 3. Palette

Index 0 is shared: transparent on layer 1 and on sprites, an ordinary colour (black) on
layer 0. Budgets count it once.

| Indices | Count | Use |
|---|---:|---|
| 0 | 1 | Shared transparent / black |
| 1-31 | 31 | Dialog (nine defined: box, frame, text, name, phone, credits, selection, arrow) |
| 32-78 | 47 | Left portrait |
| 79-125 | 47 | Right portrait |
| 126-252 | 127 | Map, sprites and effects, or the CG (128 including index 0) |
| 253-255 | 3 | Spare |

The dialog palette is loaded once and never replaced, so text stays correct in every
mode. A CG must be quantized to 127 colours plus black.

**Baking.** Art carries its final indices, so loading it is a plain copy. **Portraits are
baked and checked by the compiler** (index 0 or the side's range, palette slice stored
as `first`..`last`; compiler-spec.md section 5.7). Two tools produce them:
`script/tools/assemble_portrait.py` (candidates to `art/portraits/<name>.png`) and
`script/tools/export_portrait.py` (sheet to the baked GIF). Brad (left) and Jane
(right) are done and in `memo.dat`; the other five are right-side. Their tile counts
are Daniel 20, Gord 28, Sandra 36, Georgia 36, Patricia 40, Jane 36, Brad 44, so
each fits its 50-slot region.
CGs, the farm atlas and sprites are **planned**: `convert_cgs.py` and
`export_farm_pilot.py` still use local indices and must be changed to emit these ranges.

## 4. Dialog box (done)

Three tile rows of 16 px are six text lines of 8 px, 36 columns wide (288 px), starting at
x=16 so every glyph is on the aligned fast path:

| Line | Use |
|---|---|
| 0 | Name plate (at most 16 characters; empty for the narrator; hidden for credits) |
| 1-3 | Dialog text, pre-wrapped by the compiler at `\n` |
| 4-5 | Spare; the blinking continue arrow sits in the last cell (row 3, column 19) |

Styles: normal, phone and credits differ in text colour only for now; credits drop the
name plate. Lines longer than 36 columns and text beyond three lines are cut off,
because `draw_text_char` does not clip aligned writes.

Behaviour (`screen.c`):

* **Line model.** Every content call lays out the six lines, compares them with the lines
  already in VRAM, and marks only the rows that differ. Identical text costs nothing, even
  after the box was hidden.
* **First showing**: changed rows are composed one per frame and uploaded into slots 1-60
  while the layer 1 cells stay empty. A one-line text needs one upload. When the last row
  is staged the cells appear at once.
* **Replacing visible content**: the box stays up. Each changed row is blanked, uploaded
  and revealed in a single frame, so the text wipes in from the top.
* **Moving a selection** updates in place: the changed rows are uploaded without being
  blanked, so the box does not flicker. This relies on the upload finishing before the
  raster reaches the box (rows 12-14 are the last fifth of the frame, and the estimated
  upload is about 11 ms into a 16.7 ms frame). It must be confirmed on an emulator, and it
  will not hold for the CG-mode box in rows 9-11 without a second look.
* **Hiding** clears the layer 1 cells only; the art underneath is not touched.
* A dialog, menu or list ignores confirm input until every row is on screen.
* The box is up while the host is in a dialog, tutorial, choice or trigger pick, so
  back-to-back content never drops it; any other script step takes it down.

### Choice menu

The prompt (may be empty) comes first, then each option, up to six lines in all. Prompt
and option text are split at `\n`. The selected option's lines get a full-width highlight
(palette 7) and a `>` in the left margin. If the content needs more than six lines the
prompt gives way first, and every option keeps at least one line. Up/Left and Down/Right
move the selection and wrap; A or Start confirms.

### Trigger picker (placeholder)

A stand-in for walking the map, until maps exist: a header ("Go where? Goal: <place>")
over a list of the places currently available, five at a time, scrolling to keep the
selection visible, with " k/n" appended to the header when the list scrolls. The names are
the trigger names from `maps.json`, emitted by the compiler as `MEMO_TRIGGER_NAMES` in
`memo_ids.h` (underscores shown as spaces).

## 5. Frame protocol (done for the box)

Main loop order: input, `gfx_wait_end_vblank`, `game_update` (VM and host), `gfx_wait_vblank`,
`render_sprites`, `game_draw` (all VRAM writes). Estimated cost: a 20-tile upload is
5,120 bytes, about 11 ms at 10 MHz with `LDIR`; this must be measured. Hence one upload
per frame, and larger transfers (portraits, CGs) are streamed in 4 KB chunks of whole
tiles, one chunk per frame, using `dat_read_block`.

A residency table (planned) records what each slot region holds (text, CG bottom,
portrait character, map tileset) so nothing is streamed twice.

## 6. Sprites

`add_sprite(x, y, tile, flags)` takes the top-left corner in screen pixels. Flags are the
`SPRITE_FLAG_*` values in [main.h](../engine/main.h): `PRIORITY` (behind layer 1, so
dialog and portraits cover the sprite), `FLIP_X`, `FLIP_Y`, and `TALL`, a software flag
that sets the hardware 32 px option and is masked off before the hardware sees it.
A tall sprite shows `tile` over `tile+1`, which matches how the walking sprites are
exported (two stacked tiles per frame). Flips of tall sprites, and the tall sprite's
anchor, are assumed from the SDK header and **must be checked on an emulator**.

## 7. Implementation status

| Phase | Content | State |
|---|---|---|
| 0 | Slot, row and palette constants; init order; remove test code; baked-index tooling | Constants, init order and cleanup **done**; asset tools **planned** |
| 1 | Dialog and tutorial box in map mode, names from `CHARS`, marker | **done** |
| 2 | Choice menu and trigger picker in the box | **done** |
| 3 | Portraits (stream, palette slice, expression cells) | planned |
| 4 | CG mode (stream, box over rows 9-11, restore on hide) | planned |
| 5 | Map layers, scroll, sprites, `above` policy | planned |

Tests: `engine/test/screen_main.c` (box against a video model: one-upload budget,
invisible staging, in-place selection updates, scrolling, clipping, overflow layout),
`engine/test/frame_main.c` (real host, screen and VM against a mock DAT, including menus
and the picker), `engine/test/chars_main.c` (loader against the Python reader). The model
([gfx_mock.c](../engine/test/gfx_mock.c)) renders screens to PPM for review. Run
`python -m unittest discover -s script/tests -p test_engine.py`.

## 8. Open items

* Measure upload and read speed on the emulator and hardware; confirm one upload per frame holds.
* Check a tall sprite's anchor and flips, and the `PRIORITY` flag, on an emulator.
* Decide the `above` layer policy per map (D11), including the sprite alternative.
* Rework the converters to emit baked slot and palette indices, with CGs at 127 colours plus black.
* Fade: palette fading needs a 512-byte staging copy; for now a fade is only a timer.
* The compiler still checks portraits against 32 colours and has no slot or palette-range check.
