# Anchor tracking — run #1 act 3 and act 4 annotated stills

An annotation's anchor is a point on the photograph and travels with
it; its label is type and is locked; the leader is redrawn between
them. This renders the first and last frame of each hold, finds where
the FEATURE went by matching a patch of the photograph, finds where
the DOT went by its accent colour, and compares.

`would be off if locked` is the control: it is how far the dot would
sit from its feature under the previous behaviour, and it is what
makes a passing number mean something.

| cut | annotation | frames | feature start | feature end | dot end | off | if locked | match |
|---|---|---|---|---|---|---|---|---|
| c089 | dolerite pounder | 177 | 1121.3,683.6 | 1134.0,694.0 | 1133.5,694.7 | **0.86px** | 16.41px | 0.985 |
| c089 | worked face | 177 | 576.0,356.4 | 545.0,341.0 | 544.6,341.3 | **0.46px** | 34.61px | 0.906 |
| c177 | contact line | 194 | 902.4,540.0 | 897.0,540.0 | 897.3,539.6 | **0.53px** | 5.4px | 0.982 |
| c177 | no mortar | 194 | 1536.0,324.0 | 1582.0,307.0 | 1581.1,305.7 | **1.57px** | 49.04px | 0.958 |

## And the labels did not move

| cut | words read | scenes with a word in a different place | worst |
|---|---|---|---|
| c089 | 18 | 0 | 0.629px |
| c177 | 8 | 0 | 0.527px |

Frames and clips: `remotion-composer/out/anchors`
