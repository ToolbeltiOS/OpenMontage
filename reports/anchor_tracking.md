# Anchor tracking — run #1 act 3 and act 4 annotated stills

An annotation's anchor is a point on the photograph and travels with
it; its label is type and is locked; the leader is redrawn between
them. This renders the first and last frame of each hold, finds where
the FEATURE went by matching a patch of the photograph, finds where
the DOT went by rendering the frame with and without the annotation
and taking the difference, and compares the two.

`would be off if locked` is the control: it is how far the dot would
sit from its feature under the previous behaviour, and it is what
makes a passing number mean something.

| cut | annotation | frames | feature start | feature end | dot end | off | if locked | match | by |
|---|---|---|---|---|---|---|---|---|---|
| c089 | dolerite pounder | 177 | 1121.3,683.6 | 1133.9,695.6 | 1133.7,694.6 | **0.97px** | 17.38px | 0.99 | ecc-affine |
| c089 | worked face | 177 | 576.0,356.4 | 545.3,341.3 | 544.6,341.3 | **0.71px** | 34.18px | 0.913 | ecc-affine |
| c177 | contact line | 194 | 902.4,540.0 | 897.4,540.0 | 897.3,539.6 | **0.44px** | 5.0px | 0.988 | ecc-affine |
| c177 | no mortar | 194 | 1536.0,324.0 | 1582.1,306.8 | 1581.5,306.3 | **0.75px** | 49.24px | 0.984 | ecc-affine |

## And the labels did not move

| cut | words read | scenes with a word in a different place | worst |
|---|---|---|---|
| c089 | 0 | 0 | 0.0px |
| c177 | 0 | 0 | 0.0px |

Frames and clips: `remotion-composer/out/anchors`
