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
| D13 | **Who is shown (2026-11-10).** A speaker's portrait appears on their `CHARS` side and **stays up while the other side speaks**, so a conversation shows both partners. A line by a character with no side (the narrator) takes both down, as do tutorials, waits and the trigger picker; a choice keeps what was showing. The box and the portraits go away together. |
| D14 | **Portraits yield the frame to the box.** The text box has first call on the frame's one upload; portrait streaming uses the frames the box leaves free. A portrait appears as soon as the tiles its expression needs are resident and goes on streaming the rest in the background. |
| D15 | **Never rewrite what is visible.** A different character on a side is blanked, then streamed, then revealed. An expression whose head is not resident yet waits, and the previous expression stays up. A character's tiles and palette stay resident when hidden, so coming back costs only tilemap writes. |
| D16 | **CG (2026-11-10).** `cg X` makes the script wait until the picture is on screen (about half a second), so text after it never appears over the old screen. A CG is invisible while it streams and appears in one frame. A baked CG (palette 126-252) is required; anything else is refused and skipped. The box sits over the CG's bottom rows and wipes in and out; a replaced CG cuts through black unless the script fades (D17). See section 4b. |
| D17 | **Fade (2026-11-11).** `fade black` / `fade clear` scale the palette entries 32-252 (portraits, map, sprites, CG) and never the dialog palette 0-31, so the box stays readable. The fade state persists: after `fade black` the screen stays black, and art loaded meanwhile (a CG, a map) stays hidden until `fade clear`. All palette loads in 32-252 go through `fade_palette` so they honour the level. The script waits for a fade as before. See section 4c. |

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
`script/tools/export_portrait.py` (sheet to the baked GIF). All seven portrait characters
(Brad on the left, the other six on the right) are done and in `memo.dat`. Their tile counts
are Daniel 20, Gord 28, Sandra 36, Georgia 36, Patricia 40, Jane 36, Brad 44, so
each fits its 50-slot region.
CGs, the farm atlas and Brad's walk sprites are baked too (2026-11-11), into the world range:

* **CGs** (`convert_cgs.py`): 320x192, quantized to 127 colours (median cut with k-means
  refinement, snapped to RGB565) at indices 126-252, written as `CG-xx__B8CFD.gif` (253 palette
  entries). Index 0 (black) is unused by the picture and shows below it. At hardware precision
  this is as good as the old 128 colour local palettes or better (about +1 dB); there is no
  dithering. All 23 story CGs are baked and flagged `"baked": true` in `cgs.json` and the manifest.
  **CG-title is the exception**: it is shown at startup, before the dialog and portrait palettes
  exist, so it keeps palette entries 0-127 (`CG-title__B8C80.gif`, `title.c`).
* **Farm atlas and Brad** (`export_farm_pilot.py`): transparent 0 and the pilot's 117 shared
  colours at 126-242, written as `farm__B8CFD.gif` and `brad-farm__B8CFD.gif`. They are in the
  manifest as the tileset `farm` and the sprite sheet of `brad`; the compiler stores each sheet's own
  slice of the palette (the atlas 126-211, Brad 212-242). 10 of the 127 world entries (243-252)
  remain for other actors and effects. The next batch of world art must be exported **with
  this palette** (add its colours to `make_palette`) because map, sprites and effects share the one range.
* **Tile slots are not baked into pixels.** A tile's slot is where the engine loads the sheet
  (world art starts at slot 164), and its position in the sheet; the pilot manifest lists the
  target slot of every sprite tile. Tilemap values are the map converter's job (Phase 5).

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

## 4a. Portraits (done in map mode)

`portrait.c` owns the two portrait regions (slots 64-113 and 114-163) and the 2x4 tile cells
above the box (rows 8-11, columns 0-1 or 18-19). The host asks for them with
`portrait_show(who, side, expr)` from `host_say`, and `game_host_draw` calls
`portrait_draw` after `screen_draw`, giving it the frame if the box did not upload (D14).

Per side the module tracks three things: **resident** (the character whose tiles and
palette are in VRAM and how many tiles have arrived), **wanted** (character and expression
to display) and **shown** (what the cells say now). Each frame:

1. A side whose shown character is no longer wanted is blanked (four cells, no upload).
2. If the frame is free, one step runs: first a side that wants tiles it does not have,
   else a side still finishing its resident character. A step is the palette (the stored slice, loaded
   at its baked indices) or one chunk of `PORTRAIT_CHUNK_TILES` (8) tiles, read with
   `dat_read_block` straight into the tileset at slot base + tiles loaded.
3. A side whose wanted character and expression are resident is revealed: all eight cells for
   a new character, or just the four head cells for an expression change.

Tile order is the file order (compiler-spec.md section 5.7): base tiles 0-7, then head `e`
at `8 + 4(e-1)`. The cells of expression 0 are the base; expression `e` replaces the top
2x2 cells with head `e`. `expr` is clamped: `EXPR_NONE` keeps the character's current
expression (0 for a new one), and an expression the portrait lacks shows the base.

Cost: Brad (44 tiles) is the palette frame plus six chunk frames, and is on screen after the
second (base tiles in); a head late in the file appears when its chunk lands. Everything
after that is tilemap writes. All art streaming (title, portraits, CGs) shares the single
2 KB buffer in `stream.c`, which is only used inside one call; the program's data now ends
near 0xEEC4, leaving about 4.4 KB for the stack (measure on hardware; the fade's 442 byte shadow palette is the latest addition). `portrait_forget()`
drops what is resident when a CG is about to overwrite the portrait slots.

**Validation.** The descriptor is checked before any VRAM write: a 2x4 base, a 2-wide head
inside it, at most 50 tiles, an 8bpp uncompressed tileset block large enough for the tiles, and a
palette slice inside the side's range (32-78 left, 79-125 right, at most 48 entries,
block size exactly `2 + 2n`). A character without usable art logs once per line and shows
nothing; the other side is unaffected.

## 4b. CG mode (done)

`cg.c` shows a CG (`host_cg`) and takes it down (`host_cg_off`). The host sequences it:

1. `host_cg` asks `cg_show()`, which checks the art without touching VRAM: an 8bpp uncompressed
   240 tile picture with no tile map and a palette slice inside **126-252**. Anything else (a
   missing CG, or one whose palette is not baked yet) is logged and refused, and the script simply
   goes on without a picture. On success `portrait_forget()` runs and the host enters a
   `CG_LOAD` state in which **the script waits**, so `cg X` followed by `say` shows the picture
   first and the text after it (D16).
2. Each frame the box has first call on the upload; then `cg_draw` streams one chunk (8 tiles):
   the top nine rows (180 tiles, 23 chunks) into slots 64-243, then the bottom three rows
   (60 tiles, 8 chunks) into slots 1-60. About 31 frames, roughly half a second.
3. Nothing visible points at changing slots: the layer 0 cells stay as they were until the
   last chunk is in. Then, in one frame, the palette (126-252) is loaded, all fifteen layer 0
   rows are written (rows 0-8 slots 64-243, rows 9-11 slots 1-60, rows 12-14 empty), and the box
   moves to rows 9-11 (`screen_set_layout`).
4. **The text box over a CG.** Slots 1-60 hold either the CG's bottom rows or the box. When the box
   is shown it uploads its rows there, so the picture's bottom wipes into the box row by
   row. When it is hidden, `cg_draw` streams the bottom rows back (8 chunks, one per free frame)
   and the box wipes back into the picture. A text request that arrives mid-restore wins and
   the restore starts over later. The first restore chunk calls `screen_invalidate()`, so
   identical text asked for again is uploaded again.
5. **Replacing a CG.** The cells go blank (black) before the first tile of the new CG is
   written, because no double buffer fits in 256 slots; the new picture then appears as in step 3.
   `host_cg_off` clears the layer and moves the box back to rows 12-14; `host_say` shows
   portraits again.
6. **No portraits over a CG** (D6): `host_say` hides them while a CG is wanted. A CG waits until
   any portraits are down, because it overwrites their slots.

Palette: the CG uses 126-252 only, so the dialog palette (0-31) and the portrait palettes (32-125)
stay resident. A baked CG is one whose pixels are 0 (black, shared) or 126-252: set
`"baked": true` on its manifest entry (compiler-spec.md section 5.7); the compiler then checks the
range and stores just the used slice. All 23 story CGs are baked (section 3); only CG-title is not,
and the engine refuses it in CG mode because `title.c` shows it at startup.

## 4c. Palette fade (done)

`fade.c` keeps a **shadow copy** of palette entries 32-252 (442 bytes) and writes them to the video
board scaled by a brightness from 0 (black) to 256 (the art's own colours, copied without scaling).
Entries 0-31, the dialog palette, are never touched.

* `host_fade(mode, t)` (the `fade` op) calls `fade_start(clear, ms)`; `fade_update` runs in
  `game_update` and sets the brightness linearly from where it is now to the target; `fade_draw`
  is the first thing in `game_draw`, so whatever else changes in the frame appears at the right
  level. The script waits for the fade as before (the host's timer), and both end in the same frame.
* The state persists. After `fade black` the picture stays black until `fade clear`, so the
  scripts' usual pattern, `fade black`, change the CG or map, `fade clear`, never shows the
  old picture, the new picture loading, or the cells being blanked.
* **Everything that loads a palette in 32-252 goes through `fade_palette`** (`stream_palette` does for
  portraits and CGs; the map loader in Phase 5 must too). It remembers the colours and shows them at the
  current brightness, so art loaded while black stays black.
* A fade to where the screen already is does nothing (the first scene's `fade clear` on an
  already clear screen only waits). Reversing a fade in the middle continues from the brightness
  it had reached. `ms = 0` jumps.
* Scaling is per RGB565 channel, `value * level >> 8` (rounding down), through two lookup tables built by
  repeated addition each time the level changes, because a Z80 multiply is slow: 221 colours
  cost roughly 6 ms (estimated; measure) and one to four palette writes of at most 64 colours.
  Black is exactly black and level 256 is exactly the art.
* The host takes the dialog box and portraits down when a fade starts (as it does for any
  other timed step), so only the picture fades. A fade that should carry the box and a portrait with it would
  need those to stay up during `HOST_TIMER`; not done.
## 5. Frame protocol (done for the box and portraits)

Main loop order: input, `gfx_wait_end_vblank`, `game_update` (VM and host), `gfx_wait_vblank`,
`render_sprites`, `game_draw` (all VRAM writes). Estimated cost: a 20-tile upload is
5,120 bytes, about 11 ms at 10 MHz with `LDIR`; this must be measured. Hence one upload
per frame, and larger transfers (portraits, CGs) are streamed in chunks of whole tiles, one
chunk per frame, using `dat_read_block` through the shared buffer in `stream.c`. Chunks are 2 KB
(8 tiles), less than the box's 5 KB row, since a chunk also costs a file read from the card or disk
in the same frame. Each frame the box goes first, then the CG, then the portraits.

There is no general residency table. Each module tracks its own slots: `portrait.c` per side, `cg.c`
for the CG tiles, and the box's line cache (which a CG restore invalidates).

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
| 0 | Slot, row and palette constants; init order; remove test code; baked-index tooling | **done** (portraits, CGs, farm atlas and Brad's sprites baked; section 3) |
| 1 | Dialog and tutorial box in map mode, names from `CHARS`, marker | **done** |
| 2 | Choice menu and trigger picker in the box | **done** |
| 3 | Portraits (stream, palette slice, expression cells) | **done** |
| 4 | CG mode (stream, box over rows 9-11, restore on hide) | **done**; the 23 story CGs are baked |
| 5 | Map layers, scroll, sprites, `above` policy | planned |

Tests: `engine/test/screen_main.c` (box against a video model: one-upload budget,
invisible staging, in-place selection updates, scrolling, clipping, overflow layout),
`engine/test/frame_main.c` (real host, screen, portraits and VM against a mock DAT, including
menus, the picker and a mock portrait), `engine/test/portrait_main.c` (the portrait module against
a real `memo.dat` with Brad, Jane and a synthetic Daniel: streaming order, one upload per frame,
expression cells, swaps on one side, hide and return; the test then compares every screen
pixel-for-pixel with the artists' sheets), `engine/test/chars_main.c` (loader against the Python
reader), `engine/test/cg_main.c` (CG mode against a real `memo.dat` with synthetic baked CGs: invisible
streaming and its frame count, one upload per frame, the box over the bottom rows, restore after the
text hides, stale-cache invalidation, a restore interrupted by text, replacing and removing a CG, a CG
requested while the box is up, and refusal of unbaked or missing art; the test compares the screens
pixel-for-pixel with the GIFs). `frame_main.c` also covers the host side: the script waits for the
CG, no portrait over it, and the box and portraits return after `cg_off`. The model
([gfx_mock.c](../engine/test/gfx_mock.c)) renders screens to PPM for review. Run
`python -m unittest discover -s script/tests -p test_engine.py`.

## 8. Open items

* Measure upload and read speed on the emulator and hardware; confirm one upload per frame holds.
* Check a tall sprite's anchor and flips, and the `PRIORITY` flag, on an emulator.
* Decide the `above` layer policy per map (D11), including the sprite alternative.
* Future world art (NPC sprites, props, effects, more tilesets) must be exported with the shared
  palette: 10 of the 127 entries remain, so decide the final world colour budget before the next
  batch (re-quantize the shared set to leave room if needed).
* **Title screen.** CG-title uses palette 0-127 at startup. If it should also be shown by `cg_show`
  (for example on returning to the title), it needs a baked twin.
* Measure the fade on hardware: the scale-and-write of 221 colours is estimated at about 6 ms of the frame (computed in game_draw; it could move to the update phase into a 442 byte staging buffer if it tears or the frame is tight).
* A fade out takes the dialog box and any portrait down at once (the host hides them when a fade starts); only the picture fades.
* Measure the streaming chunk (file read plus 2 KB upload) against the frame, how long a CG really
  takes (estimated 31 frames), and the stack headroom above the 0xEEC4 end of the program's data (about 4.4 KB).
* A script that replaces a CG without `fade black` first still cuts through black for the load time; the story scripts all fade between scenes.
* The map (`host_map`) is not bound, so `host_cg_off` leaves layer 0 black.
