"""Authored texture beats.


reuse rule allows a clip once, so the thirteen that cannot be filled are
authored here rather than repeated — repetition is the defect this package
exists to fix.

Each entry is a distinct configuration of `texture_field`: kind, seed, density,
angle and speed all differ, so no two satisfy the rule's "identical component
and props" clause by accident. The kind is chosen from what the beat actually
shows, not assigned round-robin — water soaking into sand advances in bands
(strata), droplets at macro scale are discrete and dense (grain_drift), an
unlit interior is depth with nothing in it (depth_field).

Textures carry no figures, so none of these take a ledger id.
"""

A1 = {"actNumber": "01", "actTitle": "A verdict two thousand years old"}
A2 = {"actNumber": "02", "actTitle": "Where the stones came from"}
A3 = {"actNumber": "03", "actTitle": "What the stone itself says"}
A4 = {"actNumber": "04", "actTitle": "The cases nobody has closed"}


def _t(act, idx, kind, seed, density, angle, speed, caption=None):
    p = {**act, "sceneIndex": idx, "kind": kind, "seed": seed,
         "density": density, "angle": angle, "speed": speed}
    if caption:
        p["caption"] = caption
    return {"type": "texture_field", "props": p}


SLOTS = {
    # act1_s019 asked for a classical relief of a Cyclops. Commons has no such
    # category -- "Polyphemus" and "Cyclopes" are moths and silky anteaters --
    # and run #1 filled it with a photograph of the Mycenae wall, which is not
    # a relief of anything. It sits between a timeline (s018) and the Pausanias
    # document (s020), so a third text card would make three in a row; a dark
    # breathing beat between them is the better edit as well as the honest one.
    "act1_s019": _t(A1, "S 019", "depth_field", "cyclops-absent-019", 24, 36, 0.2),

    # --- act 1 / act 2 ---------------------------------------------------
    # A shaft of light is the one beat that is literally airborne dust.
    "act1_s046": _t(A1, "S 046", "dust", "shaft-light-046", 120, 72, 0.8),
    # Raking light across creased paper: long low bands, almost static.
    "act2_s073": _t(A2, "S 073", "strata", "map-creases-073", 30, 6, 0.15),

    # Scottish coast: the bank holds no Scottish coastline, and Stonehenge on
    # grass is not one. Horizontal depth, cool and slow.
    "act2_s080": _t(A2, "S 080", "depth_field", "scottish-coast-080", 44, 2, 0.38),
    # An empty horizon with nothing on it. The beat is the absence -- no source
    # describes the vessel -- so the sparsest configuration in act 2 says it.
    "act2_s084": _t(A2, "S 084", "strata", "empty-horizon-084", 16, 0, 0.14,
                    caption="No retrieved source describes the vessel"),
    # Machine register: fast, regular, nothing like the hand-worked beats
    # around it.
    "act3_s096": _t(A3, "S 096", "scanline", "drill-rig-096", 96, 0, 1.8),

    # --- act 3: the wetted-sand experiment -------------------------------
    # Poured sand is a narrow vertical fall of discrete grains.
    "act3_s104": _t(A3, "S 104", "grain_drift", "poured-sand-104", 170, 84, 1.25),
    # Slumping builds a ridge: bands advancing at a shallow angle.
    "act3_s124": _t(A3, "S 124", "strata", "slump-ridge-124", 40, 11, 0.3),
    # Soaking advances as a front, so this reads in bands rather than motes.
    "act3_s126": _t(A3, "S 126", "strata", "soak-front-126", 34, 4, 0.35),
    # Macro droplets are discrete and crowded; fastest drift in the set.
    "act3_s127": _t(A3, "S 127", "grain_drift", "bound-grains-127", 240, 28, 1.5),
    # A poured stream is near-vertical and narrow.
    "act3_s132": _t(A3, "S 132", "grain_drift", "thin-stream-132", 90, 86, 1.1),
    # A tool set down: coarse stone, almost still. The beat is the stopping.
    "act3_s141": _t(A3, "S 141", "strata", "tool-down-141", 18, 2, 0.12),

    # --- act 4: the four open files --------------------------------------
    # The same sea with the horizon taken away: low contrast, no band.
    "act4_s147": _t(A4, "S 147 / FILE 1", "strata", "no-horizon-147", 26, -3, 0.22),
    "act4_s172": _t(A4, "S 172 / FILE 4", "grain_drift", "river-cobbles-172", 54, 16, 0.5),
    # A gap in masonry is vertical and dark.
    "act4_s167": _t(A4, "S 167 / FILE 4", "depth_field", "narrow-gap-167", 30, 90, 0.3),
    # Torchlight not reaching the back: sparse warm motes, nothing behind them.
    "act4_s168": _t(A4, "S 168 / FILE 4", "dust", "torch-falloff-168", 38, 64, 0.45),
    # The closing pair -- depth without detail, then depth unresolved. The
    # sparsest configurations in the film, because the film ends on not knowing.
    "act4_s180": _t(A4, "S 180", "depth_field", "dark-interior-180", 20, 48, 0.18),
    "act4_s181": _t(A4, "S 181", "scanline", "unresolved-181", 14, 0, 0.1),
    # Altiplano light: airborne and warm, the only fast dust in the film.
    # A gap in masonry is vertical and dark.
    # Torchlight not reaching the back: sparse warm motes, nothing behind them.
    "act4_s172": _t(A4, "S 172 / FILE 4", "grain_drift", "river-cobbles-172", 54, 16, 0.5),
    # A gap in masonry is vertical and dark.
    "act4_s167": _t(A4, "S 167 / FILE 4", "depth_field", "narrow-gap-167", 30, 90, 0.3),
    # Torchlight not reaching the back: sparse warm motes, nothing behind them.
    "act4_s168": _t(A4, "S 168 / FILE 4", "dust", "torch-falloff-168", 38, 64, 0.45),
    # The closing pair -- depth without detail, then depth unresolved. The
    # sparsest configurations in the film, because the film ends on not knowing.
    "act4_s180": _t(A4, "S 180", "depth_field", "dark-interior-180", 20, 48, 0.18),
    "act4_s181": _t(A4, "S 181", "scanline", "unresolved-181", 14, 0, 0.1),
    # The closing pair: depth without detail, then depth unresolved. Sparsest
    # configurations in the film, because the film ends on not knowing.
}
