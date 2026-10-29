# Art To-Do

Art requirements derived from [../script/script-plan.md](../script/script-plan.md). Priority: **P1** = needed for the first playable scene set (S1-S3), **P2** = needed for the full game, **P3** = nice to have / cut if budget is tight.

Existing sheets: [brad-bart.png](brad-bart.png), [gord-mcvine.png](gord-mcvine.png), [jane-mcvine.png](jane-mcvine.png), [jane-mcvine-formal.png](jane-mcvine-formal.png), [sandra-stump.png](sandra-stump.png), [georgia-grove.png](georgia-grove.png), [prof-patricia-peters.png](prof-patricia-peters.png).

## 0. Technical Decisions

Decided (see [../script/compiler-spec.md](../script/compiler-spec.md) section 5.7 and 12):

- [x] Tools: `gif2zeal.py` makes `.zts` (tiles) and `.ztp` (palette, RGB565 little endian); `tiled2zeal.py` makes `.ztm` from Tiled maps.
- [x] Tile size 16x16. CG size: 320x240 at 4bpp (16 colours) **or** 320x192 at 8bpp (256 colours); choose per CG.
- [x] Portraits: 8bpp, about 80x32 base image plus alternate heads per expression, 32 dedicated colours each (including transparent).
- [x] Files are GIFs with `__` filename flags for the converter (for example `cg01__B8R.gif`); map tilesets must NOT use the unique flag (`U`), so tile order matches Tiled.

Still to confirm:

- [ ] Portrait geometry: is 80x32 the whole portrait or only a head strip (compiler-spec section 12, question 1).
- [ ] The 256-entry palette split between UI, left portrait, right portrait and scene art (compiler-spec section 5.7 proposal). Pixel indices are absolute, so each GIF must be authored with its colours at its slot's indices.
- [ ] Walk-sprite size (suggest 16x24 or 16x32).
- [ ] File naming: `<character>-<outfit>.gif` per portrait sheet, `cg<id>__B8R.gif` for CGs, `sprite-<character>.gif` for walk sprites, map tilesets without `U`.
- [ ] The existing turnaround sheets are high-resolution PNG. They need to be redrawn or downscaled and palette-reduced to the sizes above.

## 1. Brad Bart (main character): P1

Brad's sheet has a turnaround and no expression set. He appears on the left in every dialog scene, so he needs the most variants.

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
- [ ] Mortified / blushing (S5, S9). **P1**
- [ ] Smirk (S3, S8). **P1**
- [ ] Deadpan stare (S1, S2). **P2**
- [ ] Full smile (rare; trivia night gag, S9). **P2**
- [ ] Muddy / ruffled after the goose fight (S6). **P3**
- [ ] Halloween costume (e.g., a goth witch or a raven). Expressions: neutral, smile, mortified. **P2**

### Georgia Grove (blonde, cafe)
Have: neutral, smile, surprised, wink.
- [ ] Laughing (S4 mascot gag). **P1**
- [ ] Worried / sad (S5 candid window, S8). **P1**
- [ ] Embarrassed (S5). **P2**
- [ ] Thoughtful (S6, S8 recipe tweak). **P3**
- [ ] Cafe apron outfit (S1, S2, S5, S8). Expressions: neutral, smile, surprised. **P1**
- [ ] Halloween costume. Expressions: neutral, smile, surprised. **P2**

### Prof. Patricia Peters
Have: neutral, smile, serious, thinking.
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

**Shared:**
- [ ] CG-01 (S1): Attic window at dusk, glowing Patch 7, the crow on the sill. **P1**
- [ ] CG-02 (S2): Lecture hall extinguisher chaos, Patricia over her glasses, the crow with the name tag in the window. **P1**
- [ ] CG-03 (S3): Lab flooded with glowing orange foam, four silhouettes. **P1**
- [ ] CG-05 (S5): Glowing Pumpkin Surprise and the group around the table, mid-confession. **P2**
- [ ] CG-06 (S6): Patch 7 at golden hour, giant glowing pumpkins, Gord in silhouette. **P2**
- [ ] CG-07 (S7): Archive by flashlight, the Pumpkin Research Program binder, a photo of three young people. **P2**
- [ ] CG-08 (S8): The van at the lab loading dock, Mr. Gourd lifting a pumpkin, one stylish shoe. **P2**
- [ ] CG-09 (S9): Great Hall, glowing punch bowl, crowd mid-confession. **P2**
- [ ] CG-11 (S10): Flashback of the original dance 25 years ago: young Daniel, Gord, and Eleanor under the program banner, glowing punch bowl in the foreground, Brad's mother in the crowd. **P2**
- [ ] CG-12 (S10): Farm ending: Brad and Gord on the snowy porch, the crow on the railing, a carved glowing pumpkin between them. **P2**
- [ ] CG-13 (S10): Good Friends ending: group photo on the tavern steps with Brad, all four heroines and Gord, the crow photobombing in the corner. **P2**
- [ ] CG-09 (S9) and CG-04a-d / CG-10a-d: see the CG lists in [../script/common/cgs.json](../script/common/cgs.json) for the full set of scripted images.

**Route (one per route, 4 images each):**
- [ ] CG-04a-d (S4): Bonfire moment with Jane / Sandra / Georgia / Patricia. **P2**
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
- When a sheet gains a new outfit, update this file and the portrait list in `characters.json` once it exists.
