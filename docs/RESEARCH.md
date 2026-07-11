# How quality Second Life avatars are built — research synthesis

Compiled from the SL Wiki, viewer source code (github.com/secondlife/viewer),
Avastar/Machinimatrix documentation, creator-forum engineering threads, and
Firestorm developer Beq Janus's technical analyses. This drives every design
decision in this repository's pipeline.

## 1. Platform fundamentals

- **Skeleton**: `avatar_skeleton.xml` v2.0 — **133 bones + 26 collision
  volumes = 159 riggable joints** ("Bento" since 2016). 26 classic bones,
  plus 4 spine, 46 face, 30 finger, 11 wing, 6 tail, 9 hind-limb, 1 groin.
  Rest pose is a T-pose, X forward, Y left, Z up, meters; all bone rest
  rotations are zero (translation-only joint matrices); collision volumes
  carry non-zero rest rotation/scale that must be baked into bind matrices.
- **Skinning**: linear blend skinning only, **max 4 weights per vertex**
  (viewer normalizes them), no dual quaternion, no blendshapes on uploaded
  mesh, no corrective joints. All shape adaptation happens through bones.
- **Fitted mesh**: appearance sliders move/scale the 26 collision volumes
  (`volume_morph` entries in avatar_lad.xml). The fraction of a vertex's
  weight on a volume bone (vs. its paired mBone) is the fraction of slider
  response. Pairs: mPelvis→PELVIS/BUTT, mTorso→BELLY/HANDLES/LOWER_BACK,
  mChest→CHEST/PECS/UPPER_BACK, limbs→L_/R_ UPPER/LOWER ARM/LEG etc.
  Redistribution within a pair leaves animation unchanged — that is why
  fitting is safe to layer on top of proven weights.
- **Sliders on the head**: avatar_lad.xml has bone-driven params (ids
  30000+) that scale/offset **face bones**, so a mesh head weighted to the
  standard face bones responds to most head sliders automatically.

## 2. Upload rules (hard limits)

| Rule | Value | Source |
|---|---|---|
| Format | COLLADA 1.4.0/1.4.1 (`lldaeloader.cpp`) | viewer source |
| Axis/units | Z_UP, meters | viewer source |
| Materials per mesh | 8 (`MAX_MODEL_FACES`) | llmodel.h |
| Triangles per material | 21,844 (16-bit index buffer / 3) | wiki Limits |
| Vertices per mesh | 65,534 | wiki Limits |
| Joints per mesh | **110** (`LL_MAX_JOINTS_PER_MESH_OBJECT`) | lljoint.h |
| Weights per vertex | 4, normalized | lldaeloader.cpp |
| DAE file size | 8 MB | wiki Limits |
| Textures | ≤2048×2048 (2K grid-wide since 2024), power of two | LL 2024 FAQ |

- Joint names must match the skeleton exactly (`m*` names, volumes like
  `BELLY`); unknown names silently drop the rig.
- Full skeleton hierarchy in the DAE is NOT required — only used joints.
- Inverse bind matrices are honored as the actual bind pose (Bento-era).
- Negative scale, non-ASCII names, `&`/`<` in names, loose vertices, and
  unweighted vertices are the classic causes of "dae parsing issue" /
  mangled uploads.
- LOD files match nodes **by name**: `<label>_LOD2/_LOD1/_LOD0/_PHYS`;
  material lists must be subsets of the high LOD. Physics for worn
  attachments is never simulated but must exist — a trivial shape named
  `default_physics_shape` is the standard trick.
- "Include skin weights" ON, "include joint positions" OFF for anything
  meant to coexist with sliders and other attachments (offsets disable
  slider translation per joint, fight other attachments, and persist until
  Reset Skeleton).
- **Blender exporter**: only the "SL + OpenSim" presets work —
  `open_sim=True` is the critical bone-orientation flag. Collada was
  marked legacy in Blender 4.2 and removed in 5.0: pin Blender 3.6/4.5 LTS.
  (SL's glTF rigged-mesh upload went live in 2025 beta but per-LOD control
  and joint overrides were still maturing — Collada remains the proven path.)

## 3. Texturing / Bakes on Mesh

- Classic **SLUV layout**: three 0–1 UV regions (head, upper incl. hands,
  lower incl. feet) + eyes + skirt + hair. Seams at neck, wrists, waist,
  ankles — boundary rows of the three textures must match exactly.
- **Bakes on Mesh** (2019, 2K since Feb 2025): the server composites all
  worn system layers (skin/tattoo/universal/clothing, alpha punches holes)
  per channel; a mesh face opts in by using the magic bake UUID as its
  diffuse texture. Key channels:
  - `BAKED_HEAD  5a9f4a74-30f2-821c-b88d-70499d3e7183`
  - `BAKED_UPPER ae2de45c-d252-50b8-5c6e-19f39ce79317`
  - `BAKED_LOWER 24daea5f-0539-cfcf-047f-fbc40b2786ba`
  - `BAKED_EYES  52cc6bb6-2ee5-e632-d3ad-50197b1dcb8a`
  - (also HAIR, SKIRT, LEFTARM, LEFTLEG, AUX1-3)
- BoM is why modern bodies dropped onion layers: one mesh shell, one
  composited texture per channel, system alpha wearables replace alpha-cut
  HUDs. Slink Redux (~15k tris, BoM-native) is the optimization reference;
  Legacy's 794k tris / 1,471 texture faces is the cautionary tale — ARC
  rewards segmentation but real render cost is drawcalls.
- Bake channels are **diffuse-only**: form shading (AO, musculature) must
  be baked into the skin diffuse. Normal/specular go on the mesh faces as
  regular materials if desired.
- Alpha **masking** sorts like opaque geometry; alpha **blending** causes
  the classic sorting glitches — mask wherever edges can be hard.
- Uploads are converted to lossy JPEG2000 — paint detail slightly bolder
  than target; never upload JPEG sources.

## 4. Product engineering of top avatars

- A "body" is a linkset attachment + HUD (alpha, skins, nails, hand poses)
  + BoM alpha wearables + shape. Heads ship separately (LeLutka etc.).
- Quality deformation = weight-paint craft: smooth gradients across 2–3
  edge loops at elbows/knees/shoulders, volume-bone shares in fleshy zones
  (belly/butt/pecs get physics), slider stability tested at extremes.
- **Clothing fits exactly one body** because garments are sculpted against
  that body's rest surface and inherit its exact weight maps (dev-kit
  workflow: append kit body → model garment over it → transfer weights →
  export). This pipeline uses the same trick programmatically: garments
  are cut from the body mesh itself, so fit and weights are identical by
  construction.
- Hair: card/shell technique over a scalp base, alpha-masked strand
  textures, rigged to HEAD/NECK (+ spare Bento bones for sway); 3–10k
  complexity is the "well-made" bracket.
- Height: the shape **Height slider spans roughly 1.1–2.4 m** — a 2.3 m
  Ganondorf is reachable WITHOUT joint offsets, keeping full slider
  compatibility (the approach chosen here).

## 5. Decisions taken in this pipeline

1. **Foundation = official assets**: skeleton from `avatar_skeleton.xml`
   (positions from `pos`, per viewer `llavatarappearance.cpp`), body
   geometry/UVs/weights/morphs parsed from the viewer's `.llm` binaries.
   This guarantees SLUV compatibility (any BoM skin will fit) and
   viewer-exact classic weights as the rigging base.
2. **Classic weight decode** reproduces the viewer's render-joint arrays;
   the per-mesh array-length ambiguity is resolved against
   `max(int(weight))` and verified with anatomical landmarks and bilateral
   symmetry histograms.
3. **Single-layer BoM body** (Slink-Redux architecture): 3 bake-channel
   materials (+arms overflow slot pointing at the same channel), eyes,
   lashes; no onion layers; alpha via system alpha wearables.
4. **Fitted mesh**: 50 % uniform mBone→volume split + extra share in
   belly/butt/pec/handle zones (physics-responsive), capped at 4 weights.
5. **Bento fingers and face** weighted procedurally (nearest-chain
   parameterization for fingers; capped proximity fields for the face) so
   hand pose HUDs, face animations and head sliders all work.
6. **Garments are shells of the body mesh** — identical fit, weights and
   SLUV texture coordinates (trim bands are painted along the exact
   island boundaries).
7. **No joint offsets**; Ganondorf height comes from a shape recipe.
8. **Custom LOD chains** exported with the `_LODn` naming convention plus
   a `default_physics_shape` physics file.
