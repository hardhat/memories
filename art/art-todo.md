# Art To-Do

Art requirements derived from [../script/script-plan.md](../script/script-plan.md). Priority: **P1** = needed for the first playable scene set (S1-S3), **P2** = needed for the full game, **P3** = nice to have / cut if budget is tight.

Existing sheets: [brad-bart.png](brad-bart.png), [gord-mcvine.png](gord-mcvine.png), [jane-mcvine.png](jane-mcvine.png), [jane-mcvine-formal.png](jane-mcvine-formal.png), [sandra-stump.png](sandra-stump.png), [georgia-grove.png](georgia-grove.png), [prof-patricia-peters.png](prof-patricia-peters.png).

## Progress Snapshot (2026-10-30)

Reference-sheet work and finished engine assets are separate milestones.
Unchecked asset tasks below do not mean their character designs are missing.

- [x] Review the seven original cast/outfit sheets.
- [x] Generate, download, and review 14 supporting-character reference sheets,
  including young Gord for the flashback; select preferred originals/revisions.
  See section 3 for the complete linked inventory.
- [x] Generate, download, and review all eight P1 outfit/expression references.
  See section 1 for the complete linked inventory.
- [x] Restore Georgia's original cheerful closed-eye smile in the selected
  expression supplement.
- [x] Test OpenArt MCP with reference-conditioned GPT Image 2.5 Sunburst:
  CG-02 preserves Brad and Patricia's designs. The test result is 1600x960;
  downloaded, converted, approved, and installed over the local placeholder.
- [x] Convert the CG-02 pilot to 320x192 with 128 colours using the local
  converter. Verify indexed GIF dimensions, RGB565 palette bytes, and raster
  tile bytes; installed PNG/GIF/engine outputs match the reviewed copies by SHA256.
- [x] Generate CG-01 and CG-03 at verified 1280x768, download to session review
  storage, and convert to 320x192/128-colour previews and engine outputs.
  Verify GIF dimensions, palette indices, RGB565 palette bytes, and tile ordering.
  User approved both reduced previews; installed the PNG/GIF replacements and
  rebuilt `.ztp`/`.zts` outputs. All installed files match the approved review
  outputs by SHA256; existing CG registry paths are unchanged.
- [x] Test PixelLab MCP: grass/dirt Wang tileset, 16 tiles at 16x16, 64x64
  PNG plus metadata downloaded to session storage, not integrated into maps.
- [ ] Convert reference art to the required portrait GIFs and walk sprites.
  Runtime expression indexing and portrait definitions are unchanged.
- [x] Generate final required CGs, review their downsampled/palette-limited output,
  and replace placeholders only after approval.
- [x] Complete all 23 registered CGs, including four separate Sweet endings,
  and wire the ending branches to their approved variants.
- [x] Complete seven later outfit references: Brad homecoming, mascot and
  winter; Jane winter; Sandra witch; Georgia pie; Patricia Mr. Gourd.

**P1 CG status:** CG-01 through CG-03 are approved and installed.
No additional turnaround sheet blocks this P1 CG batch:
the crow, Brad's farm outfit, Patricia's lab coat, and existing
cast designs are available. Reference sheets can guide CGs before portrait or
walk-sprite conversion is complete.

**Later reference work remains:** Brad's orientation/scarecrow/Gord-parody
looks, Jane's formal expressions and remaining P2/P3 expression supplements
in sections 1-2. Homecoming, winter, Sandra's witch, Georgia's pie and
Patricia's Mr. Gourd references are complete and have guided approved CGs.
Brad is off-camera in CG-09, so his selectable Halloween looks remain
portrait/sprite work, not CG blockers. Duplicate-facing side profiles alone
are not a retry requirement.

## 0. Technical Decisions

Decided (see [../script/compiler-spec.md](../script/compiler-spec.md) section 5.7 and 12):

- [x] Tools: `gif2zeal.py` makes `.zts` (tiles) and `.ztp` (palette, RGB565 little endian); `tiled2zeal.py` makes `.ztm` from Tiled maps.
- [x] Tile size 16x16. CG size: 320x240 at 4bpp (16 colours) **or** 320x192 at 8bpp (256 colours); choose per CG.
- [x] Portraits: 8bpp, **32 pixels wide by 80 tall** (2 x 5 tiles) base image plus alternate heads per expression, 32 colours each including transparent.
- [x] The alternate head is a **2 x 2 tile (32x32 px) region at the top of the base image**. One GIF per portrait, 32 px wide: the 80 px base image (expression 0) first, then one 32x32 head for each further expression stacked below it, in the order listed in `characters.json` (`have`, then `todo`). A character with `n` expressions is `32 x (80 + 32 * (n - 1))` px, exported as `name__B8C20.gif` (`C20` = 32 colours). The compiler rejects other sizes and says what it expected.
- [x] Exploration uses the shared tile/palette budgets below, superseding the
  earlier independent-palette assumption. Art is stored uncompressed in the DAT.
- [x] Files are GIFs with `__` filename flags for the converter (for example `cg01__B8C20.gif`); the compiler needs the flags in the name. Map tilesets must NOT use the unique flag (`U`), so tile order matches Tiled, and hold at most 255 tiles.
- [x] Save GIFs with every palette entry you use at the index you want: the pixel index is stored as is, and the build checks it is inside the palette.
- [x] CG production workflow: request 1280x768 source PNGs (5:3), then downsize
  and palette-limit locally with [convert_cgs.py](../script/tools/convert_cgs.py).
  Its current output is 320x192, 8bpp, 128 colours (`__B8C80.gif`), plus
  `.ztp` and `.zts`. Verify actual generated dimensions; the OpenArt CG-02
  pilot was 1600x960, which has the same aspect ratio.

Still to confirm:

- [x] All 23 required CGs use 320x192 8bpp/128 colours; no output-mode
  exceptions were needed. 320x240 4bpp remains an available alternative.
- [x] Walk-sprite size: 16x32; two animation frames per stored direction,
  with one reused as idle.
- [ ] File naming: `<character>.gif` per portrait sheet (`jane__B8C20.gif`), `cg<id>__B8C<nn>.gif` for CGs, `sprite-<character>.gif` for walk sprites.
- [ ] The existing turnaround sheets are high-resolution PNG. They need to be redrawn or downscaled and palette-reduced to the sizes above.

### Exploration tiles and palettes (2026-10-30 decisions)

Orthogonal maps on a 16x16 grid, with readable RPG building fronts/top
surfaces rather than isometric art. Backgrounds should be quieter and lower
contrast than character silhouettes. Generate at native tile resolution.

The shared 256-tile memory layout retains both portraits:

| Hardware tile slots | Count | Use |
|---|---:|---|
| 0 | 1 | Empty tile |
| 1-63 | 63 | Dialog area |
| 64-113 | 50 | Left portrait |
| 114-163 | 50 | Right portrait |
| 164-255 | 92 | Location scenery, sprites and effects together |

Each portrait reserves a 2x5-tile base plus up to ten additional 2x2 heads:
10 + 10*4 = 50 tiles (up to eleven expressions including the base).
Keep both portraits as the baseline; reclaim portrait space only if story
needs and a concrete location budget justify it. The existing portrait file
layout remains unchanged; its old 32-colour export limit is a legacy tooling
constraint, not the new hardware budget.

- [x] Moving character: front/back/one side, two frames each, two tiles per
  frame = 12 unique tiles. Mirror X for the opposite side.
- [x] Stationary NPC: one 16x32 pose = two tiles; extra facings/poses cost more.
- [x] Hardware supports independent X/Y mirroring of each 16x16 sprite tile.
  Symmetric wider costumes may reuse mirrored halves; head/feet and animation
  differences still count. Test the pie costume silhouette before final export.
- [x] Budget only simultaneously resident characters, but include all their
  resident animation frames and effects. Example: Brad plus three stationary
  NPCs costs 18 tiles, leaving 74 for scenery/effects.
- [x] Shared palette entry 0 is transparent for sprites and layer 1; layer 0
  displays its colour normally. Portrait budgets are 48 colours each including
  shared transparency, dialog 32 colours, world/sprites/effects 128 colours
  including shared transparency. These are not independent 256-colour palettes.
- [ ] Assign exact non-overlapping hardware palette ranges and local-to-global
  pixel remapping before exporting production atlases; count entry 0 only once.
- [x] Preserve atlas tile order (no unique/deduplication converter flag).
  Tiled uses local atlas indices, not hardware tile-slot numbers.
  Remap exported empty 255 to hardware tile 0 separately from relocating real
  local world indices 0-91 into slots 164-255. Collision is logical data,
  not a display tile layer to relocate.
- [x] Keep tile indices and semantic palette roles stable across variants.
  Prefer palette swaps for dusk/night and snow where sufficient; use matching
  replacement tiles when snow changes outlines/coverage. Keep sprite skin,
  clothing and effect roles separate from terrain lighting roles as needed.
- [ ] Implement/validate shared VRAM allocation, palette remapping and map
  empty-cell translation in the runtime/build pipeline. Documentation records
  the target contract; current compiler checks do not enforce it yet.

Terrain starts with one 16-tile corner-Wang grass/dirt set for a farm pilot.
Reserve the rest of the 92-tile budget for props, buildings, sprites and effects;
do not spend it all on terrain combinations. Author TMX with CSV layers
`ground`, optional `above`, `collision`, plus `spawns` and `triggers` objects.
Day/dusk/night/snow previews and sprite/background readability are acceptance
checks before expanding to full locations.

- [ ] Farm terrain production pilot: PixelLab
  `504c9bda-e262-429a-a949-6ce413958a41`, submitted for 16 corner-Wang
  tiles at 16x16, muted olive autumn grass / warm compacted dirt, low detail
  and basic shading. Downloaded [source PNG](terrain/farm-grass-dirt.png)
  and [PixelLab metadata](terrain/farm-grass-dirt.json); added
  [Tiled tileset](../map/farm-grass-dirt.tsx) with all 16 corner-Wang
  definitions validated against metadata bounding boxes.
  Verified 64x64 RGBA source, 60 RGB colours. User approved the terrain sample
  appearance in Tiled. Palette consolidation and sprite-readability review
  remain before marking complete.
  The user's `farm.tmx`, `farmland.tsx` and placeholder image are unchanged;
  placeholder tile meanings do not match this atlas automatically.
  Added a separate [terrain sample map](../map/farm-terrain-sample.tmx),
  24x18 tiles, with a central yard, connected dirt paths and a southwest plot.
  Validated dimensions, image references and all adjacent Wang corners;
  rendered a preview for initial visual review. This is terrain-only, not
  runtime M04: collision/spawns/triggers and sprite contrast tests remain open.
  Standard generation does not enforce a fixed palette; these are source
  pixels, not a final hardware-indexed atlas.
  Dirt base ID: `1559eee0-0ed5-4035-8457-01ee2c9010d5`;
  grass base ID: `8724c56c-a468-4fb2-adc9-7e86e6b4f8ec`.
  Reuse these bases when adding connected terrain rather than independently
  regenerating the shared surface.

## 1. Brad Bart (main character): P1

Brad's original sheet has a turnaround; the expression supplement below adds
the ten requested reference expressions. He appears on the left in every dialog
scene, so he needs the most variants.

### P1 outfit and expression reference sheets

Generated with OpenArt GPT Image 2.5 Sunburst from each character's canonical
sheet, downloaded as 1024x1024 PNGs, and given an initial visual review:

- [x] [Brad expressions](brad-bart-expressions.png): all ten listed default
  expressions are present with consistent identity.
- [x] [Brad farm outfit](brad-bart-farm.png): open brown plaid flannel over the
  black tee, jeans, muddy work boots; neutral, smile, surprised, worried, laugh.
- [x] [Jane expressions](jane-mcvine-expressions.png): neutral/smile anchors,
  worried, and laugh.
- [x] [Sandra expressions](sandra-stump-expressions.png): neutral/slight-smile
  anchors, mortified, and smirk.
- [x] [Georgia expressions](georgia-grove-expressions.png): neutral/smile anchors,
  laugh, and worried. Selected the smile revision using the original
  turnaround's cheerful closed-eye smile as reference; the prior supplement
  is archived outside the repository.
- [x] [Patricia expressions](prof-patricia-peters-expressions.png): neutral/serious
  anchors, flustered, and frustrated.
- [x] [Georgia cafe apron](georgia-grove-cafe.png): sage-green bib apron over the
  default outfit, with front/back construction details and neutral, smile,
  surprised, laugh, worried expressions.
- [x] [Patricia lab coat](prof-patricia-peters-lab.png): open white lab coat over
  the default outfit, with neutral, smile, surprised, serious, worried
  expressions.

All eight P1 reference sheets are downloaded and initially reviewed.
The requested emotions are readable at reference resolution. Georgia's revised
default smile is distinct from neutral but close to laugh; her apron
neutral/smile remain subtle. Brad's confused expression reads somewhat annoyed;
check readability again when adapting to small portraits.
These supplements do not replace the original turnarounds. The checkboxes
below still track game-ready portraits/outfits, not high-resolution references;
runtime portrait GIFs and expression indexing have not been changed.

**Game-ready portrait expressions (default outfit: black tee, jeans, white sneakers):**
- [ ] Neutral
- [ ] Smile
- [ ] Laugh
- [ ] Surprised
- [ ] Embarrassed / blush
- [ ] Worried / nervous
- [ ] Determined
- [ ] Confused / thinking
- [ ] Candid (mid-blurt, wide-eyed; used in S5 and S9)
- [ ] Sad / vulnerable (S3 confession, S9 confession)

**Outfits (neutral + smile + surprised each, at minimum):**

Completed later CG references, downloaded and reviewed at 1024x1024:

- [x] [Brad homecoming](brad-bart-homecoming.png): orange-and-black scarf,
  optional pennant.
- [x] [Brad mascot](brad-bart-mascot.png): maroon-scarfed raven suit with
  Brad's identity, head on/off and detached head.
- [x] [Brad winter](brad-bart-winter.png): brown shearling-collar jacket,
  jeans, winter boots and removable gloves.

These establish CG continuity; game-ready portrait/sprite tasks below remain open.

- [ ] Farm work: muddy boots, flannel or work shirt (S1, S3 boots gag, S6, S8). **P1**
- [ ] Orientation look with name tag (S2); same default outfit plus tag. **P2**
- [ ] Homecoming: school-colors flag/scarf (S4). **P2**
- [ ] Raven mascot costume, head on and head off (S4 G route). **P2**
- [ ] Halloween costume 1: Scarecrow (S9). **P2**
- [ ] Halloween costume 2: Raven (S9). **P3**
- [ ] Halloween costume 3: "Gord" parody (beard and flannel) (S9). **P3**

**Walk sprite:** 4 directions x 3 frames (idle, step, step), default outfit, plus farm outfit and mascot costume (map only). **P1**

## 2. Existing Characters: Missing Expressions and Outfits

The script uses these expressions beyond the current sheets (smile, wink, serious, surprised etc.).
Unchecked tasks in this section require game-ready portraits/outfits, not
just the completed high-resolution references.

### Jane McVine (red hair, green tee)
Have: smile, wink, serious, surprised.

- [x] [Winter work reference](jane-mcvine-winter.png): olive insulated jacket,
  black trousers, boots, gloves and barn-key detail; used in approved endings.

Game-ready assets:
- [ ] Worried / anxious (S4, S5, S6, S8). **P1**
- [ ] Laughing (S1 wheelbarrow, S8 haggling). **P1**
- [ ] Candid / blushing (S5, S9). **P2**
- [ ] Formal outfit, expressions: neutral, smile, surprised, candid (S9). Have the sheet; need expressions. **P2**
- [ ] Farm work outfit (overalls or flannel over tee) for S6/S8. **P3**

### Sandra Stump (goth)
Have: neutral, slight smile, annoyed, surprised.

- [x] [Halloween witch reference](sandra-stump-witch.png) is downloaded and reviewed
at 1024x1024: existing gothic outfit plus pointed hat and short plum-lined cape;
neutral, slight smile, mortified and full smile. Runtime asset tasks remain open.

- [ ] Mortified / blushing (S5, S9). **P1**
- [ ] Smirk (S3, S8). **P1**
- [ ] Deadpan stare (S1, S2). **P2**
- [ ] Full smile (rare; trivia night gag, S9). **P2**
- [ ] Muddy / ruffled after the goose fight (S6). **P3**
- [ ] Halloween costume (e.g., a goth witch or a raven). Expressions: neutral, smile, mortified. **P2**

### Georgia Grove (blonde, cafe)
Have: neutral, smile, surprised, wink.

- [x] [Pumpkin-pie costume reference](georgia-grove-pie.png) is downloaded and reviewed
at 1024x1024: padded circular pie sandwich-board, crust rim and cream decoration;
neutral, closed-eye smile, surprised and embarrassed. Runtime assets remain open.

- [ ] Laughing (S4 mascot gag). **P1**
- [ ] Worried / sad (S5 candid window, S8). **P1**
- [ ] Embarrassed (S5). **P2**
- [ ] Thoughtful (S6, S8 recipe tweak). **P3**
- [ ] Cafe apron outfit (S1, S2, S5, S8). Expressions: neutral, smile, surprised. **P1**
- [ ] Halloween costume. Expressions: neutral, smile, surprised. **P2**

### Prof. Patricia Peters
Have: neutral, smile, serious, thinking.

- [x] [Mr. Gourd reference](prof-patricia-peters-gourd.png) is downloaded and reviewed
at 1024x1024: tan trench coat, round sunglasses, removable mustache, black
heels, lifting pose, disguised neutral/caught and undisguised reveal.
This supplies CG-08 continuity; runtime portraits and walk sprite remain open.

- [ ] Flustered / blushing (S1 gate, S3 invitation). **P1**
- [ ] Frustrated at technology (S2 projector, S3 computer). **P1**
- [ ] Scared / worried (S3, S5 candid, S8, S9). **P2**
- [ ] Cold / disappointed (S7 if Brad lied or exploited her candor). **P2**
- [ ] Candid (S5, S9). **P2**
- [ ] **"Mr. Gourd" disguise:** trench coat, sunglasses, fake mustache, the stylish heels still visible (S8, S9). Expressions: neutral, caught/panicked. Also a walk sprite. **P2**
- [ ] Lab coat outfit (S3). Expressions: neutral, serious, worried. **P1**
- [ ] Halloween costume (e.g., a "mad scientist" gag). **P3**

### Gord McVine
Have: neutral, smile, surprised, angry.
- [ ] Worried / guilty (S1, S6, S9). **P2**
- [ ] Sad / tender (S9 truth scene). **P2**
- [ ] Tiny pumpkin-lover smile (talking to pumpkins, S6). **P3**
- [ ] Parade outfit (hat and tie, S4). **P3**
- [ ] Halloween "costume" (comedic: he wears his normal clothes with a name tag). **P3**

## 3. New Supporting Characters

Mostly small portraits (neutral + one extra), plus a walk sprite where noted.

### Supporting-character design sheets

Reference sheets generated with OpenArt GPT Image 2.5 Sunburst using the
existing cast sheets as style or family references. These are 1024x1024 PNG
design references, not converted portraits or walk sprites; the asset tasks
below remain open until their required game-ready images exist.

Downloaded and visually reviewed; preferred reference versions selected:

- [x] [Crow](crow.png).
- [x] [Tour guide](tour-guide.png).
- [x] [Icebreaker leader](icebreaker-leader.png).
- [x] [Alumni trio](alumni-trio.png).
- [x] [Freshman raven mascot](freshman-raven-mascot.png).
- [x] [Big Mel](big-mel.png).
- [x] [Brad's mother, young](brads-mother-young.png).
- [x] [Dr. Eleanor Peters, program era](dr-eleanor-peters-young.png).
- [x] [Crowd](crowd.png).
- [x] [Mr. Pruitt](mr-pruitt.png).
- [x] [Dean Whitlock](dean-whitlock.png).
- [x] [Young Daniel Bart](daniel-bart-young.png).
- [x] [Present-day Daniel Bart](daniel-bart.png).
- [x] [Young Gord McVine](gord-mcvine-young.png) (for CG-11).

- Revision selection (preferred images use the standard filenames above):
  - Crow, tour guide, icebreaker leader, and young Daniel: revisions preserve
    the designs and useful expression/prop panels while adding opposite-facing
    profiles.
  - Freshman mascot: revision preserves the costume, fixes the profiles, and
    makes the nervous expression clearly distinct.
  - Present-day Daniel: revision reads convincingly older than Brad and young
    Daniel, while preserving the outfit, pie box, and family resemblance.
    Duplicate-facing side profiles remain acceptable for this reference use.
  - Eleanor: revision has a more angular, mature face, narrower eyes, and
    clearer expressions, distinguishing her better from Patricia.
  - Dean: revision retains his identity and expressions while matching the
    textured pixel-art rendering of the other sheets more closely.
  - The other six supporting sheets retain their original generations.
  - Superseded originals are archived outside the repository in session
    storage. No further retries are planned solely for duplicate side profiles.

- [ ] **Crow**: recurring mascot. Portrait or icon: perched, stealing a tag, holding the tag, holding a mustache. Walk/fly sprite (map). **P1**
- [ ] Tour guide (S2). **P3**
- [ ] Icebreaker leader (S2, Sandra route). **P3**
- [ ] Alumni trio from Brad's dad's class (S4), one shared portrait with three variants. **P2**
- [ ] Freshman raven mascot (S4). **P3**
- [ ] Big Mel, the rival vendor (S8). **P2**
- [ ] Janitor with the archive key (S7). **P3**
- [ ] Dean (S9, "afraid of squirrels" candid gag). **P3**
- [ ] Brad's dad, young: game-ready photo portrait; reference and CG-07/CG-11
  appearances are complete. **P2**
- [ ] **Daniel Bart, present day** (S10 epilogue): an older version of Brad's design, with a pie box. Neutral, smile, sheepish, serious. **P2**
- [x] Brad's mother, young: reference complete and included in approved CG-11;
  no separate portrait needed. **P3**
- [x] Dr. Eleanor Peters (Patricia's mother), program era (photo only):
  reference complete and used in approved CG-07/CG-11; mature program
  director, not a fellow student. **P2**
- [ ] Generic crowd sprites for the market and dance floor (4-6 variants). **P2**

## 4. Map Tilesets and Environments

Tile sets for the maps listed in section 4 of the script plan. Each has a day variant; some have extras.

- [ ] **Town:** Town Square, Main Street with cafe/tavern/gate exteriors. Variants: parade (S4), market stalls (S8). **P1**
- [ ] **Farm:** Farm Road, yard, barn, fields, shed, Patch 7. Variants: day, dusk (S1), night with glow (S6, S9), snow (S10). **P1**
- [ ] **Interiors:** Farmhouse and attic; Grove Cafe; Log and Stump Tavern; lecture hall; science lab (+loading dock); student centre; library, stacks, and archive. **P1** (lab, lecture hall, farmhouse) / **P2** (rest)
- [ ] **Campus:** Quad (day, bonfire night variant), football field and bleachers. **P1** (quad) / **P2** (rest)
- [ ] **Great Hall** dance floor: decorations, dance-floor tiles, punch table, glowing pumpkins. **P2**
- [ ] **Pumpkin tile variants:** normal, large, glowing (Patch 7), blooming (S9). **P1**
- [ ] Day-clock UI (S1: dusk countdown), objective marker, interaction prompt icon, bingo card UI (S2). **P1**
- [ ] Text box frame, choice menu frame, name plate, affection indicator (optional), clue journal icons (optional). **P1**

## 5. CGs (full-screen special images)

From the CG list in the script plan. Many reuse the existing character designs, so the art needs the same outfits and expressions listed above.

**Production status:** All 23 registered CGs (CG-01 through CG-13, including
CG-04a-d, CG-10a-d and all four
CG-10 Sweet variants) are approved and installed at their
existing paths in `cg-placeholders`; the directory name is retained for registry
compatibility. The required CG set is complete; optional extra CGs remain open.
The successful OpenArt CG-02 consistency pilot
([source PNG](https://cdn.openart.ai/openart-ai/production/2026-10/create-image/S3B9Ym2wdG7dt46E5tcJ/gpt-image-2.5-sunburst-edit-1_1793396805849_c6977ba1.png))
has been downloaded, locally converted, approved, and installed in the game.
The 320x192, 128-colour preview retains the character
silhouettes, red extinguisher, foam, and crow; the tiny name-tag lettering is
not readable at that size. Dimensions, palette bytes, and tile ordering have
been verified against the GIF.
CG-01 and CG-03 have also been downloaded and converted through the same pipeline:

- [CG-01 source](https://cdn.openart.ai/openart-ai/production/2026-10/create-image/S3B9Ym2wdG7dt46E5tcJ/gpt-image-2.5-sunburst-edit-1_1793400933495_e61d417e.png)
  (OpenArt `YVuDcQIkTNJcpcY1v1KU`): verified 1280x768. The crow silhouette
  and distant orange patch remain clear in the 320x192/128-colour preview.
- [CG-03 source](https://cdn.openart.ai/openart-ai/production/2026-10/create-image/S3B9Ym2wdG7dt46E5tcJ/gpt-image-2.5-sunburst-edit-1_1793400941083_170e2a5d.png)
  (OpenArt `dUcgJjGbhucRnKA3wRQt`): verified 1280x768. Four distinct goggled
  students and glowing orange foam remain readable at game resolution;
  Patricia is off-camera, consistent with the four-figure composition.

All three candidates and their GIF/engine outputs are retained in session
review storage. Palette and tile bytes match the converted GIFs. The user
approved all three candidates; their source PNGs and GIFs now
replace the local placeholders, with rebuilt `.ztp`/`.zts` files. SHA256 checks
confirm every installed output matches its approved review copy.
Use [cgs.json](../script/common/cgs.json) and each scene's script for exact
composition and character/outfit requirements.

### Homecoming batch: approved and installed

CG-04a-d replace the local placeholders at their existing registry paths.
All four sources are verified 1280x768; converted previews are
320x192 indexed GIFs with 128 colours. RGB565 palette bytes and raster tile
bytes match each GIF. Rebuilt `.ztp`/`.zts` outputs and installed PNG/GIF files
all match their approved session review copies by SHA256.

| CG | OpenArt history ID | Initial reduced-preview review |
|---|---|---|
| CG-04a | `pqPvVWwGmikjgWfHiQcS` | Jane's shoulder lean, Brad's scarf, gold pumpkin and bonfire remain readable. |
| CG-04b | `chyHlk2nRRYfr38wJUb9` | Sandra's quiet smile, rooftop setting and distant bonfire remain readable. |
| CG-04c | `harXA2zxNS4dk5mt5TLC` | Brad's headless mascot suit and the detached head in Georgia's lap are clear. |
| CG-04d | `FCfdAmLBPoaoVTUspSDV` | Patricia's glasses/lanyard/clipboard and the respectful gap from Brad remain clear. |

### Cafe and Patch Seven batch: approved and installed

CG-05 and CG-06 replace the local placeholders at their existing registry
paths. Both sources are verified 1280x768 and converted to
320x192/128-colour indexed GIFs. RGB565 palette bytes and raster tile bytes
match each GIF. Installed PNG/GIF files and rebuilt `.ztp`/`.zts` outputs
all match their approved session review copies by SHA256.

| CG | OpenArt history ID | Initial reduced-preview review |
|---|---|---|
| CG-05 | `a7MC2crnlpVuqRznUvEd` | Four recognizable friends, Georgia's apron, the tart and separate candle remain readable. Expressions lean toward friendly amusement rather than exaggerated confession. |
| CG-06 | `DPogZq3nDG66lwGhKDGY` | Giant glowing pumpkins, golden-hour field, Gord and his KEEP OUT / PATCH 7 plank remain clear. |

### Archive batch: approved and installed

CG-07 (OpenArt `7B7ctP3RrseS1vQMtqJ4`) replaces the local placeholder at its
existing registry path. Source dimensions are verified 1280x768; the 320x192/128-colour
preview retains Brad, the three-person photograph and the SEALED memo.
Small photo identities/text lose detail at game resolution. RGB565 palette
and raster tile bytes match the converted GIF. Installed PNG/GIF files and
rebuilt `.ztp`/`.zts` outputs match the approved review copies by SHA256.

### Loading dock batch: approved and installed

CG-08 (OpenArt `wVQlM6y6iezOzpipSBHc`) replaces the local placeholder at its
existing registry path. Source dimensions are verified 1280x768; the 320x192/128-colour
preview retains the open van, glowing pumpkin, Mr. Gourd disguise and clearly
visible black high heel. RGB565 palette and raster tile bytes match the GIF.
Installed PNG/GIF files and rebuilt `.ztp`/`.zts` outputs match the approved
review copies by SHA256.

### Halloween and flashback batch

- CG-09 (OpenArt `yXUAyr8yvxbNwiQlBPLm`) is approved and installed at its existing
  registry path. Verified 1280x768 source
  and 320x192/128-colour preview; RGB565 palette and raster tile bytes match
  the GIF. Sandra's witch outfit, Georgia's pie, glowing punch, full moon
  and reacting crowd remain readable. Brad stays out of view so it works
  with all three player-selected costumes. Installed PNG/GIF files and rebuilt
  `.ztp`/`.zts` outputs match the approved review copies by SHA256.
- CG-11 (OpenArt `3n66Wcyq6d8JfcP66Odm`) is approved and installed at its existing
  registry path. Verified 1280x768 source and
  320x192/128-colour preview; RGB565 palette and raster tile bytes match the GIF.
  Young Daniel/Gord, mature Eleanor, Brad's mother, program banner and glowing
  punch remain readable at game resolution. Installed PNG/GIF files and
  rebuilt `.ztp`/`.zts` outputs match the approved review copies by SHA256.

**Shared:**
- [x] CG-01 (S1): Attic window at dusk, glowing Patch 7, the crow on the sill. **P1**
- [x] CG-02 (S2): Lecture hall extinguisher chaos, Patricia over her glasses, the crow with the name tag in the window. **P1**
- [x] CG-03 (S3): Lab flooded with glowing orange foam, four silhouettes. **P1**
- [x] CG-05 (S5): Glowing Pumpkin Surprise and the group around the table, mid-confession. **P2**
- [x] CG-06 (S6): Patch 7 at golden hour, giant glowing pumpkins, Gord in silhouette. **P2**
- [x] CG-07 (S7): Archive by flashlight, the Pumpkin Research Program binder, a photo of three young people. **P2**
- [x] CG-08 (S8): The van at the lab loading dock, Mr. Gourd lifting a pumpkin, one stylish shoe. **P2**
- [x] CG-09 (S9): Great Hall, glowing punch bowl, crowd mid-confession. **P2**
- [x] CG-11 (S10): Flashback of the original dance 25 years ago: young Daniel, Gord, and Eleanor under the program banner, glowing punch bowl in the foreground, Brad's mother in the crowd. **P2**
- [x] CG-12 (S10): Farm ending: Brad and Gord on the snowy porch, the crow on the railing, a carved glowing pumpkin between them. **P2**
- [x] CG-13 (S10): Good Friends ending: group photo on the tavern steps with Brad, all four heroines and Gord, the crow photobombing in the corner. **P2**
See [../script/common/cgs.json](../script/common/cgs.json) for the full set of scripted images.

### Ending variants batch

Separate True Love and Sweet images are approved for production for all four
routes. Keep existing CG-10a-d IDs for True Love; add separate Sweet registry
entries and branch calls when the corresponding reviewed art is approved.
Do not install pending images or change runtime references before approval.

All six results are downloaded and initially reviewed. All four Sandra/Georgia
CGs are approved and installed. Existing CG-10b/c IDs retain the True Love
images; new CG-10b-sweet and CG-10c-sweet registry entries are used only by
their respective Sweet branches. New entries are appended to preserve existing
numeric CG IDs. Installed source/GIF/palette/tile files match approved review
copies by SHA256.
Focused epilogue validation/compilation passes, with expected partial-scene
warnings about flags set elsewhere. Branch checks confirm True Love keeps
CG-10b/c and Sweet selects the new variants; existing CG index order is unchanged.

- CG-10b True Love: `4PfBmKIPhtAlLjnUX2RO`; Sandra's full smile,
  joined hands, old/new photographs.
- CG-10b Sweet: `WXFixw4fe7yaWKxNRZQi`; tentative smile, close but not
  touching, old photograph only.
- CG-10c True Love: `r67tVGlVnKCa0w78Xac1`; cafe-counter kiss,
  ordinary pumpkin tart and brass key.
- CG-10c Sweet: `mddmupYfNafv14lxd9He`; planning a bakery map,
  no kiss or cafe key.
- [Brad winter reference](brad-bart-winter.png): `0Zai2mzgZiVhGCZsPd5S`;
  brown shearling-collar work jacket, jeans and winter boots.
- [Jane winter reference](jane-mcvine-winter.png): `xAUHwnu0cGed1njcCNTi`;
  olive insulated work jacket, black trousers and winter boots.

Verified actual source sizes: all four CGs are 1280x768 and both reference
sheets are 1024x1024. Each CG preview is 320x192 with 128 colours; palette
indices, exact RGB565 palette bytes and raster tile bytes are validated.
Sandra's True Love image shows joined hands below the table and both framed
photos; Sweet keeps hands separate and only the old photo. Georgia's kiss/key
and separate bakery-map scene remain readable without magical pastry glow.
Winter outfits preserve both characters' identities; Brad's profiles face
the same direction, a previously accepted nonblocking reference-sheet flaw.
Jane/Patricia variants use Brad's winter sheet in all
four images and Jane's winter sheet in both Jane images:

- CG-10a True Love: `dDLEc7y1mUPNTgj0SXZa`; snowy farm kiss, snow pumpkin
  and barn key.
- CG-10a Sweet: `ALqNeKcF4v0L3HSrV6XE`; leaning against the snow pumpkin
  watching sunset, no kiss or key.
- CG-10d True Love: `ehHXDZxrvYcDgaSSMUnO`; cautious doorway kiss,
  Patricia's tan trench coat and clear safety goggles.
- CG-10d Sweet: `EJ5PGBvZ5NVoOKw0BTDU`; cocoa thermos exchange,
  tan trench coat and ordinary rectangular glasses.

All four are approved and installed. Existing CG-10a/d IDs retain True Love;
new CG-10a-sweet and CG-10d-sweet entries are appended to preserve existing
numeric CG IDs and selected by their respective Sweet branches.
Installed PNG/GIF/palette/tile files match approved review copies by SHA256.
Actual sources are 1280x768; previews are 320x192
indexed GIFs with 128 colours. Palette index bounds, exact RGB565 palette
bytes and raster tile bytes are validated.
Brad's winter jacket appears in all four, Jane's olive jacket in both hers.
Jane True Love shows the kiss and joined hands, but the barn key is not clearly
readable at game resolution. Jane Sweet seats them separately against the
snow pumpkin rather than standing; sunset and non-contact staging are clear.
Patricia True Love retains clear safety goggles; Sweet uses normal glasses
and a thermos exchange. Neither includes the disguise accessories.
Patricia references include her canonical identity and established trench-coat
sheet, explicitly excluding the mustache and sunglasses in both endings.
Runtime winter portraits/sprites are not complete.

### Final shared endings batch

- CG-12 (OpenArt `tsTZvaJC7n7sB7U825Oo`): Brad and Gord on the snowy porch,
  carved glowing pumpkin between them, crow on railing and welcome-home note.
  Uses Brad's winter sheet and Gord's canonical identity; Gord wears a plain
  forest-green insulated coat over his grey-green work shirt.
- CG-13 (OpenArt `27ZRIejv9BDiZ9RRI73g`): timed-camera tavern-steps group
  photo with exactly Brad, Jane, Sandra, Georgia, Patricia, Gord and one crow.
  Brad/Jane use winter sheets; Gord repeats the forest-green coat, Patricia
  wears her tan trench without disguise, Sandra adds a black wool coat and
  Georgia a camel coat with winter leggings.

Both are approved and installed at their existing registry paths. Installed
PNG/GIF/palette/tile files match the approved review copies by SHA256;
conversion freshness checks pass. Actual sources are 1280x768; both previews are
320x192 indexed GIFs with 128 colours. Palette index bounds, exact RGB565
palette bytes and raster tile bytes are validated.
CG-12 clearly retains Brad/Gord, winter coats, welcome-home note, central
glowing carved pumpkin and crow on the rail.
CG-13 contains all six distinct characters once: Gord/Patricia/Brad behind
Jane/Sandra/Georgia, with unobstructed faces and a foreground crow photobomb.
Winter layers and Georgia's closed-eye smile remain readable. The crow is
larger than prompted but stays clear of faces; Sandra retains her canonical
fishnets under the added coat.

**Route:**
- [x] CG-04a-d (S4): Bonfire moment with Jane / Sandra / Georgia / Patricia. **P2**
- [ ] CG-06a-d (S6): Route-specific farm moment (optional). **P3**
- [x] CG-10a-d (S10): True Love ending images, one per route. **P2**
  - [x] CG-10b/c: Sandra and Georgia approved and installed.
  - [x] CG-10a/d: Jane and Patricia approved and installed.
- [x] CG-10 separate Sweet variants (4), with matching registry/scene wiring. **P2**
  - [x] CG-10b-sweet / CG-10c-sweet: approved, installed and wired.
  - [x] CG-10a-sweet / CG-10d-sweet: approved, installed and wired.

**Possible additional CGs (not yet in the script plan, do only if the script needs them):**
- [ ] Brad and Gord at the dinner table (S1). **P3**
- [ ] Jane and Brad on the tractor float (S4 J route). **P3**
- [ ] Sandra and Brad on the tavern roof (S4 S route). **P3**
- [ ] The final cure/preserve choice: the pumpkins' bloom (S9). **P3**

## 6. Priority Summary

| Priority | What |
|---|---|
| **P1** | Remaining game-ready portraits/expressions and farm outfit, walk sprites (all main characters), crow, town/farm/lab/lecture-hall tiles, UI frames. P1 references and CGs are complete. |
| **P2** | Remaining game-ready outfits, costumes, expressions, supporting-character portraits/sprites and interiors. All required shared/route CGs and Sweet variants are complete. |
| **P3** | Extra expressions, extra costumes, route CGs for S6, bonus CGs |

## 7. Notes

- Keep the **crow** consistent across all CGs. It is a recurring gag.
- Jane's formal outfit should only appear in S9 so it stays a surprise.
- For every outfit, include the same expression set as the default (neutral, smile, surprised) so the script can switch outfits without adding conditions.
- Reference-only outfit additions are inventoried here. Update
  [characters.json](../script/common/characters.json) and the runtime asset
  mappings when converted portraits are ready; do not mark high-resolution
  reference supplements as installed portrait expressions.
