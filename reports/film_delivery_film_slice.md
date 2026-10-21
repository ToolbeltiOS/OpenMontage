# Film delivery — they-said-it-couldnt-be-built — film_slice.mp4

`/private/tmp/claude-501/-Users-mac/8ff191cb-a0fe-4699-b10d-d62595d025e1/scratchpad/fo/film_slice.mp4` · 794 frames · 26.5s · plate `remotion-composer/out/they-said-it-couldnt-be-built/plate.mp4`

## Gates

| check | measured | verdict |
|---|---|---|
| frame motion | 0.0% duplicate pairs, longest freeze 0.0s, timestamps constant | PASS |
| frame order | 0 frames out of place, 0 isolated black, correlation with the plate 0.999 | PASS |
| plate purity | 0 words legible in the plate pass | PASS |
| type lock | 4 text-bearing scenes sampled a second apart, 0 with a word in a different place, worst 0.529px | PASS |
| delivery audio | -16.5 dBFS mean, -13.7 LUFS against the mix's -14.0 (0.3 dB) | PASS |

## Luma map

One character per frame, 30 per row — a second a row. `#` is black, `+` under 12, then `.` `:` `-` `=` `*` `o` `O` `@` brightening. A cut is a step; a frame from somewhere else is one character that belongs to neither side of it.

```
    0.0s |++......::::::::::::::::::::::
    1.0s |::::::::::::::::::::::::::::::
    2.0s |::::::::::::::::::::::::::::::
    3.0s |::::::::::::::::::::::::::::::
    4.0s |::::::::::::::::::::::::::::::
    5.0s |::::::::::::::::::::::::::::::
    6.0s |::::::::::...#################
    7.0s |################++++++++++++++
    8.0s |++++++++++++++++++++++++++++++
    9.0s |++++++++++++++++++++++++++++++
   10.0s |++++++++++++++++++++++++++++++
   11.0s |++++++++++++++++++++++++++++++
   12.0s |++++++++++++++++++++++++++++++
   13.0s |+++++++++++++++++++++++....:::
   14.0s |::::::::::::::::::::::::::::::
   15.0s |::::::::::::::::::::::::::::::
   16.0s |::::::::::::::::::::::::::::::
   17.0s |::::::::::::::::::::::::::::::
   18.0s |::::::::::::::::::::::::::::::
   19.0s |::::::::::::::...+++++++++++++
   20.0s |++++++++++++++++++++++++++++++
   21.0s |++++++++++++++++++++++++++++++
   22.0s |++++++++++++++++++++++++++++++
   23.0s |++++++++++++++++++++++++++++++
   24.0s |++++++++++++++++++++++++++++++
   25.0s |++++++++++++++++++++++++++++++
   26.0s |+++++++++++++
```
