# Weapon grip sizing reference

Use **cougar-approved-grip-v1** as the default hand-contact sizing reference for
future weapons. The user approved the latest Cougar's grip size on 2026-10-22.
The portable measurements and source hashes are in
[weapon-grip-standard-v1.json](weapon-grip-standard-v1.json).

Measure the usable grip, then size the weapon from that grip. Do not infer scale
from overall weapon length, blade width, guard, pommel or generated image framing.
Keep the verified native hand origin and attachment axes. Map each new design's
axes to the reference before comparing measurements.

The reference usable length is **0.1831918 native units**. Its central cross-section
is **0.0486066387 wide by 0.0295819642 deep**. The JSON includes five sections along
the usable grip to distinguish its natural taper from a full-part bounding box.
The complete Cougar grip part includes additional hardware and is longer than
the usable hand-contact region; its full bounds are not the length target.

For each future weapon:

1. Record usable grip endpoints and transverse sections in the asset manifest;
   reference `cougar-approved-grip-v1` and its exact JSON hash in the fitting evidence.
2. Fit the usable length and hand placement, then compare the grip's face width
   and depth against this reference. Use the measured dimensions, rather than
   repeating the Cougar's historical 0.8/1/0.64 scale on a different source mesh.
3. Record the resulting fit and actual grip dimensions in the family/fitting
   profile. Apply corresponding transforms to donor, working mesh and shadows.
   Preserve each design's intended blade/barrel/stock proportions and openings.
4. Inspect the actual grip in the native hand on both supported Human bodies
   before acceptance. Intentional sizing departures need explicit review.

This is a sizing reference, not a requirement to copy the Cougar's grip shape.
Two-handed weapons or unusual grip mechanisms still need their own contact and
native contracts. Firearm packaging remains blocked until its multipart contract
is supplied. Grip approval does not establish the full client validation matrix
or authorize production promotion.
