# Ganondorf Avatar — Quickstart

Follow in order. Every step is mechanical; no judgment calls.

## 0. One-time account setup (5 min, once ever)

1. Log in at secondlife.com → Account → **Mesh Upload Status** and accept
   the IP terms (a short quiz). Without this the Upload Model button stays
   greyed out.
2. Have about **L$600** on the account (textures L$10 each, meshes ~L$11-40
   each).

## 1. Viewer (once)

Install **Firestorm** (firestorm-viewer.org). It auto-fills the LOD slots
from the `_LOD2/_LOD1/_LOD0` file names in each item folder, which is why
this kit takes minutes instead of hours.

## 2. Upload all textures in one action

`Avatar menu → Upload → Bulk (L$10 per file)...` → select **every** file in
`01_Textures/` → OK. That's all 19 textures, one action. They appear in
Inventory → Textures.

## 3. Upload the 13 meshes (~30 seconds each)

For each folder `02_Body` … `14_Sword`, in order:

1. `Avatar menu → Upload → Model...` → pick the main file (the one
   **without** `_LOD` in its name, e.g. `ganondorf_body.dae`).
2. The Medium/Low/Lowest LOD slots fill themselves from the sibling files.
   (If they show "Use LoD above" instead, choose *Load from file* and pick
   the matching `_LOD2/_LOD1/_LOD0` file — the names line up.)
3. **Physics tab**: choose **Lowest LOD** from the dropdown. Do not press
   Analyze.
4. **Upload options tab**: tick **Include skin weights**. Leave **Include
   joint positions UNCHECKED** (this matters).
5. Calculate weights & fee → Upload. Name it after the folder.

The sword (14) is the only unrigged item — same steps, skin weights
irrelevant for it.

## 4. Assemble your avatar (in-world, ~15 min)

1. **Skin**: Inventory → right-click → New Clothes → **New Skin** → edit it,
   set Head/Upper/Lower to `skin_head` / `skin_upper` / `skin_lower`. Wear it.
2. **Shape**: New Body Parts → **New Shape** → edit → set sliders:
   Height 90-100, Body Thickness 60-70, Torso Muscles 75+, Leg Muscles 70,
   Shoulders 80+, Hand Size 60, Head Size 45-50, Neck Thickness 70. Wear it.
   (Face detail is modeled into the mesh; sliders fine-tune.)
3. **Wear the meshes**: select all 13 uploaded items in Inventory →
   right-click → **Add** (never "Wear" — Wear replaces, Add stacks).
4. **Texture the faces**: right-click each worn item → Edit → tick
   **Select Face** → click a face → Textures tab → apply per the tables
   below. Gold faces: raise Shininess. This is the longest step; the tables
   make it mechanical.
5. **Hide the system body**: New Clothes → **New Alpha** → tick all body
   regions → wear it. (If you used the BAKED_* options on the body faces,
   the system body hides itself and shows your skin through the mesh —
   either route works; the alpha is the simpler one.)
6. Right-click the sword while worn → Edit → drag it flush to the left hip.
7. **Save the outfit**: Appearance → gear icon → *Save As* → "Ganondorf".
   One click re-wears everything from now on.

**Body** — attach to *Avatar Center*

| Select Face | Apply texture |
|---|---|
| lashes prim | `lashes  (Alpha mode: Alpha blending)` |
| each eye prim | `eyes  (or Bake tab: BAKED_EYES)` |
| body face 0 (head) | `skin_head  (or Bake tab: BAKED_HEAD)` |
| body face 1 (torso) | `skin_upper  (or BAKED_UPPER)` |
| body face 2 (legs) | `skin_lower  (or BAKED_LOWER)` |
| body face 3 (arms/hands) | `skin_upper  (or BAKED_UPPER)` |

**Hair** — attach to *Skull*

| Select Face | Apply texture |
|---|---|
| face 0 (mane) | `hair  (Alpha masking, cutoff 64, if glitchy)` |
| face 1 (gold tie) | `gold` |

**Circlet** — attach to *Skull*

| Select Face | Apply texture |
|---|---|
| face 0 (band) | `gold` |
| face 1 (jewel) | `gem  (Glow 0.05)` |

**Earrings** — attach to *Skull*

| Select Face | Apply texture |
|---|---|
| face 0 | `gold` |

**Necklace** — attach to *Chest*

| Select Face | Apply texture |
|---|---|
| face 0 (collar+plates) | `gold` |
| face 1 (gem) | `gem  (Glow 0.05)` |

**Robe** — attach to *Spine*

| Select Face | Apply texture |
|---|---|
| face 0 (upper) | `robe_upper  (+ robe_normal in Bumpiness)` |
| face 1 (skirt) | `robe_lower  (+ robe_normal in Bumpiness)` |

**Sash** — attach to *Pelvis*

| Select Face | Apply texture |
|---|---|
| face 0 | `sash  (+ sash_normal in Bumpiness)` |

**Pants** — attach to *Pelvis*

| Select Face | Apply texture |
|---|---|
| face 0 | `pants  (+ pants_normal in Bumpiness)` |

**Bracer Left** — attach to *L Forearm*

| Select Face | Apply texture |
|---|---|
| face 0 | `bracer` |

**Bracer Right** — attach to *R Forearm*

| Select Face | Apply texture |
|---|---|
| face 0 | `bracer` |

**Anklet Left** — attach to *L Lower Leg*

| Select Face | Apply texture |
|---|---|
| face 0 | `legwrap` |

**Anklet Right** — attach to *R Lower Leg*

| Select Face | Apply texture |
|---|---|
| face 0 | `legwrap` |

**Sword** — attach to *Left Hip (unrigged: position after attach)*

| Select Face | Apply texture |
|---|---|
| face 0 (scabbard) | `sheath` |
| face 1 (grip+guard) | `sword_gold` |
| face 2 (pommel) | `gem` |


## Troubleshooting (one line each)

| Symptom | Fix |
|---|---|
| Upload Model greyed out | step 0.1 not done (Mesh Upload Status) |
| "Missing required level of detail" | you renamed files — use them unedited |
| Mesh doesn't move with body | "Include skin weights" wasn't ticked |
| Body distorts on other avatars' load | "joint positions" was ticked — reupload without |
| Two bodies visible / skin doubled | wear the alpha (step 4.5) |
| Hair/lashes look glassy or flicker | switch that face to Alpha masking, cutoff ~64 |
| Neck seam line | use the provided 3 skins together; don't mix with other skins |

Total cost: ~L$400-600. Total time: ~45 min, most of it step 4.4.
