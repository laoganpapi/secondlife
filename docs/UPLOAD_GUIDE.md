# Ganondorf Bento Avatar — Second Life Upload & Assembly Guide

Everything you upload lives in `output/dae` (meshes) and `output/textures`
(images). Use the **Firestorm** or official SL viewer. Total cost estimate:
~L$11–16 per mesh × 11 + L$10 per texture × 14 ≈ **L$260–320**.

## 1. Upload the textures first

`Build → Upload → Image (L$10)` for each file in `output/textures/`:

| File | Used for |
|---|---|
| `skin_head.png`, `skin_upper.png`, `skin_lower.png` | skin (system skin for BoM, or applied directly to the body) |
| `eyes.png` | eye mesh |
| `lashes.png` | eyelashes (alpha) |
| `hair.png`, `gold.png`, `gem.png` | hair cards (alpha-cutout strand atlas), all gold jewelry, gems |
| `loincloth.png` (+`loincloth_normal.png`) | loincloth |
| `bracer.png` | both bracers |
| `legwrap.png` | both anklets/leg wraps |
| `sword_gold.png`, `sheath.png` | sword |

Tip: check "Use lossless compression" only for the small gold/gem textures.

## 2. Create the system skin (recommended: Bakes on Mesh)

1. Inventory → New Clothes → **New Skin**; edit it and set Head/Upper/Lower
   textures to `skin_head` / `skin_upper` / `skin_lower`.
2. Make a **New Shape** — this is your Ganondorf shape. Suggested sliders:
   - Height ~90–100 (≈2.2–2.4 m), Body Thickness 60–70, Torso Muscles 75+,
     Leg Muscles 70, **Leg Length 70–85**, Shoulders 80+, Hand Size 60,
     Head Size 45–50 (small head reads imposing), Neck Thickness 70.
   - Leg Length is the correct way to make the legs read longer: the mesh
     uses standard (non-overridden) Bento joints, so it follows this
     slider's joint offsets exactly. Stretching the mesh geometry itself
     instead would desync the knee crease from the actual knee bone and
     look wrong in any bend/sit animation — deliberately not done here.
   - Face is mostly baked into the mesh; sliders still work — tweak Jaw
     Angle / Chin Depth / Brow to taste.
3. Wear skin + shape (+ any system alpha layers later for clothing).

## 3. Upload the meshes

For **each** item below: `Build → Upload → Model`, then in the dialog:

- **LOD tab**: High = `<item>.dae`. For Medium/Low/Lowest choose
  *Load from file* and pick `<item>_LOD2.dae` / `_LOD1` / `_LOD0`
  (names match automatically), or leave lower LODs on *Use LoD above*
  for maximum quality at higher cost.
- **Physics tab**: *From file* → `ganondorf_physics.dae` (or step 1 lowest).
  Do NOT press Analyze for worn items.
- **Upload options tab**: check **Include skin weights**. Leave
  **Include joint positions UNCHECKED**.
- Name it, Calculate weights & fee, Upload.

Items (all rigged unless noted):

| File | Attach point (suggested) |
|---|---|
| `ganondorf_body.dae` (body+eyes+lashes linkset) | Avatar Center |
| `ganondorf_hair.dae` | Skull |
| `ganondorf_circlet.dae` | Skull |
| `ganondorf_earrings.dae` | Skull |
| `ganondorf_necklace.dae` | Chest |
| `ganondorf_loincloth.dae` | Pelvis |
| `ganondorf_bracer_left/right.dae` | Forearms |
| `ganondorf_anklet_left/right.dae` | Lower legs |
| `ganondorf_sword.dae` (static, unrigged) | **Left Hip**, then position manually |

Rigged attachments ignore attachment-point position — they always follow
the skeleton, so the point choice is bookkeeping only (each point holds
multiple attachments; spread items out).

## 4. Texture the mesh faces (in-world)

Rez or wear each item, `Edit` → *Select Face*:

**Body** — the Bakes-on-Mesh hookup:
- head face → texture picker → **Bake** tab → `BAKED_HEAD`
- both upper-body faces (torso + arms) → `BAKED_UPPER`
- lower face → `BAKED_LOWER`
- eyes → `BAKED_EYES` (or apply `eyes.png` directly)
- lashes → apply `lashes.png`, set Alpha mode **Alpha blending**
- With BoM active, your system skin (step 2) appears on the body, and any
  system tattoo/clothing/alpha layers work like on a classic avatar.

**Everything else** — apply the matching texture per face; gold faces get
`gold.png` (set Shininess high or add a specular map), gems get `gem.png`
with a little Glow (0.05). Loincloth: apply `loincloth_normal.png` in the
Bumpiness slot for leather depth. Hair (the whole mane is one face): apply
`hair.png` and set Alpha mode to **Alpha masking** (cutoff ~50) — this is
required, not optional, since the hair is built from overlapping cards
whose strand definition comes entirely from this texture's alpha cutout;
Alpha blending will show visible sorting artifacts between cards.

## 5. Hiding the body under clothes

The body is BoM, and the loincloth only covers the hips — wear a standard
**alpha wearable** if you want the covered strip hidden under the system
skin too (Inventory → New Clothes → New Alpha). Not required: BoM already
shows your skin correctly everywhere the mesh doesn't cover.

## 6. Animation notes

- Hands: rigged to all 30 Bento finger bones — any Bento hand-pose HUD or
  AO works.
- Face: jaw, lips, brows, lids, cheeks, ears are weighted — Bento facial
  animation HUDs and most head appearance sliders respond.
- Eyes follow your look-at target automatically (rigged to eye bones).
- The mane is graded mHead → mNeck → mChest by height, so the crown
  follows the head and the long back cascade follows head+neck motion
  naturally.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Missing required level of detail" | LOD file node names must end `_LOD2` etc. — use the provided files unedited |
| Mesh uploads but doesn't move with body | "Include skin weights" wasn't checked |
| Body distorts when someone else's shape loads | you checked "joint positions" — reupload without it |
| Neck/waist seam line | ensure head/upper/lower textures are the provided set (seam rows match); use a neck-blender if you swap skins |
| Alpha glitches on hair/lashes | switch that face from Alpha blending to Alpha masking |
| Skin looks flat | SL converts to JPEG2000; the shipped textures are pre-boosted — avoid re-saving as JPEG before upload |
