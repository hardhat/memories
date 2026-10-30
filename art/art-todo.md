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
- [ ] Generate final CGs, review their downsampled/palette-limited output,
  and replace placeholders only after approval.

**P1 CG status:** CG-01 through CG-03 are approved and installed.
No additional turnaround sheet blocks this P1 CG batch:
the crow, Brad's farm outfit, Patricia's lab coat, and existing
cast designs are available. Reference sheets can guide CGs before portrait or
walk-sprite conversion is complete.

**Later reference work remains:** P2/P3 outfits and expression supplements in
sections 1-2, especially Brad's orientation/Halloween looks,
Jane's formal expressions, Sandra and Georgia's Halloween costumes, Patricia's
Mr. Gourd disguise, and Gord's remaining emotions. Create these as needed before
the corresponding later CGs rather than delaying the P1 CGs. The freshman's
mascot sheet defines the borrowed costume; Brad's wearer reference is now available.
CG-08 needs the Mr. Gourd disguise; S9 art needs the applicable formal/costume
references. Duplicate-facing side profiles alone are not a retry requirement.

## 0. Technical Decisions

Decided (see [../script/compiler-spec.md](../script/compiler-spec.md) section 5.7 and 12):

- [x] Tools: `gif2zeal.py` makes `.zts` (tiles) and `.ztp` (palette, RGB565 little endian); `tiled2zeal.py` makes `.ztm` from Tiled maps.
- [x] Tile size 16x16. CG size: 320x240 at 4bpp (16 colours) **or** 320x192 at 8bpp (256 colours); choose per CG.
- [x] Portraits: 8bpp, **32 pixels wide by 80 tall** (2 x 5 tiles) base image plus alternate heads per expression, 32 colours each including transparent.
- [x] The alternate head is a **2 x 2 tile (32x32 px) region at the top of the base image**. One GIF per portrait, 32 px wide: the 80 px base image (expression 0) first, then one 32x32 head for each further expression stacked below it, in the order listed in `characters.json` (`have`, then `todo`). A character with `n` expressions is `32 x (80 + 32 * (n - 1))` px, exported as `name__B8C20.gif` (`C20` = 32 colours). The compiler rejects other sizes and says what it expected.
- [x] Each image has its own palette (the Video Board SDK loader supports independent palettes per 8bpp image), so there is no shared palette budget. Art is stored uncompressed in the DAT.
- [x] Files are GIFs with `__` filename flags for the converter (for example `cg01__B8C20.gif`); the compiler needs the flags in the name. Map tilesets must NOT use the unique flag (`U`), so tile order matches Tiled, and hold at most 255 tiles.
- [x] Save GIFs with every palette entry you use at the index you want: the pixel index is stored as is, and the build checks it is inside the palette.
- [x] CG production workflow: request 1280x768 source PNGs (5:3), then downsize
  and palette-limit locally with [convert_cgs.py](../script/tools/convert_cgs.py).
  Its current output is 320x192, 8bpp, 128 colours (`__B8C80.gif`), plus
  `.ztp` and `.zts`. Verify actual generated dimensions; the OpenArt CG-02
  pilot was 1600x960, which has the same aspect ratio.

Still to confirm:

- [ ] Confirm exceptions to the current 320x192 8bpp/128-colour CG workflow;
  320x240 4bpp remains an available alternative, not the current converter mode.
- [ ] Walk-sprite size (suggest 16x24 or 16x32).
- [ ] File naming: `<character>.gif` per portrait sheet (`jane__B8C20.gif`), `cg<id>__B8C<nn>.gif` for CGs, `sprite-<character>.gif` for walk sprites.
- [ ] The existing turnaround sheets are high-resolution PNG. They need to be redrawn or downscaled and palette-reduced to the sizes above.

## 1. Brad Bart (main character): P1

Brad's original sheet has a turnaround; the expression supplement below adds
the ten requested reference expressions. He appears on the left in every dialog
scene, so he needs the most variants.

### P1 outfit and expression reference sheets

Generated with OpenArt GPT Image 2.5 Sunburst from each character's canonical
sheet, downloaded as 1024x1024 PNGs, and given an initial visual review:

- [Brad expressions](brad-bart-expressions.png): all ten listed default
  expressions are present with consistent identity.
- [Brad farm outfit](brad-bart-farm.png): open brown plaid flannel over the
  black tee, jeans, muddy work boots; neutral, smile, surprised, worried, laugh.
- [Jane expressions](jane-mcvine-expressions.png): neutral/smile anchors,
  worried, and laugh.
- [Sandra expressions](sandra-stump-expressions.png): neutral/slight-smile
  anchors, mortified, and smirk.
- [Georgia expressions](georgia-grove-expressions.png): neutral/smile anchors,
  laugh, and worried. Selected the smile revision using the original
  turnaround's cheerful closed-eye smile as reference; the prior supplement
  is archived outside the repository.
- [Patricia expressions](prof-patricia-peters-expressions.png): neutral/serious
  anchors, flustered, and frustrated.
- [Georgia cafe apron](georgia-grove-cafe.png): sage-green bib apron over the
  default outfit, with front/back construction details and neutral, smile,
  surprised, laugh, worried expressions.
- [Patricia lab coat](prof-patricia-peters-lab.png): open white lab coat over
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

**Expressions (default outfit: black tee, jeans, white sneakers):**
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

Homecoming CG references are downloaded and reviewed at 1024x1024:
[Brad homecoming](brad-bart-homecoming.png) adds an orange-and-black scarf and
optional pennant; [Brad mascot](brad-bart-mascot.png) preserves the existing
maroon-scarfed raven suit with Brad's identity, head on/off and detached head.
These establish CG-04 continuity; runtime portrait/sprite tasks below remain open.

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

### Jane McVine (red hair, green tee)
Have: smile, wink, serious, surprised.
- [ ] Worried / anxious (S4, S5, S6, S8). **P1**
- [ ] Laughing (S1 wheelbarrow, S8 haggling). **P1**
- [ ] Candid / blushing (S5, S9). **P2**
- [ ] Formal outfit, expressions: neutral, smile, surprised, candid (S9). Have the sheet; need expressions. **P2**
- [ ] Farm work outfit (overalls or flannel over tee) for S6/S8. **P3**

### Sandra Stump (goth)
Have: neutral, slight smile, annoyed, surprised.

[Halloween witch reference](sandra-stump-witch.png) is downloaded and reviewed
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

[Pumpkin-pie costume reference](georgia-grove-pie.png) is downloaded and reviewed
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

[Mr. Gourd reference](prof-patricia-peters-gourd.png) is downloaded and reviewed
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

- Downloaded and visually reviewed; preferred versions selected:
  [crow](crow.png), [tour guide](tour-guide.png),
  [icebreaker leader](icebreaker-leader.png), [alumni trio](alumni-trio.png),
  [freshman raven mascot](freshman-raven-mascot.png), [Big Mel](big-mel.png),
  [Brad's mother, young](brads-mother-young.png),
  [Dr. Eleanor Peters, program era](dr-eleanor-peters-young.png),
  [crowd](crowd.png), [Mr. Pruitt](mr-pruitt.png),
  [Dean Whitlock](dean-whitlock.png), [young Daniel Bart](daniel-bart-young.png),
  [present-day Daniel Bart](daniel-bart.png),
  and [young Gord McVine](gord-mcvine-young.png) (for CG-11).
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
- [ ] Brad's dad, young (from the photo in S4 and S7, and the CG-11 flashback). **P2**
- [ ] **Daniel Bart, present day** (S10 epilogue): an older version of Brad's design, with a pie box. Neutral, smile, sheepish, serious. **P2**
- [ ] Brad's mother, young (small background figure in CG-11; no portrait needed). **P3**
- [ ] Dr. Eleanor Peters (Patricia's mother), young (photo only). **P2**
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

**Production status:** CG-01 through CG-09, including CG-04a-d, and CG-11 are approved and installed at their
existing paths in `cg-placeholders`; the directory name is retained for registry
compatibility. Other local CGs remain placeholders.
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
- [ ] CG-12 (S10): Farm ending: Brad and Gord on the snowy porch, the crow on the railing, a carved glowing pumpkin between them. **P2**
- [ ] CG-13 (S10): Good Friends ending: group photo on the tavern steps with Brad, all four heroines and Gord, the crow photobombing in the corner. **P2**
See [../script/common/cgs.json](../script/common/cgs.json) for the full set of scripted images.

**Route (one per route, 4 images each):**
- [x] CG-04a-d (S4): Bonfire moment with Jane / Sandra / Georgia / Patricia. **P2**
- [ ] CG-06a-d (S6): Route-specific farm moment (optional). **P3**
- [ ] CG-10a-d (S10): Ending images, one per route (True Love; Sweet reuses the image with a small change). **P2**
- [ ] CG-10 separate Sweet variants (4). **P3**

**Possible additional CGs (not yet in the script plan, do only if the script needs them):**
- [ ] Brad and Gord at the dinner table (S1). **P3**
- [ ] Jane and Brad on the tractor float (S4 J route). **P3**
- [ ] Sandra and Brad on the tavern roof (S4 S route). **P3**
- [ ] The final cure/preserve choice: the pumpkins' bloom (S9). **P3**

## 6. Priority Summary

| Priority | What |
|---|---|
| **P1** | Brad expressions (default outfit) and farm outfit, walk sprites (all main characters), crow, town/farm/lab/lecture-hall tiles, UI frames, missing P1 expressions, CG-01 to CG-03 |
| **P2** | Remaining outfits and costumes, remaining interiors, supporting characters, Mr. Gourd, shared CGs for S5-S9, route CGs for S4 and S9 |
| **P3** | Extra expressions, extra costumes, route CGs for S6, Sweet endings, bonus CGs |

## 7. Notes

- Keep the **crow** consistent across all CGs. It is a recurring gag.
- Jane's formal outfit should only appear in S9 so it stays a surprise.
- For every outfit, include the same expression set as the default (neutral, smile, surprised) so the script can switch outfits without adding conditions.
- Reference-only outfit additions are inventoried here. Update
  [characters.json](../script/common/characters.json) and the runtime asset
  mappings when converted portraits are ready; do not mark high-resolution
  reference supplements as installed portrait expressions.
