"""Process shots — beats the asset bank cannot photograph.

These three slots describe laboratory and workshop states that no screened
Commons category holds at a usable resolution: a kerf part-way through a block,
a scratch test, and a tray with a model sled. Two were reworked after checking
their neighbours, because the first choice would have duplicated a graphic two
shots away:

  act3_s112 was planned as "Mohs hardness specimens arranged in order", but
  act3_s113 is already a hardness scale_comparison ten seconds later. It is
  authored instead as the scratch TEST — the physical act the scale is derived
  from — and deliberately carries no hardness numbers, leaving those to s113.

  act3_s105 is a PLAN view down the annulus. act3_s103 is the same mechanism in
  SECTION, so the projection is what keeps them two shots and not one twice.

Every figure is bound to a ledger id; nothing here states a number that
research_brief.json does not carry.
"""

A1 = {"actNumber": "01", "actTitle": "The argument that will not die"}
A3 = {"actNumber": "03", "actTitle": "The hole in the granite"}
A4 = {"actNumber": "04", "actTitle": "The cases nobody has closed"}

INK, MUTED, RULE, ACCENT, VOID, STONE = "#EDE6D8", "#8A8578", "#3A3630", "#C08A3E", "#0C0C0E", "#17171C"

SLOTS = {
    # ---------------------------------------------------------------- act 1

    # ---------------------------------------------------------------- act 3
    # Looking down the drill: the annular kerf, sand in the gap, core inside.
    "act3_s105": {
        "_ledger": ["c22", "c24"],
        "type": "schematic",
        "props": {
            **A3, "sceneIndex": "S 105 / KERF, PLAN",
            "kicker": "Mechanism — from above",
            "title": "Part-way through",
            "caption": "The cut is an annulus. Sand fills it; the core is what is left standing",
            "source": "Ledger c22, c24",
            "layers": [
                {"id": "block", "kind": "rect", "x": 560, "y": 220, "w": 800, "h": 640,
                 "stroke": MUTED, "fill": STONE, "strokeWidth": 3},
                {"id": "outer", "kind": "circle", "x": 960, "y": 540, "r": 230,
                 "stroke": RULE, "fill": VOID, "strokeWidth": 2},
                {"id": "inner", "kind": "circle", "x": 960, "y": 540, "r": 170,
                 "stroke": INK, "fill": STONE, "strokeWidth": 2},
                {"id": "tubeO", "kind": "circle", "x": 960, "y": 540, "r": 222,
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 6},
                {"id": "tubeI", "kind": "circle", "x": 960, "y": 540, "r": 178,
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 6},
                {"id": "g1", "kind": "circle", "x": 960, "y": 340, "r": 6, "fill": INK, "stroke": "none"},
                {"id": "g2", "kind": "circle", "x": 1098, "y": 468, "r": 5, "fill": INK, "stroke": "none"},
                {"id": "g3", "kind": "circle", "x": 1060, "y": 690, "r": 6, "fill": INK, "stroke": "none"},
                {"id": "g4", "kind": "circle", "x": 838, "y": 650, "r": 5, "fill": INK, "stroke": "none"},
                {"id": "g5", "kind": "circle", "x": 806, "y": 452, "r": 6, "fill": INK, "stroke": "none"},
                {"id": "lead", "kind": "line", "x": 1182, "y": 540, "x2": 1368, "y2": 540,
                 "stroke": RULE, "strokeWidth": 2},
                {"id": "leadc", "kind": "line", "x": 960, "y": 370, "x2": 960, "y2": 258,
                 "stroke": RULE, "strokeWidth": 2},
            ],
            "reveals": [
                {"layer_id": "block", "at": 0.1, "effect": "fade"},
                {"layer_id": "outer", "at": 0.6, "effect": "draw", "duration": 0.7},
                {"layer_id": "inner", "at": 0.9, "effect": "draw", "duration": 0.7},
                {"layer_id": "tubeO", "at": 1.6, "effect": "draw", "duration": 0.6},
                {"layer_id": "tubeI", "at": 1.6, "effect": "draw", "duration": 0.6},
                {"layer_id": "g1", "at": 2.4, "effect": "fade"},
                {"layer_id": "g2", "at": 2.55, "effect": "fade"},
                {"layer_id": "g3", "at": 2.7, "effect": "fade"},
                {"layer_id": "g4", "at": 2.85, "effect": "fade"},
                {"layer_id": "g5", "at": 3.0, "effect": "fade"},
                {"layer_id": "lead", "at": 3.3, "effect": "draw", "duration": 0.4},
                {"layer_id": "leadc", "at": 3.8, "effect": "draw", "duration": 0.4},
            ],
            "labels": [
                {"text": "sand in the kerf", "x": 1392, "y": 548, "at": 3.6,
                 "anchor": "start", "accent": True},
                {"text": "core", "x": 960, "y": 232, "at": 4.1, "anchor": "middle"},
            ],
        },
    },

    # The scratch test, not the scale. s113 carries the numbers.
    "act3_s112": {
        "_ledger": ["c24"],
        "type": "schematic",
        "props": {
            **A3, "sceneIndex": "S 112 / THE TEST",
            "kicker": "How hardness is decided",
            "title": "One scratches the other, or it does not",
            "caption": "The test is a groove. Which material leaves it is the whole question",
            "source": "Ledger c24",
            "layers": [
                {"id": "plate", "kind": "rect", "x": 420, "y": 560, "w": 1080, "h": 230,
                 "stroke": MUTED, "fill": STONE, "strokeWidth": 3},
                {"id": "groove", "kind": "line", "x": 520, "y": 600, "x2": 1270, "y2": 600,
                 "stroke": INK, "strokeWidth": 4},
                {"id": "stylus", "kind": "polyline",
                 "points": "1300,420 1356,420 1328,576 1300,420",
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 5},
                {"id": "arrow", "kind": "line", "x": 1250, "y": 480, "x2": 980, "y2": 480,
                 "stroke": MUTED, "strokeWidth": 3},
                {"id": "head", "kind": "polyline", "points": "1004,468 980,480 1004,492",
                 "stroke": MUTED, "fill": "none", "strokeWidth": 3},
                {"id": "spoil1", "kind": "circle", "x": 1282, "y": 588, "r": 5, "fill": INK, "stroke": "none"},
                {"id": "spoil2", "kind": "circle", "x": 1296, "y": 572, "r": 4, "fill": INK, "stroke": "none"},
            ],
            "reveals": [
                {"layer_id": "plate", "at": 0.1, "effect": "fade"},
                {"layer_id": "stylus", "at": 0.7, "effect": "draw", "duration": 0.6},
                {"layer_id": "arrow", "at": 1.5, "effect": "draw", "duration": 0.5},
                {"layer_id": "head", "at": 1.9, "effect": "draw", "duration": 0.3},
                {"layer_id": "groove", "at": 2.2, "effect": "draw", "duration": 1.4},
                {"layer_id": "spoil1", "at": 3.4, "effect": "fade"},
                {"layer_id": "spoil2", "at": 3.6, "effect": "fade"},
            ],
            "labels": [
                {"text": "harder material", "x": 1328, "y": 384, "at": 1.2,
                 "anchor": "middle", "accent": True},
                {"text": "softer material", "x": 460, "y": 860, "at": 3.0, "anchor": "start"},
            ],
        },
    },

    # The rate, as an accumulating volume.

    # The extrapolation: the tray that the pyramid claim was scaled up from.
    "act3_s133": {
        "_ledger": ["c15", "c17"],
        "type": "schematic",
        "props": {
            **A3, "sceneIndex": "S 133 / THE TRAY",
            "kicker": "What was actually measured",
            "title": "A tray, and what was read from it",
            "caption": "An extrapolation from a laboratory tray",
            "source": "Ledger c15, c17",
            "layers": [
                {"id": "tray", "kind": "rect", "x": 300, "y": 700, "w": 420, "h": 110,
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "sand", "kind": "rect", "x": 306, "y": 752, "w": 408, "h": 54,
                 "stroke": "none", "fill": RULE},
                {"id": "sled", "kind": "polyline", "points": "420,752 540,752 528,724 432,724 420,752",
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 4},
                {"id": "pull", "kind": "line", "x": 540, "y": 738, "x2": 626, "y2": 718,
                 "stroke": MUTED, "strokeWidth": 2},
                {"id": "gap", "kind": "line", "x": 760, "y": 756, "x2": 1120, "y2": 756,
                 "stroke": RULE, "strokeWidth": 2, "dashed": True},
                # The colossus at the far end of the arrow, as a mass, not a drawing.
                {"id": "col", "kind": "rect", "x": 1180, "y": 420, "w": 300, "h": 390,
                 "stroke": MUTED, "fill": STONE, "strokeWidth": 3},
                {"id": "colsled", "kind": "polyline",
                 "points": "1150,810 1510,810 1486,854 1174,854 1150,810",
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 4},
                {"id": "ground", "kind": "line", "x": 240, "y": 854, "x2": 1680, "y2": 854,
                 "stroke": RULE, "strokeWidth": 2},
            ],
            "reveals": [
                {"layer_id": "ground", "at": 0.1, "effect": "draw", "duration": 0.6},
                {"layer_id": "tray", "at": 0.6, "effect": "draw", "duration": 0.6},
                {"layer_id": "sand", "at": 1.1, "effect": "fade"},
                {"layer_id": "sled", "at": 1.5, "effect": "draw", "duration": 0.5},
                {"layer_id": "pull", "at": 2.0, "effect": "draw", "duration": 0.3},
                {"layer_id": "gap", "at": 2.6, "effect": "draw", "duration": 0.9},
                {"layer_id": "col", "at": 3.5, "effect": "fade"},
                {"layer_id": "colsled", "at": 3.9, "effect": "draw", "duration": 0.5},
            ],
            "labels": [
                {"text": "measured here", "x": 510, "y": 666, "at": 2.2,
                 "anchor": "middle", "accent": True},
                {"text": "claimed for this", "x": 1330, "y": 386, "at": 4.3, "anchor": "middle"},
            ],
        },
    },

    # The bank's Egyptian material is painted wooden coffins, not worked
    # granite, so the tool marks Petrie recorded are drawn rather than
    # photographed. Section, not plan or elevation -- s103 and s105 hold those.
    "act3_s092": {
        "_ledger": ["c24", "c26"],
        "type": "schematic",
        "props": {
            **A3, "sceneIndex": "S 092 / TOOL MARKS",
            "kicker": "What Petrie recorded",
            "title": "Marks on the inside face",
            "caption": "Drawn, not photographed: the bank holds no worked-granite interior",
            "source": "Ledger c24, c26",
            "layers": [
                {"id": "box", "kind": "polyline",
                 "points": "420,340 1500,340 1500,840 420,840 420,340",
                 "stroke": MUTED, "fill": STONE, "strokeWidth": 3},
                {"id": "cavity", "kind": "rect", "x": 500, "y": 410, "w": 920, "h": 360,
                 "stroke": INK, "fill": VOID, "strokeWidth": 3},
                {"id": "m1", "kind": "line", "x": 540, "y": 440, "x2": 540, "y2": 740,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "m2", "kind": "line", "x": 596, "y": 440, "x2": 596, "y2": 740,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "m3", "kind": "line", "x": 652, "y": 440, "x2": 652, "y2": 740,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "m4", "kind": "line", "x": 708, "y": 440, "x2": 708, "y2": 740,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "arc", "kind": "path", "d": "M 1180 470 a 150 150 0 0 0 0 240",
                 "stroke": ACCENT, "strokeWidth": 3},
                {"id": "lead", "kind": "line", "x": 760, "y": 590, "x2": 980, "y2": 590,
                 "stroke": RULE, "strokeWidth": 2},
                {"id": "lead2", "kind": "line", "x": 1196, "y": 706, "x2": 1528, "y2": 706,
                 "stroke": RULE, "strokeWidth": 2},
            ],
            "reveals": [
                {"layer_id": "box", "at": 0.1, "effect": "draw", "duration": 0.8},
                {"layer_id": "cavity", "at": 0.9, "effect": "draw", "duration": 0.7},
                {"layer_id": "m1", "at": 1.8, "effect": "draw", "duration": 0.3},
                {"layer_id": "m2", "at": 1.95, "effect": "draw", "duration": 0.3},
                {"layer_id": "m3", "at": 2.1, "effect": "draw", "duration": 0.3},
                {"layer_id": "m4", "at": 2.25, "effect": "draw", "duration": 0.3},
                {"layer_id": "arc", "at": 2.8, "effect": "draw", "duration": 0.7},
                {"layer_id": "lead", "at": 3.4, "effect": "draw", "duration": 0.4},
                {"layer_id": "lead2", "at": 3.9, "effect": "draw", "duration": 0.4},
            ],
            "labels": [
                {"text": "parallel striations", "x": 1004, "y": 598, "at": 3.7,
                 "anchor": "start", "accent": True},
                # Outside the box and 110px below the striations label. Centred
                # under the box it read as a caption for the whole section;
                # beside the arc it sat on the striations label's baseline.
                {"text": "rounded corner", "x": 1544, "y": 712, "at": 4.2, "anchor": "start"},
            ],
        },
    },

    # ---------------------------------------------------------------- act 4
    # The bank's muon material is collider hardware at Brookhaven and CERN,
    # which is not what ScanPyramids used, so the three technologies are drawn.
    # Three INDEPENDENT methods agreeing is the whole weight of the result.
    "act4_s163": {
        "_ledger": ["c39"],
        "type": "schematic",
        "props": {
            **A4, "sceneIndex": "S 163 / FILE 3",
            "kicker": "Three methods, three teams",
            "title": "Agreeing independently",
            "caption": "Nuclear emulsion, scintillator hodoscopes and gas detectors — three groups",
            "source": "Ledger c39",
            "layers": [
                {"id": "u1", "kind": "rect", "x": 300, "y": 430, "w": 300, "h": 210,
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "u2", "kind": "rect", "x": 810, "y": 430, "w": 300, "h": 210,
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "u3", "kind": "rect", "x": 1320, "y": 430, "w": 300, "h": 210,
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "p1", "kind": "line", "x": 340, "y": 470, "x2": 560, "y2": 470,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "p2", "kind": "line", "x": 340, "y": 500, "x2": 560, "y2": 500,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "g1", "kind": "circle", "x": 960, "y": 500, "r": 9,
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 3},
                {"id": "g2", "kind": "circle", "x": 960, "y": 570, "r": 9,
                 "stroke": ACCENT, "fill": "none", "strokeWidth": 3},
                {"id": "h1", "kind": "line", "x": 1360, "y": 470, "x2": 1360, "y2": 600,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "h2", "kind": "line", "x": 1420, "y": 470, "x2": 1420, "y2": 600,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "h3", "kind": "line", "x": 1480, "y": 470, "x2": 1480, "y2": 600,
                 "stroke": ACCENT, "strokeWidth": 2},
                {"id": "track", "kind": "line", "x": 300, "y": 300, "x2": 1620, "y2": 300,
                 "stroke": RULE, "strokeWidth": 2, "dashed": True},
                {"id": "d1", "kind": "line", "x": 450, "y": 300, "x2": 450, "y2": 430,
                 "stroke": MUTED, "strokeWidth": 2},
                {"id": "d2", "kind": "line", "x": 960, "y": 300, "x2": 960, "y2": 430,
                 "stroke": MUTED, "strokeWidth": 2},
                {"id": "d3", "kind": "line", "x": 1470, "y": 300, "x2": 1470, "y2": 430,
                 "stroke": MUTED, "strokeWidth": 2},
            ],
            "reveals": [
                {"layer_id": "track", "at": 0.1, "effect": "draw", "duration": 0.8},
                {"layer_id": "u1", "at": 0.8, "effect": "draw", "duration": 0.5},
                {"layer_id": "u2", "at": 1.1, "effect": "draw", "duration": 0.5},
                {"layer_id": "u3", "at": 1.4, "effect": "draw", "duration": 0.5},
                {"layer_id": "p1", "at": 2.0, "effect": "draw", "duration": 0.3},
                {"layer_id": "p2", "at": 2.1, "effect": "draw", "duration": 0.3},
                {"layer_id": "g1", "at": 2.3, "effect": "fade"},
                {"layer_id": "g2", "at": 2.45, "effect": "fade"},
                {"layer_id": "h1", "at": 2.6, "effect": "draw", "duration": 0.3},
                {"layer_id": "h2", "at": 2.7, "effect": "draw", "duration": 0.3},
                {"layer_id": "h3", "at": 2.8, "effect": "draw", "duration": 0.3},
                {"layer_id": "d1", "at": 3.3, "effect": "draw", "duration": 0.4},
                {"layer_id": "d2", "at": 3.5, "effect": "draw", "duration": 0.4},
                {"layer_id": "d3", "at": 3.7, "effect": "draw", "duration": 0.4},
            ],
            "labels": [
                {"text": "emulsion film", "x": 450, "y": 700, "at": 4.0, "anchor": "middle"},
                {"text": "gas detectors", "x": 960, "y": 700, "at": 4.2, "anchor": "middle"},
                {"text": "scintillator", "x": 1470, "y": 700, "at": 4.4, "anchor": "middle"},
                {"text": "same signal", "x": 960, "y": 252, "at": 4.7,
                 "anchor": "middle", "accent": True},
            ],
        },
    },
    # act4_s143 is the Altar Stone slab; run #1 gave that one photograph to
    # both slots, so this beat -- the act-four enumeration -- is drawn.
    "act4_s142": {
        "_ledger": ["c11"],
        "type": "schematic",
        "props": {
            **A4, "sceneIndex": "S 142 / FOUR FILES",
            "kicker": "Act four",
            "title": "Four files. Still open",
            "caption": "Four questions the literature has not closed",
            "source": "Ledger c11",
            "layers": [
                {"id": "f1", "kind": "polyline",
                 "points": "300,470 452,452 486,588 334,620 300,470",
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "f2", "kind": "polyline",
                 "points": "640,444 800,470 776,606 626,586 640,444",
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "f3", "kind": "polyline",
                 "points": "980,462 1140,440 1166,598 1004,610 980,462",
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "f4", "kind": "polyline",
                 "points": "1320,450 1486,468 1460,604 1306,590 1320,450",
                 "stroke": INK, "fill": STONE, "strokeWidth": 3},
                {"id": "base", "kind": "line", "x": 280, "y": 660, "x2": 1510, "y2": 660,
                 "stroke": RULE, "strokeWidth": 2},
            ],
            "reveals": [
                {"layer_id": "base", "at": 0.1, "effect": "draw", "duration": 0.7},
                {"layer_id": "f1", "at": 0.8, "effect": "draw", "duration": 0.5},
                {"layer_id": "f2", "at": 1.3, "effect": "draw", "duration": 0.5},
                {"layer_id": "f3", "at": 1.8, "effect": "draw", "duration": 0.5},
                {"layer_id": "f4", "at": 2.3, "effect": "draw", "duration": 0.5},
            ],
            "labels": [
                {"text": "01", "x": 393, "y": 724, "at": 2.9, "anchor": "middle", "level": "data"},
                {"text": "02", "x": 713, "y": 724, "at": 3.1, "anchor": "middle", "level": "data"},
                {"text": "03", "x": 1073, "y": 724, "at": 3.3, "anchor": "middle", "level": "data"},
                {"text": "04", "x": 1396, "y": 724, "at": 3.5, "anchor": "middle", "level": "data"},
            ],
        },
    },
}
