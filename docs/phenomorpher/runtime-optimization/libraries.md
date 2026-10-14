# Runtime optimization: Phase 3 libraries and Human repoint

Offline motion evidence for all eight shared libraries and the Human Large repoint.
No packaged asset or contract changed; this creates no motion, client or production approval.
The pipeline is the Phase 2 one ([pilots.md](pilots.md)).

## Libraries

Fit and Large chains were controller-identical for every race and gender except the
female `2hslashl`, which takes the Fit clip as authorized.

| Library | Supermodel | Retained | Inherited | Bytes | SHA-256 (restored) |
|---|---|---:|---:|---:|---|
| `srn_an_df` | `a_fa` | 168 | 4 | 2,258,216 | `880ebdd3835b758b2cafac706ffd8090e134ff1a0ba7f29aa15c861b633e6336` |
| `srn_an_dm` | `a_ba` | 169 | 3 | 2,175,232 | `0c411fe7420579d051404f4d6f83ca825c56ebb174e1e1981b812c6fe380d036` |
| `srn_an_ef` | `a_fa` | 147 | 25 | 2,094,012 | `ea379429c6f443f621caef7226a98071a76fdb8950ba265a225e0849e33103f6` |
| `srn_an_em` | `a_ba` | 147 | 25 | 2,004,696 | `4389324cf707ec9f8aeca148c4e40f75f5f933055398c770c35db6ecb4c83dba` |
| `srn_an_of` | `a_fa` | 147 | 25 | 2,094,012 | `7ab4d38e12cf5aeee922000b4b4a29dc4cc1aa305af1123f04dfed67c56efaa6` |
| `srn_an_om` | `a_ba` | 147 | 25 | 2,004,696 | `e869c04d6db99ca6feb9c72bc76a8818b88af61195c48033c3e2377d99a3c794` |
| `srn_an_gf` | `a_fa` | 147 | 25 | 2,094,012 | `15e5a9763c32adeeb155ed62f85479b1daf8fa383a8e04c0567e13e8e8e981e9` |
| `srn_an_gm` | `a_ba` | 147 | 25 | 2,004,696 | `4f7652f219ba8be8116549ae6b4f0b2a45ca55f202b185ff05648c7b803c53a4` |

In total, 16,729,572 bytes replace the 147,686,860 bytes of private carriers.

## Motion comparison (all 20 roots)

Every comparison passed. Retained clips are byte-exact; inherited clips have identical
keys to the published clips (0 mm, 0°) and differ only in stock's root name and
simultaneous-event order. The worst assembled drift of an inherited clip is 1.3×10⁻⁷ m
(non-Human) and 7.8×10⁻⁷ m (Human, compile rounding of the ASCII `a_ba_custom` clips).

| Roots | New parent | Result |
|---|---|---|
| Non-Human Fit/Large | their race/gender library | exact + inherited; female Large `2hslashl` authorized |
| `pmh2` | `a_ba` | 166 inherited exact, 6 within tolerance |
| `pfh2` | `srn_fa_h0` (as `pfh0`) | `pause1`/`pause2` exact, 158 inherited exact, 11 within tolerance, `2hslashl` authorized |

Female posture (**hips level + original upper lean/breathing**): `pause1` and `pause2`
are byte-exact to the published clips in all ten female assemblies.

## Unkeyed nodes

In inherited clips about fifty nodes carry no key (stock keys position only on
`rootdummy`). Their bind frames differ between our rigs and stock `a_ba`/`a_fa` by up
to 1.15 m (`headconjure`) and 150–230 mm on limbs. The library geometry equals each
root's frames exactly.

The shipped game already settles which frames the engine uses. Stock `pmd0 > a_da > a_ba`
plays `a_ba` walk and talk clips (`a_da` overrides only 22 combat/sit clips).
`a_da`'s shin frame equals `a_ba`'s, while stock `pmd0`'s differs by 157 mm, and stock dwarves
walk with dwarf shins. An unkeyed node therefore takes the instance (root) frame, not the
immediate supermodel's or the clip owner's. Stock `pme0 > a_ba` (50 mm leg differences)
shows the same. The offline comparison uses that rule.

This is an inference from stock behaviour, not a client run of these libraries; the
client session still has to show inherited clips on these bodies.
