# The bank quality floor

`lib/verify_bank_quality.py`, applied in `lib/asset_bank.py` to the
downloaded file — not to the provider's metadata, because focus and
compression are not in an imageinfo record.

Three checks: long edge ≥ 2400 on the file, sharpness, JPEG blocking. The
bank already rejected images under 3000px by metadata and flat frames by
grey standard deviation; these are the ones that need the pixels.

## Sharpness is not the global Laplacian variance

Ranked by global variance, the three softest pictures in the bank are:

| picture | global var | what it actually is |
|---|---|---|
| hand holding a stone | 21.9 | a shallow-DOF macro, sharp on the subject |
| lamplit tunnel | 50.5 | dark, not blurred |
| dim museum interior | 65.3 | dark, not blurred |

**None is out of focus.** A global floor condemns all three — a deliberate
bokeh background and two dark rooms. So the question asked is whether
*anything* in the picture is sharp, which is what matters for a still that
will be magnified: the frame is tiled, Laplacian variance is taken per tile,
and the measure is the 95th percentile of those.

Against the same pictures Gaussian-blurred at sigma 3, which is the control:

| picture | as banked | blurred |
|---|---|---|
| hand and stone | 80.4 | 2.2 |
| tunnel | 131.0 | 5.3 |
| museum interior | 269.4 | 2.9 |
| Tiryns wall | 1279.0 | 2.8 |
| moai row | 3711.3 | 4.7 |
| Sacsayhuamán joint | 5471.8 | 7.2 |

Real 80.4 and up, blurred 7.2 and down. The floor of 25 sits in that gap
with 3.2× clearance below the softest real picture.

Everything is measured at a normalised 1024px long edge, because Laplacian
variance grows with resolution — measured on the file it would rank big
pictures above sharp ones, which is the one thing this check must not do
since the bank is already ordered by resolution.

The tile adapts to the frame. A fixed 128px tile returns **zero** on
`wm_229317340`, a 2068×20064 panorama that normalises to 105px tall: no tile
fits, the variance list comes back empty, and a sharp photograph fails a
sharpness check because of its shape. With an adaptive tile it reads 3837.2.

## Blockiness never fires here, and that is the honest expectation

Across all 325 banked images it runs 0.856 to 1.160, median 1.001. Commons
originals are not recompressed JPEGs, so there is nothing for this check to
find. The threshold therefore comes from a control — the same picture
re-encoded at falling quality:

| JPEG quality | blockiness |
|---|---|
| 95 | 0.989 |
| 50 | 1.501 |
| 20 | 2.063 |
| 10 | 2.987 |
| 5 | 5.207 |

The ceiling of 1.30 catches quality 50 and worse and clears the entire bank.
It exists for the day a provider that is not Commons supplies a recompressed
file.

## Run against the bank as it stands

**0 of 325 rejected.**

| measure | observed | floor |
|---|---|---|
| sharpness | min 80.4, p1 255.8, median 2701.8 | 25.0 |
| blockiness | max 1.160, p99 1.065 | 1.30 |
| long edge | min 3020 | 2400 |

Zero rejections is the expected result and not evidence the gate does
nothing: the corpus was already filtered for size and flatness, and the
blur, panorama and compression controls above each produce a rejection.
