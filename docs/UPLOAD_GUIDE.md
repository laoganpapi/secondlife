# Ganondorf Bento Avatar — Second Life Upload & Assembly Guide

Everything you upload lives in `output/dae` (meshes) and `output/textures`
(images). Use the **Firestorm** or official SL viewer. Total cost estimate:
~L$11–16 per mesh × 14 + L$10 per texture × ~18 ≈ **L$350–450**.

## 1. Upload the textures first

`Build → Upload → Image (L$10)` for each file in `output/textures/`:

| File | Used for |
|---|---|
| `skin_head.png`, `skin_upper.png`, `skin_lower.png` | skin (system skin for BoM, or applied directly to the body) |
| `eyes.png` | eye mesh |
| `lashes.png` | eyelashes (alpha) |
| `hair.png`, `gold.png`, `gem.png` | hair, all gold jewelry, gems |
| `robe_upper.png`, `robe_lower.png` (+`robe_normal.png`) | robe |
| `pants.png` (+`pants_normal.png`) | pants |
| `sash.png` (+`sash_normal.png`) | sash |
| `bracer.png` | both bracers |
| `legwrap.png` | both anklets/leg wraps |
| `sword_gold.png`, `sheath.png` | sword |

Tip: check "Use lossless compression" only for the small gold/gem textures.

## 2. Create the system skin (recommended: Bakes on Mesh)

1. Inventory → New Clothes → **New Skin**; edit it and set Head/Upper/Lower
   textures to `skin_head` / `skin_upper` / `skin_lower`.
2. Make a **New Shape** — this is your Ganondorf shape. Suggested sliders:
   - Height ~90–100 (≈2.2–2.4 m), Body Thickness 60–70, Torso Muscles 75+,
     Leg Muscles 70, Shoulders 80+, Hand Size 60, Head Size 45–50 (small
     head reads imposing), Neck Thickness 70.
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
| `ganondorf_robe.dae` | Spine |
| `ganondorf_sash.dae` | Pelvis |
| `ganondorf_pants.dae` | Pelvis |
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
with a little Glow (0.05). Robe/pants/sash: apply the matching
`*_normal.png` in the Bumpiness slot for fabric depth. Hair: `hair.png`
on hair faces, `gold.png` on the tie; set Alpha mode **Alpha masking**
(cutoff ~64) if you see sorting glitches.

## 5. Hiding the body under clothes

The body is BoM — wear a standard **alpha wearable** that hides what the
robe/pants cover (Inventory → New Clothes → New Alpha; paint or use any
full-body alpha HUD). Because the garments were cut from this exact body
with identical weights, clipping is minimal even without alphas in most
animations.

## 6. Animation notes

- Hands: rigged to all 30 Bento finger bones — any Bento hand-pose HUD or
  AO works.
- Face: jaw, lips, brows, lids, cheeks, ears are weighted — Bento facial
  animation HUDs and most head appearance sliders respond.
- Eyes follow your look-at target automatically (rigged to eye bones).
- The topknot/mane is rigged to the head; sideburn tips carry a little
  neck weight for natural motion.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| "Missing required level of detail" | LOD file node names must end `_LOD2` etc. — use the provided files unedited |
| Mesh uploads but doesn't move with body | "Include skin weights" wasn't checked |
| Body distorts when someone else's shape loads | you checked "joint positions" — reupload without it |
| Neck/waist seam line | ensure head/upper/lower textures are the provided set (seam rows match); use a neck-blender if you swap skins |
| Alpha glitches on hair/lashes | switch that face from Alpha blending to Alpha masking |
| Skin looks flat | SL converts to JPEG2000; the shipped textures are pre-boosted — avoid re-saving as JPEG before upload |
