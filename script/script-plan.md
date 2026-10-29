# Memories of Ravenwood College: Script Plan

Story-beat plan for the nine incidents (scenes) and the epilogue (S10). Step 2 turns each beat into full script, per scene and per route. Character and incident background lives in [../README.md](../README.md).

Route codes used below: **J** = Jane McVine, **S** = Sandra Stump, **G** = Georgia Grove, **P** = Prof. Patricia Peters.

---

## 1. Presentation Format

Every scene is about **10 minutes** and mixes three presentation modes:

| Mode | What the player sees | Used for |
|---|---|---|
| **Map** | Top-down tile map (Stardew-style), 4-direction walking, bump-to-interact, objective marker | Travel, exploring, optional interactions, "walk and talk" triggers |
| **Dialog** | Art-sheet portrait left (Brad) and right (speaker), text box at the bottom, 1-3 lines per box | Most of the story, choices |
| **CG** | Full-screen special image with the text box overlaid | Key emotional or comedic moments, 1-3 per scene |

### Portraits
- Brad: left. Everyone else: right. Exceptions: two non-Brad speakers may share the screen (one each side) when Brad is off screen.
- Available expressions from the art sheets: Jane (smile, wink, serious, surprised), Sandra (neutral, slight smile, annoyed, surprised), Georgia (neutral, smile, surprised, wink), Patricia (neutral, smile, serious, thinking), Gord (neutral, smile, surprised, angry). **Brad's sheet has no expression set** (extra art is tracked in [../art/art-todo.md](../art/art-todo.md)).
- Jane's formal outfit ([jane-mcvine-formal.png](../art/jane-mcvine-formal.png)) is used for the Halloween dance only, so it stays a surprise.

### Pacing Template (per scene, ~10:00)

| Time | Act | Mode | Notes |
|---|---|---|---|
| 0:00-1:30 | **A. Opening** (shared) | Map + Dialog | Establish place and goal, short walk |
| 1:30-4:30 | **B. Shared middle** | Map + Dialog | Scene's main event, shared clue, comedy set-piece |
| 4:30-8:00 | **C. Route beat** | Dialog + CG | Route-specific, ~35-45 text boxes |
| 8:00-10:00 | **D. Shared close** | Dialog + CG | Mystery beat, state update, hook into next scene |

Budget guide: ~90-110 text boxes per scene at ~5 s each, plus about 1.5 min of walking. About half the text boxes are shared and about 40 are route-specific. This keeps shared content in one place in the data and only the route beat multiplied by four.

---

## 2. Choice and State Design

### Variables (all fit in one byte)
- `aff_j`, `aff_s`, `aff_g`, `aff_p`: affection, 0-30.
- `route`: 0 = unset, 1-4 = J/S/G/P. Set at the end of Scene 3.
- `clues`: bit flags, one bit per clue (CL1-CL8, below).
- `trust_gord`: 0-3.
- `ending`: 0 = unset, 1 = True Love, 2 = Sweet, 3 = Good Friends, 4 = Farm (Solo). `F_CURED`: set if the pumpkins were cured in S9.
- Per-scene flags (named in each scene, e.g. `F_CONFESSED_LAB`).

### Route Structure
- **Scenes 1-3 (Meet phase):** All four heroines appear. Choices decide who Brad spends the "focus time" with, and the route beats below are the four possible focus interactions. Each stop has its own beat for every route so no one is missed.
- **End of Scene 3 (lock-in):** Brad walks up to whoever he wants to invite to Homecoming. If that person's `aff` is at least 3 she accepts and `route` is set. If not, she declines and `pick_max` picks the higher-affection of the **other** heroines among Jane, Sandra and Georgia, who then asks Brad instead (Patricia never asks, because she is his professor). A route is always assigned.
- **Scenes 4-9 (Route phase):** Only the locked route's Act C plays. The other heroines still cameo in shared acts (A, B, D) so the town stays populated.

### Choice Types (aim for 3-4 per scene, at least 1 that matters beyond the scene)
1. **Affection choices** change `aff_x` by +1 or +2 (a wrong read costs 0, not negative, to keep it forgiving).
2. **Mystery choices** investigate or ignore. They set clue bits.
3. **Character choices** (honesty vs diplomacy, trust vs secrecy). They set flags that change dialog or the ending later.
4. **Candid Window choices** (Scenes 5 and 9): a heroine is accidentally honest, and Brad chooses between exploiting that for answers and respecting her. This is the game's signature ethical choice.

### Clue Bits (`clues`)
| Bit | Scene | Clue |
|---|---|---|
| CL1 | S3 | "Sample 7" reacts with farm soil and glows orange |
| CL2 | S4 | Anonymous note in Brad's jacket: "The soil remembers. Ask your father about the dance." |
| CL3 | S4 | Old photo: Brad's dad, Gord, and a woman (Dr. Eleanor Peters) in front of a banner "Pumpkin Research Program" |
| CL4 | S5 | The glowing pumpkin dessert makes eaters temporarily candid |
| CL5 | S6 | Orange residue is naturally in Patch 7 soil |
| CL6 | S6 | The note's handwriting matches Gord's |
| CL7 | S7 | Archive records: the program was shut down after "the Halloween dance incident" |
| CL8 | S8 | The bulk pumpkin buyer is linked to the college lab |

### Ending Matrix (decided at the S9 climax, shown in the S10 epilogue)
Every route climax in S9 offers three kinds of answer: **confess**, **stay friends**, or **"not yet, I need to figure out what I want first"**. The last one leads to the solo Farm ending.

| Ending | Condition |
|---|---|
| **True Love** | Confess, locked route `aff` >= 20, and at least 6 clue bits |
| **Sweet** | Confess, locked route `aff` >= 14 |
| **Good Friends** | Picks "stay friends", or confesses with `aff` 8-13 (she gently says "let's keep it friends") |
| **Farm (Solo)** | Picks "not yet", or `aff` < 8 at the climax (she says Brad isn't there yet) |

That is 4 routes x 3 endings plus one shared Farm ending (13 total). The cost is kept low by sharing the S9 Act D close and the S10 truth scene across all routes, and swapping only the final ~1.5-minute vignette in S10. The Farm ending is a single shared vignette with a one-line cameo from the locked heroine.

---

## 3. Mystery Bible (for consistency)

- **Twenty-five years ago:** Ravenwood ran the **Pumpkin Research Program** under **Dr. Eleanor Peters** (Patricia's mother). Brad's dad and Gord were star students. They discovered a compound ("the residue") that makes pumpkins grow huge and glow and, in people, causes brief **candid honesty** (a mild truth-serum side effect).
- **The Halloween dance incident:** At the Halloween dance the punch was made with the compound. The whole student body blurted out secrets, confessions, and grudges at once. Chaos, broken friendships, an actual brawl over a casserole. The program was shut down and sealed. (It also made Brad's father finally tell Brad's mother how he felt. Brad exists because of it.)
- **Gord** kept some of the old seeds. He plants them in **Patch 7**, the glowing patch. He promised Brad's dad never to tell Brad. He tries to nudge Brad using the note instead, because he's bad at talking.
- **The bloom:** Patch 7 only blooms when a full moon falls on Halloween. That happened 25 years ago and happens again this year. Brad's dad (Daniel Bart) knew, and quietly arranged for Brad to live on the farm so someone he trusted would be nearby. He didn't tell Brad because he wanted him to enjoy college. This is revealed in the S10 epilogue.
- **Patricia** inherited the lab and the sealed "Sample 7" and is determined to prevent a repeat. At Halloween the full moon makes the pumpkins "bloom" and release the compound. She secretly buys glowing pumpkins in bulk, in a bad disguise ("Mr. Gourd": trench coat, mustache), to neutralize them.
- **Sandra's** family tavern has the old photos and the gossip memory. **Georgia** unknowingly uses Patch 7 pumpkins in her desserts. **Jane** knows the soil and her father's secrecy.
- **Crow:** The crow that steals Brad's name tag (S2) returns it at the dance (S9). Running gag: Patricia blames "ravens" for everything, and in the end one of them is actually involved.

---

## 4. Maps Needed

| ID | Map | Scenes |
|---|---|---|
| M01 | Town Square (also market variant, parade variant) | 1, 4, 8 |
| M02 | Main Street (exteriors: Grove Cafe, Log and Stump Tavern, college gate) | 1, 4, 5, 8 |
| M03 | Farm Road | 1 |
| M04 | McVine Farm: yard, barn, fields, Patch 7, shed | 1, 6, 9 |
| M05 | Farmhouse interior + attic (Brad's room) | 1, 6 |
| M06 | Campus Quad (with bonfire variant) | 2, 3, 4, 7, 9 |
| M07 | Lecture hall / classroom | 2 |
| M08 | Science lab (+ loading dock) | 3, 8 |
| M09 | Student centre | 2, 7 |
| M10 | Library, stacks, and locked archive | 7 |
| M11 | Grove Cafe interior | 5 |
| M12 | Tavern interior | 4, 5 |
| M13 | Football field / bleachers | 4 |
| M14 | Great Hall (dance floor) | 9 |

---

## 5. Scene Plans

### S01: Moving to McVine Farm
**When/Where:** Late August, afternoon to night. M01 Town Square, M02 Main Street, M03 Farm Road, M04 Farm, M05 Farmhouse.
**Goal:** Introduce the town, the controls, and the cast. Establish the tone: warm, goofy, with a hint that something is off with the pumpkins.

**Act A: Shared opening (map tutorial)**
- Bus drops Brad at Town Square with too many suitcases. Gord's text: he is "dealing with a pumpkin situation" and can't pick him up.
- Walk-through: move, interact, and the objective marker pointing to the farm at the edge of town.

**Act B: Shared middle (town walk)**
- The main street has three optional stops: Grove Cafe, Log and Stump Tavern, college gate. Brad can only make **two** before dusk (a visible day clock). Missed meetings are caught up in S2 with alternate lines.
- A crow follows Brad along the road (introduces the crow).

**Act C: Route beats** (stops 1-2 as above; Jane is always met at the farm)
- **G (Grove Cafe):** Georgia waves him in, learns his name in 30 seconds, and presses a free pumpkin-spice cookie on him. *Choice:* take the cookie (+1 G, it is delicious and faintly warm) or decline politely (+0). Light gag about "the secret ingredient."
- **S (Tavern):** Sandra sweeps the porch with a face like a thundercloud and one-word answers to his directions question. *Choice:* earnest, joke, or flee. A dry-humor joke (+2 S), earnest (+1 S), flee (+0).
- **P (College gate):** Patricia is locked out by her own security badge and is arguing with the gate. *Choice:* help her tap the badge correctly (+1 P) or call for security (+0, and she's mortified). She calls him "Mr. Bart" and goes slightly pale.
- **J (Farm, always):** Jane watches Brad lose a fight with a wheelbarrow. *Choice:* accept her help (+1 J) or insist on doing it himself (Gord approves: `trust_gord` +1, but +0 J). She teases him about the "city boy" boots.

**Act D: Shared close**
- Gord's dinner: huge, mostly pumpkin. Gord says the pumpkins "have been acting strange this year" in the deadpan voice of a man who has said this before. *Choice:* ask what he means (flag `F_ASKED_GORD`, `trust_gord` +1) or laugh it off.
- Night. Brad's attic room, the crow on the window, and a faint orange glow from the far field. **CG-01:** attic window view, farm at dusk with a glow in Patch 7.
- **Exit state:** two stop-heroines met, `aff` set by choices (max +3 per route), `F_ASKED_GORD`.

---

### S02: Orientation
**When/Where:** First Monday of term. M06 Quad, M07 Lecture hall, M09 Student centre, M10 Library.
**Goal:** Meet whoever Brad missed, get the lay of the campus, and set up Patricia and the lab.

**Act A: Shared opening**
- Jane (assigned by Gord as Brad's "orientation buddy") meets him at the gate with a coffee and a map she's already marked up. Walk to the quad together.

**Act B: Shared middle (Orientation Bingo)**
- Free-roam bingo card on the quad: five stations (Student Centre, Library, Lecture Hall, Quad fountain, Bookstore). Each station plays a short flavor scene. Visiting two key stations triggers the route beats below. Whoever he missed in S1 appears with a "we haven't met" intro line.

**Act C: Route beats**
- **J (official buddy):** Jane has done the tour three times and heckles the tour guide gently. She knows shortcuts nobody else does. *Choice:* ditch the tour for her shortcut (+2 J, misses a bingo square) or stay (+1 J, full bingo).
- **S (Library):** Sandra is hiding between the stacks from the icebreaker game. Brad finds her; she tests him with deadpan trivia. *Choice:* keep her hiding spot secret (+2 S) or tell the icebreaker leader (+0 S, but the leader gives a comedic reward).
- **G (Student centre coffee cart):** Georgia is covering a sick coworker at the welcome cart. Brad ends up helping with orders. *Choice:* give honest feedback on her experimental muffin (+2 G, it's weird but nice) or tell a kind lie (+1 G, she sees through it).
- **P (Lecture hall):** Brad arrives early and finds Patricia fighting the projector. She pauses at "Bart" again and asks if he's "any relation to Daniel Bart" (dad). *Choice:* answer honestly that he's Daniel's son (+1 P) or stay vague (+0 P, `F_VAGUE_ABOUT_DAD`).

**Act D: Shared close (the speech)**
- Patricia's welcome speech. The projector catches fire. Brad grabs the extinguisher (everyone sees). Patricia: "A raven did it." The crow is on the windowsill. The crow steals Brad's name tag and flies away.
- **CG-02:** lecture hall, Brad holding an extinguisher in a cloud of foam, Patricia peering over her glasses, the crow with the name tag in the window.
- Patricia assigns Brad "lab assistant duty" for next week (for the extinguisher heroics; she says it's a reward). Sets up S3.
- **Exit state:** all four heroines met, `aff` updated (max +3 per route), `F_VAGUE_ABOUT_DAD` possible.

---

### S03: Lab Accident
**When/Where:** Wednesday, week two. M08 Lab, M06 Quad.
**Goal:** The first real mystery beat, the only scene with all four heroines in the same room, and route lock-in.

**Act A: Shared opening**
- Intro Biology lab. Jane is the lab TA, Sandra is Brad's lab partner, Georgia is at the next bench. Patricia explains today's demo with "Sample 7," a sealed jar from "the old archive," which she insists is just decorative gourd extract.
- Comedy: Patricia vs the lab computer.

**Act B: Shared middle (the accident)**
- Brad's boots still carry farm soil from the weekend chores. A few crumbs fall into the dish. The sample turns bright orange and foams over the bench, glowing, and floods the floor. Alarms. Patricia tries to blame ravens. A raven is not present. Everyone laughs, nervously.
- *Choice:* confess it might have been his boots (`F_CONFESSED_LAB`, +trust with Patricia, CL1 set early and Patricia now learns about the farm soil) or stay quiet (CL1 still set because of the foam, but Patricia doesn't hear about the soil until S6).
- **CG-03:** the lab drowned in glowing orange foam, four silhouettes.

**Act C: Route beats (cleanup focus; pick who to stay with)**
- **P:** After hours, Brad and Patricia clean the lab in the glow. She lets slip that Sample 7 "was supposed to be inert." She makes him promise not to tell anyone. *Choice:* promise (+2 P) or say he can't promise (+1 P, respects honesty).
- **J:** The TA hush-up. Jane quietly scrapes some foam into a jar and says the farm soil sometimes glows too. "Dad says it's the moon." *Choice:* tell her about the odd glow in Patch 7 (+2 J, shares a secret) or keep it to himself (+0 J).
- **S:** Sandra photographed everything. She notes that the tavern has a framed photo of "the Great Foam Incident," 25 years ago. *Choice:* ask to see it (+2 S, sets up S4 photo) or tell her to delete the photos (+0 S, she refuses with a smirk).
- **G:** Georgia has foam in her hair and says it smells exactly like pumpkin spice. She wants to bottle it. Brad can stop her (+1 G, "a responsible choice") or let her keep a swab (+2 G, sets up S5's dessert; `F_GEORGIA_SAMPLE`).

**Act D: Shared close, route lock-in**
- Walking out under the quad lights, Brad decides who to ask to Homecoming. *Choice:* invite J, S, G, or P (see the acceptance rule in section 2). If Patricia is asked and accepts, her response is a flustered "That would be a conflict of interest. I'm chaperoning. Walk me to the bonfire, and it is not a date." (Boundary pattern: Patricia's route stays respectful throughout.)
- **Exit state:** `route` set. `clues`: CL1. `F_CONFESSED_LAB` and `F_GEORGIA_SAMPLE` possible.

---

### S04: Homecoming
**When/Where:** First Saturday of October. M01 Parade, M13 Football field, M06 Quad bonfire, M12 Tavern.
**Goal:** Locked route's first date. Family history comes into play. First clue about Brad's father.

**Act A: Shared opening**
- Parade: Gord drives the pumpkin float on the McVine tractor. Brad is draped in school colors and handed a flag. The raven mascot is a nervous freshman.
- Alumni from Brad's dad's class stop to greet him and tell contradictory stories about his father (star quarterback, mascot, never attended a game). Comedy set-piece. *Choice:* believe the quarterback story (+0 anything), ask who's right (sets `F_ASKS_ABOUT_DAD`, which makes later reveals land harder).

**Act B: Shared middle**
- The football game: Brad is dragged into a halftime pumpkin toss contest. The raven mascot loses its head. Slapstick.

**Act C: Route beats (the date)**
- **J:** Brad rides the pumpkin float; Jane lets him steer the tractor ("just keep it straight"). Parade chaos, but they win Best Float. At the bonfire she's quiet. She worries that the farm won't survive and she doesn't know if she wants to take over. *Choice:* encourage her to follow her own wishes (+2 J), tell her she'll do great whichever way (+1 J), or joke (+0).
- **S:** She boycotts Homecoming and sits in the tavern; Brad joins her. She shows him the framed photo (CL3): three young people in front of "Pumpkin Research Program," Brad's dad, Gord, and a woman. She's silent about what she knows. They watch the bonfire from the tavern roof. *Choice:* press her for what she's heard (+0, she shuts down) or stay quiet with her (+2 S, she talks).
- **G:** Brad runs the Grove Cafe booth in the raven mascot costume. Georgia can't stop laughing. At the bonfire she asks Brad to stay with her while she's off shift. *Choice:* take off the costume head for a serious moment (+2 G) or stay in costume and be funny (+1 G, it's endearing but she wanted a real talk).
- **P:** She is a chaperone and sticks to duty. At the alumni reception she gets a pointed question about her mother and the old program and deflects. Later she warns Brad: "Be careful which stories you chase." *Choice:* ask what she means (+1 P) or respect her duty and drop it (+2 P, she notices the restraint).

**Act D: Shared close**
- At the bonfire, Brad finds a note in his jacket pocket in block capitals (CL2): *THE SOIL REMEMBERS. ASK YOUR FATHER ABOUT THE DANCE.* with a small pumpkin doodle.
- **CG-04 (route variant, 4 images):** a bonfire moment with the locked route. Lowest priority for first art pass; fall back to a shared bonfire CG if needed.
- **Exit state:** CL2, CL3 (if S route, or if Brad asks Sandra/saw the photo in S3), `F_ASKS_ABOUT_DAD`.

---

### S05: Cafe Dessert
**When/Where:** Thursday evening. M02 Main Street, M11 Grove Cafe.
**Goal:** Comedy and romance, plus the **Candid Window**: eating the dessert makes people honest.

**Act A: Shared opening**
- Georgia invites a small group for a "private tasting" of her new dessert, the **Pumpkin Surprise**, after hours. It glows faintly. Everyone agrees not to ask why. The pumpkins came from Gord's farm. If `F_GEORGIA_SAMPLE` is set, she also used a "dash" of the lab foam.

**Act B: Shared middle**
- The first bites: Brad blurts that he's secretly terrified of failing his father's legacy. Everyone is silent, then kind. Georgia hurries to clarify that "it's not the dessert, it's the pumpkins" and trails off. Brad learns that the dessert makes people honest for about 30 minutes (CL4).
- **CG-05:** the group around a glowing dessert, a tart with a candle and everyone mid-confession.

**Act C: Route beats (the date and the Candid Window)**
- **G:** After closing, Georgia is candid about being afraid of being "the cafe girl forever" and wanting to bake in the city. *Choice:* ask her a question she wouldn't answer sober (exploit: +0, she'll be embarrassed later), reassure her (+2 G), or distract her with a joke (+1 G).
- **J:** Jane studies at the cafe table. Candid, she admits she's worried her dad is hiding something about the pumpkins and that she's tired of being the farm's "responsible one." *Choice:* ask exactly what he's hiding (CL4+, Jane trusts less: +0 J) or tell her she doesn't have to carry it alone (+2 J).
- **S:** Georgia bribed Sandra to attend with free black coffee. Sandra tastes the dessert and says, in front of everyone, "I like having you around." Mortified, she crushes the cup. *Choice:* tease her (+0 S), say it back (+2 S), or quietly cover for her by changing the subject (+1 S, she appreciates it).
- **P:** Patricia is grading in a corner booth. She takes one bite out of curiosity, then admits "your father was my mother's best student." *Choice:* ask follow-up questions while she's candid (exploit: +0 P, but gives a bit more information about the program, `F_EXPLOITED_CANDOR`) or change the subject and let her keep her secret (+2 P).
- Note: exploiting candor gains a little information but costs trust later. Respecting candor costs nothing now but is remembered. `F_EXPLOITED_CANDOR` is checked in S7, S9, and the ending.

**Act D: Shared close**
- The candor wears off. Everyone pretends nothing happened. The crow taps on the cafe window.
- **Exit state:** CL4, `F_EXPLOITED_CANDOR` possible.

---

### S06: Pumpkin Farming
**When/Where:** Saturday, mid October. M04 Farm (yard, barn, fields, Patch 7, shed).
**Goal:** The farm side of the mystery. Evidence that the soil is the source. Gord's handwriting.

**Act A: Shared opening**
- Gord teaches Brad the pumpkin trade: planting, hauling, "talking to the pumpkins." He gives them names, such as Doris. Map interactions: water, plant, haul, three mini-tasks in a row, each with a Gord proverb.

**Act B: Shared middle**
- Patch 7 has grown three feet overnight and is humming. Brad finds orange residue in the soil (CL5) and shows it to Gord. Gord shuts down, says "Don't go near Patch 7," and writes a note to leave in the barn.
- Brad sees the handwriting and realizes it matches the note from Homecoming (CL6). Gord admits, "I made a promise to your father." *Choice:* press him now (`trust_gord` -1, more info) or give him time (`trust_gord` +1, he opens up in S9).
- **CG-06:** Patch 7 at golden hour, giant glowing pumpkins and Gord in silhouette.

**Act C: Route beats**
- **J:** Night watch in the field, sitting on hay bales while the patch pulses. They talk about leaving the farm. *Choice:* tell Gord what they saw (+1 J, `trust_gord` +1), investigate alone with Jane at night (+2 J), or promise to keep it secret (+1 J).
- **S:** She delivers tavern kegs and ends up in a feud with a goose. After, she takes a soil sample "for science" and compares it to an old tavern ledger of pumpkin purchases. *Choice:* help her with the goose (+2 S), hand her a shovel (+1 S), or watch (+0 S).
- **G:** She picks up pumpkins for pies. She says the pumpkins are "humming" and names one, "Bartholomew." Georgia confesses she's been using only Patch 7 pumpkins because they taste best. *Choice:* warn her that Patch 7 is strange (+1 G, `F_WARNED_GEORGIA` early) or let it go (+1 G, she won't be warned until S8).
- **P:** She arrives in a trench coat claiming to be "birdwatching." She collects soil. Gord's gruff politeness cracks; they clearly have history. *Choice:* cover for her (+2 P), confront her (+1 P, tension), or tell Gord about the lab accident (if `F_CONFESSED_LAB`, this is better received).

**Act D: Shared close**
- Back at the farmhouse. Gord asks Brad to promise to wait until after Halloween. *Choice:* promise (`trust_gord` +1) or refuse (`trust_gord` +0, flag `F_DEFIED_GORD`).
- **Exit state:** CL5, CL6, `trust_gord` adjusted, `F_WARNED_GEORGIA` possible.

---

### S07: Midterm Library
**When/Where:** Late October, midterm week night. M10 Library, stacks, and locked archive; M09 Student centre.
**Goal:** Find the archive records. Time pressure between studying and investigating.

**Act A: Shared opening**
- Midterm panic: a library full of snacks, flashcards, and one pair of earplugs. The library's famously unreliable quiet hours.

**Act B: Shared middle (study vs investigate)**
- The player has **three time slots** before the library closes. Each slot is either **Study** (one lore quiz question; a correct answer adds 1 to `study_pts`) or **Investigate** (adds 1 to `leads`). Two or more `study_pts` sets `MIDTERM_PASS`; two or more `leads` finds a way into the archive. Three slots cannot satisfy both, so the player must choose (route beats can add a study point). A failed midterm only changes the grade text.
- The archive door is locked. How it opens depends on the route.

**Act C: Route beats**
- **J:** Jane brings thermoses and an all-night study plan. She knows the janitor who keeps the archive key because he buys pumpkins from the farm. *Choice:* study with her (+2 J) or sneak off to the archive (+1 J, she covers for you).
- **S:** She picks the archive lock with a bobby pin, thrilled. *Choice:* go in (+2 S, CL7 earlier) or obey the "No entry" sign (+1 S, she goes in anyway and tells you what she found).
- **G:** Georgia's snack run sabotages everyone's study with delicious, distracting food. She recalls that a very polite "gentleman in a trench coat" ordered unusual pumpkin quantities (sets up S8). *Choice:* eat the snacks and study later (+2 G) or push her to focus (+1 G).
- **P:** Patricia is the proctor and archive keeper. She catches Brad in the archive. If `F_EXPLOITED_CANDOR`, she is cold. If not, she is tense but kind. *Choice:* tell her everything (+2 P, and she opens up about her mother), lie (+0 P, `F_LIED_TO_PATRICIA`), or show her the note (+1 P).

**Act D: Shared close**
- The archive contents (CL7): a binder titled "Pumpkin Research Program," a ledger, photos of Brad's father and Gord, and the final page: **"Program terminated: Halloween dance incident."**
- **CG-07:** Brad in the archive by flashlight, holding the binder, a photo of three young people taped inside.
- **Exit state:** CL7, `MIDTERM_PASS` possible, `F_LIED_TO_PATRICIA` possible.

---

### S08: Pumpkin Sales
**When/Where:** Saturday, market day. M01 Town Square (market), M02 Main Street, M08 Lab loading dock.
**Goal:** Comedy, and a chase leading to the lab. A final choice about warning Georgia.

**Act A: Shared opening**
- Gord's stand at the town market. Brad is the reluctant salesman. Rival vendor "Big Mel" sells pumpkins from a smaller, saner patch. Haggle mini-game: charm, guilt, or bluff. Wins affect the "farm money" flag.

**Act B: Shared middle**
- A tall figure in a trench coat, a mustache, and enormous sunglasses ("Mr. Gourd") buys **40 pumpkins in cash**, all from Patch 7. Nothing gets carved. He loads them into a van with a college parking permit. Brad follows him across town (a map chase: avoid carts, bump into customers).
- Georgia buys 12 pumpkins from Patch 7 for the Halloween dance punch. **Shared choice:** warn her the pumpkins make people honest (`F_WARNED_GEORGIA`) or let her make the punch (she doesn't know). This affects S9's chaos level.
- **CG-08:** the van at the lab loading dock, Mr. Gourd lifting a pumpkin, one shoe too stylish for the disguise.

**Act C: Route beats**
- **J:** She dominates the haggling and teaches Brad. A tense moment: she wonders whether the farm will survive without Patch 7's income. *Choice:* offer to help with a bigger plan (+2 J), joke (+1 J).
- **S:** The tavern's "Pumpkin Ale" stall. She uses her gossip network and tells Brad who the buyer might be: "faculty parking permit, size 7 heels." *Choice:* set a stakeout with her (+2 S, leads to a scene on the dock) or leave it to her (+1 S).
- **G:** Cafe stall. She is doing a test run of the punch recipe. Chaos. If `F_WARNED_GEORGIA`, she tries to adjust the recipe and is thoughtful. *Choice:* help adjust the recipe (+2 G), or insist she stop (+1 G, she's hurt).
- **P:** Patricia is "absent from the market." Brad recognizes her disguise by her heels and follows. He confronts her quietly at the dock (**this reveals "Mr. Gourd" early in the P route only**): she's trying to neutralize the pumpkins before the full moon. *Choice:* offer to help her (+2 P), say he'll tell the others (+0 P), or ask for a deal (+1 P).

**Act D: Shared close**
- CL8 set: the buyer links to the lab. For routes other than P, Brad doesn't learn who. Everyone is anxious about Halloween. The crow watches the loading dock.
- **Exit state:** CL8, `F_WARNED_GEORGIA` decided, farm money flag set.

---

### S09: Halloween Dance
**When/Where:** October 31. M14 Great Hall, M06 Quad, M04 Patch 7 (via a short night walk).
**Goal:** Pay off the mystery and the romance. The comedy at its biggest.

**Act A: Shared opening**
- Costume choice for Brad: Scarecrow, Raven, or Gord (a beard-and-flannel parody). Jane appears in her formal look ([jane-mcvine-formal.png](../art/jane-mcvine-formal.png)). Everyone else wears a costume variant (tracked in the art to-do). Dance floor on the map: Brad can chat with each heroine and with Gord and the crow.
- The crow returns Brad's stolen name tag. Brad takes it.

**Act B: Shared middle (the bloom)**
- The full moon rises. Patch 7 blooms; the pumpkins on the dance floor glow and hum. Georgia's punch contains Patch 7 pumpkins. The entire dance floor goes candid. Absurd, loud, and wonderful: a boy admits he never read the book, the dean admits he's afraid of squirrels, and two rivals declare their love.
- **CG-09:** the Great Hall with a glowing punch bowl and the crowd mid-confession.
- If `F_WARNED_GEORGIA`, the punch was diluted and the honesty is milder and shorter: less chaos, but also less comedy. If not, full chaos.

**Act C: Route climaxes**
Each climax ends with the same three-way answer: **confess**, **stay friends**, or **"not yet"** (Farm ending). The ending is resolved by the matrix in section 2.
- **J:** Brad and Jane leave the dance and walk to the farm. In the candid hush she confesses she loves the farm and wants Brad to stay. *Choice:* confess he feels the same, stay friends, or say "not yet." (The planned fourth "leave town together" option was dropped; choices are capped at three options.)
- **S:** She is in the middle of the chaos, deadpan and mortified, and she tells Brad she thinks about him constantly. The tavern crowd cheers. *Choice:* confess (or retreat with her to the roof for a quieter confession), stay friends, or "not yet."
- **G:** Georgia admits she wants to bake in the city, and she wants Brad to come with her. *Choice:* promise to follow (or ask her to stay and open her own place here), stay friends, or "not yet."
- **P:** In the bloom the crow steals Mr. Gourd's mustache in front of everyone, exposing Patricia in every route (the other routes learn who Mr. Gourd is here). On the balcony she tells Brad the truth about her mother and asks whether he wants to "do the right thing" and stop the bloom. After the final choice she says, "Ask me again in December, after grades are filed." (Her True ending is a promise rather than a kiss.) *Choice:* confess, stay friends, or "not yet."
- **Ending resolution (implemented):** if the locked route's `aff` is below 8 the heroine gently says Brad isn't there yet (Farm). Otherwise the choice runs. "Confess" resolves through `resolve_confess`: `aff` >= 20 and `clue_count` >= 6 gives True Love, `aff` >= 14 gives Sweet, `aff` 8-13 gives Good Friends. "Stay friends" is Good Friends and "Not yet" is Farm.

**Act D: Shared close (the choice, the promise)**
- Gord and Brad speak plainly. Gord admits he wrote the note and made a promise to Brad's father. "I never wanted to lie to you. I wanted to keep you out of it." He doesn't tell the full story; he says, "Your dad should be the one to tell you. He's coming for Thanksgiving."
- **Final shared choice:** **cure the pumpkins** (Patricia's neutralizer, safe but ends the magic) or **let the town be honest for one night** (comic consequence in S10: next year's dance gets a warning poster).
- The dance ends, and the crow rides off on the moonlight. Fade to winter.
- **Exit state:** `ending` byte set; `F_CURED` set or cleared; next: S10 epilogue.

---

### S10: Epilogue, "The Truth About the Dance"
**When/Where:** Thanksgiving weekend, first snow. M04 Farm (snow variant), M05 Farmhouse; end vignette location depends on the ending. **Shorter scene: about 6 minutes** (not 10), since it's a payoff and a goodbye.
**Goal:** The full story of the Great Honesty Dance, Brad's dad finally speaking, and one closing vignette that delivers the ending.

**Act A: Shared opening (map, ~1 min)**
- Snow on the farm. Brad walks from the farmhouse to the yard. Patch 7 is quiet (or still faintly glowing if `F_CURED` is not set). Gord is out front talking to a pumpkin. Brad's dad, Daniel Bart, arrives in a rented car with a suspicious amount of pie.

**Act B: Shared middle (the story, ~2.5 min)**
- At the farmhouse table, Daniel tells the full story of the program and the dance, with Gord interrupting and correcting him. Their two versions contradict each other. This pays off the alumni contradictions from S4: the "football star," "mascot," and "never attended" stories all started as cover stories.
- Flashback **CG-11**: the original Halloween dance 25 years ago. Young Daniel, Gord, and Eleanor under a banner, glowing punch bowl in the foreground, a young woman (Brad's mother) in the crowd.
- Reveal: At the dance Daniel blurted his love for Brad's mother, and she blurted back, "I know, you've been staring at me for a year." The program was shut down. Eleanor took the blame and Gord promised to hide the story to protect her name. The pumpkins only bloom when a full moon falls on Halloween, which happened 25 years ago and again this year. Daniel arranged for Brad to live on the farm so someone he trusted would be close.
- *Choice (reaction to the secret):* be angry (a short, honest argument that ends warmly), be understanding, or joke about it. This affects only the lines in the next minutes, not the ending.
- If Brad let the town be honest at the dance (`F_CURED` not set): the "warning poster" gag. If the pumpkins were cured: Gord quietly saves one seed in his pocket.
- If `F_EXPLOITED_CANDOR` is set: a short, awkward callback from the affected heroine before the vignette.

**Act C: Ending vignette (~1.5 min)**
- **True Love / Sweet (per route):**
  - **J:** First snow on the farm. Jane and Brad build a snow-pumpkin. She tells him she's staying to work on the farm and study agronomy. In True Love she gives him a barn key; in Sweet she says "ask me again after the harvest."
  - **S:** Tavern trivia night. Brad joins Sandra's team and loses spectacularly on the pumpkin round. For the first time, Sandra smiles fully. In True Love she shows the old photo hanging next to a new one of the two of them.
  - **G:** Georgia opens a pop-up at the Grove Cafe with her "Honest Edition" Pumpkin Surprise (no glow). Brad is the first taster. In True Love she gives him a key to the shop; in Sweet she asks him to help her plan the city trip.
  - **P:** December, grades filed. Patricia knocks on the farm door in her trench coat, without the mustache. In True Love she says, "You may ask me again." Brad does. She says yes, wearing safety goggles. In Sweet she says "ask me again in spring."
  - **CG-10a-d:** one ending image per route.
- **Good Friends:** The group photo on the tavern steps (Brad, the locked heroine, and the others), the crow in the corner of the frame. Warm and bittersweet.
- **Farm (Solo):** Brad stays on the farm over the winter. Gord teaches him pumpkin lore. All four heroines stop by for stew at various times, and the locked heroine gets a line. Brad names his first pumpkin. Gord hands him a note in block capitals: *WELCOME HOME.* **CG-12:** Brad and Gord on the porch in the snow, the crow on the railing, a carved pumpkin glowing between them.

**Act D: Credits**
- Short credits crawl over a map pan of Ravenwood in winter. A final stinger: the crow, wearing Brad's name tag.
- **Exit state:** game complete; new game plus (optional) keeps the clue journal.

---

## 6. CG List (target ~25)

| ID | Scene | Shared/Route | Description |
|---|---|---|---|
| CG-01 | S1 | Shared | Attic window, glowing Patch 7 at dusk |
| CG-02 | S2 | Shared | Lecture hall extinguisher chaos, crow with name tag |
| CG-03 | S3 | Shared | Lab flooded with glowing orange foam |
| CG-04a-d | S4 | Route (4) | Bonfire moment with J/S/G/P |
| CG-05 | S5 | Shared | Glowing dessert and the candid confessions |
| CG-06 | S6 | Shared | Patch 7 at golden hour, Gord in silhouette |
| CG-06a-d | S6 | Route (4, optional) | Route-specific farm moment |
| CG-07 | S7 | Shared | Archive by flashlight, photo of three young people |
| CG-08 | S8 | Shared | Van at the loading dock, Mr. Gourd's stylish shoes |
| CG-09 | S9 | Shared | Great Hall, glowing punch, crowd in confession |
| CG-10a-d | S10 | Route (4) | Ending images per route (True Love; Sweet can reuse with a small change) |
| CG-11 | S10 | Shared | Flashback: the original dance 25 years ago, young Daniel, Gord, and Eleanor |
| CG-12 | S10 | Shared | Farm ending: Brad and Gord on the snowy porch, crow on the railing |

Priority for art: shared CGs first (11), then S4 and S10 route CGs (8), then optional extras.

---

## 7. Suggested Data Layout (for Step 2 and the engine)

```text
script/
  scenes/
    s01_arrival.json
    s02_orientation.json
    s03_lab_accident.json
    s04_homecoming.json
    s05_cafe_dessert.json
    s06_pumpkin_farming.json
    s07_midterm_library.json
    s08_pumpkin_sales.json
    s09_halloween_dance.json
    s10_epilogue.json
  common/
    characters.json   (id, name, portrait sheet, expression list)
    maps.json         (id, tile data file, spawn points, triggers)
    cgs.json          (id, image file)
    variables.json    (aff_*, route, clues bits, flags, trust_gord)
  tools/
    validate.py       (script checker and playtime estimate)
```

Each scene file holds named blocks: `A_open`, `B_shared`, `C_route_j|s|g|p`, `D_close`. A route block is only entered when `route` matches (S4-S9) or when the player picks the focus (S1-S3). A compiler step packs these into the `.dat` resource file for the Zeal 8-bit engine.

**Command vocabulary (as implemented in [scenes/s01_arrival.json](scenes/s01_arrival.json)):**
- `say` (who, expr, text; `style: "phone"` for text messages), `show`/`hide`, `walk`, `cg`/`cg_off`
- `map` (id, spawn, time: afternoon/dusk/night), `explore` (objective, optional `clock` that ends the explore after N stops, `triggers` with `at`/`once`/`do`)
- `choice` (id, prompt, up to 3 options each with `do`), `if` (var + `cmp` eq/ne/gte/lt + `n`, or a clue `bit`), `add`/`sub`/`set`/`setbit` (`sub` saturates at 0)
- `pick_max` (options: list of `{var, route}`; sets `route` to the entry with the highest value, first wins ties), used for the S3 lock-in fallback
- `copy` (from, to), copies one variable into another; S9 uses it to put the locked route's affection into `aff` so one shared block can resolve the ending
- `call` (run a block and return), `goto` (jump), `end`, `music`, `sfx`, `fade`, `wait`, `tutorial`

**Validation:** `python script/tools/validate.py` checks every scene against `common/*.json` (speakers, expressions, variables, blocks, maps, CGs, text-box fit of 3 lines x 36 characters, at most 3 choices) and prints a rough playtime estimate. Run it after every script edit.

**Text constraints (initial assumption):** a text box holds up to 3 lines of about 36 characters. Choices have at most 3 options each. All variables fit in a byte.

---

## 8. Decisions and Open Questions

**Decided**
- Patricia's route stays respectful: nothing romantic until grades are filed; her True ending is "ask me again in December."
- "Daniel Bart" (Brad's dad) and Dr. Eleanor Peters (Patricia's mother) are the confirmed names.
- Extra expressions, outfits, and costumes (including Brad's) are tracked in [../art/art-todo.md](../art/art-todo.md).
- A solo **Farm ending** exists (shared vignette) and is reached from the "not yet" answer or low affection at the S9 climax.
- The full story of the dance moves to a separate **S10 epilogue** (about 6 minutes), with the ending vignette inside it.

**Open**
- None right now. Next step: write the full scripts, starting with S01.
