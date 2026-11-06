# Handoff: Java -> Bedrock 3D item display issues

## Goal
Convert ItemsAdder/Java resource packs (CustomModelData / item_model) to a Bedrock .mcpack + Geyser v2 mappings, so 3D items look the same on Bedrock (via Geyser) as on Java: held in hand, worn on head, furniture on ArmorStand heads, and inventory icons.

## Symptoms reported (Bedrock client, latest build)
- Swords / many 3D items held in hand: wrong position, wrong direction, floating away from the arm.
- Santa hat: sank to chest after the last binding change (was fine before); sometimes rendered like a white leather cap with a red tip.
- Furniture and vehicles larger than on Java and sunk into the ground; wall paintings ~0.5 block away from the wall.
- Wanted: configurable, higher-resolution 2D/3D inventory icons.

## Root causes found
- Old `math_utils.build_display_animation` used per-case hard-coded offsets (+16, +3.25, +11, 1.5...) fitted to a few models; head scale ignored Java's 0.625 head factor.
- Last binding change used `(a || b) ? 'head' : ...` Molang, probably not evaluated as intended.
- Keyword matching in `geyser_mappings.py` used substrings, so `santa_hat` missed `hat/` / `hat_` and lost `equippable: head`.

## Changes in this commit
- Rewrote display transform following Kas-tle/java2bedrock.sh (converter.sh): bones `root_item` -> `_x` -> `_y` -> `_z`; fixed hand poses (3rd person `rot [90,0,0] pos [0,13,-3]`, 1st person `rot [90,60,-40] pos [4,10,4] scale 1.5`); head slot `pos [0,19.9,0]` with translation/scale * 0.625; first-person head disabled.
- Binding: `c.item_slot == 'head' ? 'head' : q.item_slot_to_bone_name(c.item_slot)`; slot vars via `pre_animation` (`v.main_hand`, `v.off_hand`, `v.head`).
- Whole-token keyword matching (`_has_kw`).
- `--icon-size {16..512}` (default 128): 3D icons rendered at that size, square 2D icons NEAREST-upscaled by integer factor.
- Tests: `tests/test_display_transforms.py`; updated phase1/phase2 tests.

## Not verified
- Nothing has been checked in-game after this commit (server was down). Re-test: katana, AK-47, shield (offhand), santa hat, mini fridge, wall painting, vehicles.
- Wall paintings have no special compensation now. `dropbox_bundle.zip` not re-converted.
- Open questions: does Geyser set `c.item_slot` to `main_hand/off_hand/head` as assumed? Is `equippable: head` causing a vanilla leather-helmet render instead of the attachable? Item 2D `display_handheld` still keyword-based (e.g. `energy_capsule` now handheld).

## Reproduce
`python3 cli.py -i <generated.zip> -o output/mins_net -n MinsNetworkPack [--icon-size 128]`, copy `.mcpack` to `Geyser-Spigot/packs/` and `custom_mappings/items_v2.json`, run `geyser reload`.
