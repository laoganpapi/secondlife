#!/usr/bin/env python3
"""Build the one-folder Second Life upload kit from validated artifacts.

Copies output/dae + output/textures into output/upload_kit/ arranged as
numbered per-item folders (Firestorm auto-fills LOD slots from the _LODn
file names), writes QUICKSTART.md + CHECKLIST.txt, self-checks the result
and zips it to output/GanondorfAvatar_UploadKit.zip.

Plain Python, no Blender.  Usage:  python3 pipeline/make_upload_kit.py
"""

from __future__ import annotations

import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAE = os.path.join(ROOT, "output", "dae")
TEX = os.path.join(ROOT, "output", "textures")
KIT = os.path.join(ROOT, "output", "upload_kit")
ZIP = os.path.join(ROOT, "output", "GanondorfAvatar_UploadKit.zip")

# folder number, folder name, dae stem, attach point, face->texture rows
ITEMS = [
    ("02", "Body", "ganondorf_body", "Avatar Center", [
        ("lashes prim", "lashes  (Alpha mode: Alpha blending)"),
        ("each eye prim", "eyes  (or Bake tab: BAKED_EYES)"),
        ("body face 0 (head)", "skin_head  (or Bake tab: BAKED_HEAD)"),
        ("body face 1 (torso)", "skin_upper  (or BAKED_UPPER)"),
        ("body face 2 (legs)", "skin_lower  (or BAKED_LOWER)"),
        ("body face 3 (arms/hands)", "skin_upper  (or BAKED_UPPER)"),
    ]),
    ("03", "Hair", "ganondorf_hair", "Skull", [
        ("face 0 (whole mane)", "hair  (Alpha masking, cutoff 64, if glitchy)"),
    ]),
    ("04", "Circlet", "ganondorf_circlet", "Skull", [
        ("face 0 (band)", "gold"),
        ("face 1 (jewel)", "gem  (Glow 0.05)"),
    ]),
    ("05", "Earrings", "ganondorf_earrings", "Skull", [
        ("face 0", "gold"),
    ]),
    ("06", "Necklace", "ganondorf_necklace", "Chest", [
        ("face 0 (collar+plates)", "gold"),
        ("face 1 (gem)", "gem  (Glow 0.05)"),
    ]),
    ("07", "Robe", "ganondorf_robe", "Spine", [
        ("face 0 (upper)", "robe_upper  (+ robe_normal in Bumpiness)"),
        ("face 1 (skirt)", "robe_lower  (+ robe_normal in Bumpiness)"),
    ]),
    ("08", "Sash", "ganondorf_sash", "Pelvis", [
        ("face 0", "sash  (+ sash_normal in Bumpiness)"),
    ]),
    ("09", "Pants", "ganondorf_pants", "Pelvis", [
        ("face 0", "pants  (+ pants_normal in Bumpiness)"),
    ]),
    ("10", "Bracer_Left", "ganondorf_bracer_left", "L Forearm", [
        ("face 0", "bracer"),
    ]),
    ("11", "Bracer_Right", "ganondorf_bracer_right", "R Forearm", [
        ("face 0", "bracer"),
    ]),
    ("12", "Anklet_Left", "ganondorf_anklet_left", "L Lower Leg", [
        ("face 0", "legwrap"),
    ]),
    ("13", "Anklet_Right", "ganondorf_anklet_right", "R Lower Leg", [
        ("face 0", "legwrap"),
    ]),
    ("14", "Sword", "ganondorf_sword", "Left Hip (unrigged: position after attach)", [
        ("face 0 (scabbard)", "sheath"),
        ("face 1 (grip+guard)", "sword_gold"),
        ("face 2 (pommel)", "gem"),
    ]),
]

LODS = ["", "_LOD2", "_LOD1", "_LOD0"]
N_TEXTURES = 19


def quickstart() -> str:
    face_tables = []
    for _, folder, _, attach, faces in ITEMS:
        rows = "\n".join(f"| {f} | `{t}` |" for f, t in faces)
        face_tables.append(
            f"**{folder.replace('_', ' ')}** — attach to *{attach}*\n\n"
            f"| Select Face | Apply texture |\n|---|---|\n{rows}\n"
        )
    tables = "\n".join(face_tables)
    return f"""# Ganondorf Avatar — Quickstart

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

{tables}

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
"""


def checklist() -> str:
    lines = [
        "GANONDORF UPLOAD CHECKLIST",
        "",
        "[ ] Mesh Upload Status enabled on account (IP quiz)",
        "[ ] ~L$600 balance",
        "[ ] Firestorm installed",
        "[ ] Bulk-uploaded 01_Textures (19 files)",
    ]
    for num, folder, _, _, _ in ITEMS:
        lines.append(f"[ ] Uploaded {num}_{folder} (skin weights ON, joint positions OFF)")
    lines += [
        "[ ] New Skin (skin_head/upper/lower) worn",
        "[ ] New Shape (slider recipe) worn",
        "[ ] All 13 items Added",
        "[ ] Faces textured per QUICKSTART tables",
        "[ ] Alpha wearable on (system body hidden)",
        "[ ] Sword positioned",
        "[ ] Outfit saved as 'Ganondorf'",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    problems = []
    if os.path.isdir(KIT):
        shutil.rmtree(KIT)

    read_me = os.path.join(KIT, "00_READ_ME_FIRST")
    os.makedirs(read_me)
    with open(os.path.join(read_me, "QUICKSTART.md"), "w") as f:
        f.write(quickstart())
    with open(os.path.join(read_me, "CHECKLIST.txt"), "w") as f:
        f.write(checklist())

    tex_dst = os.path.join(KIT, "01_Textures")
    os.makedirs(tex_dst)
    textures = sorted(t for t in os.listdir(TEX) if t.endswith(".png"))
    for t in textures:
        shutil.copy2(os.path.join(TEX, t), os.path.join(tex_dst, t))
    if len(textures) != N_TEXTURES:
        problems.append(f"expected {N_TEXTURES} textures, found {len(textures)}")

    for num, folder, stem, _, _ in ITEMS:
        dst = os.path.join(KIT, f"{num}_{folder}")
        os.makedirs(dst)
        for suffix in LODS:
            src = os.path.join(DAE, f"{stem}{suffix}.dae")
            if not os.path.isfile(src):
                problems.append(f"missing {stem}{suffix}.dae")
                continue
            shutil.copy2(src, os.path.join(dst, f"{stem}{suffix}.dae"))
        n = len(os.listdir(dst))
        if n != len(LODS):
            problems.append(f"{num}_{folder}: {n} files, expected {len(LODS)}")

    # ASCII names only (SL uploader requirement)
    for dirpath, _, files in os.walk(KIT):
        for name in files:
            if not name.isascii():
                problems.append(f"non-ASCII name: {name}")

    if problems:
        for p in problems:
            print("KIT ERROR:", p, file=sys.stderr)
        return 1

    if os.path.isfile(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, files in sorted(os.walk(KIT)):
            for name in sorted(files):
                full = os.path.join(dirpath, name)
                z.write(full, os.path.relpath(full, os.path.dirname(KIT)))

    n_files = sum(len(f) for _, _, f in os.walk(KIT))
    print(f"[kit] {len(ITEMS)} items + {len(textures)} textures, "
          f"{n_files} files, zip {os.path.getsize(ZIP) // 1024} KiB")
    print("[kit] self-check OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
