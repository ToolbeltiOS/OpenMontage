"""Cold open and act 1 — the verdict that is two thousand years old."""

ACT1 = {"actNumber": "01", "actTitle": "A verdict two thousand years old"}
COLD = {"actNumber": "00", "actTitle": "Cold open"}

SLOTS = {
    # ── cold open ────────────────────────────────────────────────────────
    "cold_open_s003": {
        "_ledger": ["c36"],
        "type": "map_route",
        "props": {
            **COLD,
            "sceneIndex": "S 003 / RAPA NUI",
            "kicker": "Where this starts",
            "title": "Rapa Nui",
            # Drawn to the nearest continental coast so the ocean gap is the
            # subject. No distance is stated: the ledger carries no figure for
            # the island's isolation and the drawn line is not a claimed route.
            "route": [[-109.35, -27.12], [-71.5, -33.0]],
            "arc": True,
            "markers": [
                {"lon": -109.35, "lat": -27.12, "label": "Rapa Nui", "at": 0.5, "dx": 24, "dy": -14},
                {"lon": -71.5, "lat": -33.0, "label": "South America", "at": 2.6, "dx": 22, "dy": 28},
            ],
            "center": [-92.0, -29.0],
            "scale": 420,
            "draw_at": 1.0,
            "draw_seconds": 2.8,
            "caption": "More than 900 statues were made here, and moved",
            "source": "Ledger c36",
        },
    },
    "cold_open_s005": {
        "_ledger": ["c36", "c37"],
        "type": "scale_comparison",
        "props": {
            **COLD,
            "sceneIndex": "S 005 / RANO RARAKU",
            "kicker": "The quarry",
            "title": "What came out of one hillside",
            "unit": "tonnes",
            "at": 0.6,
            "items": [
                {"label": "Ahu Tongariki moai", "value": 86, "note": "heaviest ever erected", "hero": True},
                {"label": "Paro", "value": 82, "note": "tallest erected — 9.8 m"},
            ],
            "footnote": "More than 900 statues were produced and transported. An unfinished figure still in the quarry is larger again; its published masses disagree, so no figure is given for it.",
            "caption": "Erected masses are solid; quarry estimates are not",
            "source": "Ledger c36, c37",
        },
    },

    # ── act 1 ────────────────────────────────────────────────────────────
    "act1_s010": {
        "_ledger": ["c02"],
        "type": "schematic",
        "props": {
            **ACT1,
            "sceneIndex": "S 010 / TIRYNS",
            "kicker": "The wall",
            "title": "Unwrought stones, matched face to face",
            "caption": "No mortar — the fit is the only thing holding the course",
            "source": "After Pausanias, Description of Greece II",
            "layers": [
                {"id": "ground", "kind": "line", "x": 300, "y": 830, "x2": 1620, "y2": 830, "stroke": "#3A3630", "strokeWidth": 3},
                # the wall in section: two faces of irregular blocks, rubble core
                {"id": "faceL", "kind": "polyline", "points": "620,830 604,752 628,676 606,598 630,520 612,448", "stroke": "#EDE6D8", "strokeWidth": 3},
                {"id": "faceR", "kind": "polyline", "points": "1120,830 1140,748 1112,672 1138,596 1114,520 1136,448", "stroke": "#EDE6D8", "strokeWidth": 3},
                {"id": "top", "kind": "line", "x": 612, "y": 448, "x2": 1136, "y2": 448, "stroke": "#EDE6D8", "strokeWidth": 3},
                {"id": "core1", "kind": "circle", "x": 760, "y": 690, "r": 26, "stroke": "#55514A", "strokeWidth": 2},
                {"id": "core2", "kind": "circle", "x": 860, "y": 620, "r": 34, "stroke": "#55514A", "strokeWidth": 2},
                {"id": "core3", "kind": "circle", "x": 970, "y": 700, "r": 30, "stroke": "#55514A", "strokeWidth": 2},
                {"id": "core4", "kind": "circle", "x": 900, "y": 770, "r": 22, "stroke": "#55514A", "strokeWidth": 2},
                # a standing figure for scale, drawn not photographed
                {"id": "fig", "kind": "path", "d": "M 430 830 L 430 760 M 430 760 L 408 720 M 430 760 L 452 720 M 430 760 L 430 700 M 430 700 L 406 672 M 430 700 L 454 672 M 430 686 a 15 15 0 1 0 0.1 0", "stroke": "#C08A3E", "strokeWidth": 3},
                {"id": "dimL", "kind": "line", "x": 612, "y": 890, "x2": 1136, "y2": 890, "stroke": "#8A8578", "strokeWidth": 1.5},
                {"id": "dimT1", "kind": "line", "x": 612, "y": 876, "x2": 612, "y2": 904, "stroke": "#8A8578", "strokeWidth": 1.5},
                {"id": "dimT2", "kind": "line", "x": 1136, "y": 876, "x2": 1136, "y2": 904, "stroke": "#8A8578", "strokeWidth": 1.5},
            ],
            "reveals": [
                {"layer_id": "ground", "at": 0.1, "effect": "fade"},
                {"layer_id": "faceL", "at": 0.4, "effect": "draw", "duration": 0.9},
                {"layer_id": "faceR", "at": 0.7, "effect": "draw", "duration": 0.9},
                {"layer_id": "top", "at": 1.5, "effect": "draw", "duration": 0.5},
                {"layer_id": "core1", "at": 2.0, "effect": "fade"},
                {"layer_id": "core2", "at": 2.1, "effect": "fade"},
                {"layer_id": "core3", "at": 2.2, "effect": "fade"},
                {"layer_id": "core4", "at": 2.3, "effect": "fade"},
                {"layer_id": "fig", "at": 2.9, "effect": "draw", "duration": 0.7},
                {"layer_id": "dimL", "at": 3.6, "effect": "draw", "duration": 0.6},
                {"layer_id": "dimT1", "at": 3.6, "effect": "fade"},
                {"layer_id": "dimT2", "at": 4.0, "effect": "fade"},
            ],
            "labels": [
                {"text": "dressed outer face", "x": 500, "y": 416, "at": 1.9, "anchor": "start"},
                {"text": "rubble core", "x": 1230, "y": 614, "at": 2.5, "anchor": "start", "accent": True},
                {"text": "a standing adult", "x": 430, "y": 646, "at": 3.3, "anchor": "middle"},
                {"text": "wall thickness", "x": 874, "y": 948, "at": 4.3, "anchor": "middle", "level": "data"},
            ],
        },
    },
    "act1_s015": {
        "_ledger": ["c01", "c02"],
        "type": "schematic",
        "props": {
            **ACT1,
            "sceneIndex": "S 015 / THE JOINT",
            "kicker": "The fit",
            "title": "Irregular to irregular",
            "caption": "Each face is cut to the face it meets, and to no other",
            "layers": [
                {"id": "lower", "kind": "path", "d": "M 420 760 L 1500 760 L 1500 640 L 1380 628 L 1250 664 L 1100 622 L 960 668 L 820 618 L 680 658 L 540 622 L 420 648 Z", "stroke": "#EDE6D8", "fill": "#14141A", "strokeWidth": 3},
                {"id": "upper", "kind": "path", "d": "M 420 644 L 540 618 L 680 654 L 820 614 L 960 664 L 1100 618 L 1250 660 L 1380 624 L 1500 636 L 1500 420 L 420 420 Z", "stroke": "#EDE6D8", "fill": "#17171C", "strokeWidth": 3},
                {"id": "contact", "kind": "path", "d": "M 420 646 L 540 620 L 680 656 L 820 616 L 960 666 L 1100 620 L 1250 662 L 1380 626 L 1500 638", "stroke": "#C08A3E", "strokeWidth": 4},
                {"id": "gapcall", "kind": "line", "x": 960, "y": 666, "x2": 1060, "y2": 862, "stroke": "#C08A3E", "strokeWidth": 1.5},
            ],
            "reveals": [
                {"layer_id": "lower", "at": 0.2, "effect": "fade"},
                {"layer_id": "upper", "at": 1.0, "effect": "slide-in"},
                {"layer_id": "contact", "at": 2.4, "effect": "draw", "duration": 1.4},
                {"layer_id": "gapcall", "at": 4.1, "effect": "draw", "duration": 0.4},
            ],
            "labels": [
                {"text": "upper course", "x": 470, "y": 500, "at": 1.8, "anchor": "start"},
                {"text": "lower course", "x": 470, "y": 724, "at": 0.9, "anchor": "start"},
                {"text": "no mortar layer", "x": 1070, "y": 898, "at": 4.4, "anchor": "start", "accent": True},
            ],
        },
    },
    "act1_s018": {
        "_ledger": ["c02", "c03"],
        "type": "timeline",
        "props": {
            **ACT1,
            "sceneIndex": "S 018 / CHRONOLOGY",
            "kicker": "Chronology",
            "title": "Fourteen centuries of silence",
            "events": [
                {"year": -1400, "label": "Tiryns at its peak", "at": 0.5},
                {"year": -1200, "label": "the Mycenaean world ends", "at": 1.6},
                {"year": 170, "label": "Pausanias writes", "at": 3.0, "accent": True},
            ],
            "span": [-1700, 500],
            "caption": "The walls were already 1,400 years old when the account was written",
            "source": "Ledger c02, c03",
        },
    },
    "act1_s020": {
        "_ledger": ["c02"],
        "type": "document_reveal",
        "props": {
            **ACT1,
            "sceneIndex": "S 020 / TIRYNS",
            "kicker": "The record",
            "headline": "Pausanias, Description of Greece",
            "lines": [
                {"text": "“…the wall at Tiryns, which is made of unwrought stones,", "at": 0.6},
                {"text": "every stone being so big that a pair of mules", "at": 1.8},
                {"text": "could not move the smallest from its place.”", "at": 3.0, "emphasis": True},
            ],
            "source": "Book II, 2nd century CE — ledger c02",
            "paper": "dark",
            "light_sweep": True,
            "sweep_at": 3.6,
        },
    },
    "act1_s023": {
        "_ledger": ["c01", "c02"],
        "type": "schematic",
        "props": {
            **ACT1,
            "sceneIndex": "S 023 / THE INFERENCE",
            "kicker": "The shape of the reasoning",
            "title": "Too big for the men available",
            # Deliberately not a data chart: no retrieved source gives a
            # haulage capacity for a Mycenaean team, so the graphic draws the
            # structure of the inference rather than inventing a figure.
            "caption": "No retrieved source gives a haulage figure — this is the inference, not a measurement",
            "layers": [
                {"id": "block", "kind": "rect", "x": 360, "y": 470, "w": 420, "h": 300, "stroke": "#EDE6D8", "fill": "#17171C", "strokeWidth": 3},
                {"id": "men", "kind": "polyline", "points": "900,770 900,700 876,660 900,700 924,660 900,700", "stroke": "#8A8578", "strokeWidth": 3},
                {"id": "men2", "kind": "polyline", "points": "980,770 980,700 956,660 980,700 1004,660 980,700", "stroke": "#8A8578", "strokeWidth": 3},
                {"id": "men3", "kind": "polyline", "points": "1060,770 1060,700 1036,660 1060,700 1084,660 1060,700", "stroke": "#8A8578", "strokeWidth": 3},
                {"id": "gap", "kind": "line", "x": 800, "y": 620, "x2": 1480, "y2": 620, "stroke": "#C08A3E", "strokeWidth": 2, "dashed": True},
                {"id": "concl", "kind": "rect", "x": 1180, "y": 470, "w": 380, "h": 300, "stroke": "#C08A3E", "strokeWidth": 3, "dashed": True},
                {"id": "base", "kind": "line", "x": 300, "y": 772, "x2": 1620, "y2": 772, "stroke": "#3A3630", "strokeWidth": 3},
            ],
            "reveals": [
                {"layer_id": "base", "at": 0.1, "effect": "fade"},
                {"layer_id": "block", "at": 0.5, "effect": "fade"},
                {"layer_id": "men", "at": 1.4, "effect": "draw", "duration": 0.4},
                {"layer_id": "men2", "at": 1.6, "effect": "draw", "duration": 0.4},
                {"layer_id": "men3", "at": 1.8, "effect": "draw", "duration": 0.4},
                {"layer_id": "gap", "at": 2.8, "effect": "draw", "duration": 0.8},
                {"layer_id": "concl", "at": 4.0, "effect": "fade"},
            ],
            "labels": [
                {"text": "the stone", "x": 570, "y": 430, "at": 1.0, "anchor": "middle"},
                {"text": "the men", "x": 980, "y": 820, "at": 2.2, "anchor": "middle"},
                {"text": "therefore: a stronger builder", "x": 1370, "y": 430, "at": 4.4, "anchor": "middle", "accent": True},
            ],
        },
    },
    "act1_s028": {
        "_ledger": ["c34"],
        "type": "map_route",
        "props": {
            **ACT1,
            "sceneIndex": "S 028 / THE SHELF",
            "kicker": "Where nobody has dug",
            "title": "The coastlines that are now under water",
            "route": [[-9.0, 36.5], [-1.5, 44.0], [-4.5, 50.0], [-6.0, 54.0], [-2.0, 58.0]],
            "arc": False,
            "markers": [
                {"lon": -9.0, "lat": 36.5, "label": "Iberian shelf", "at": 0.8, "dx": 24, "dy": 26},
                {"lon": -2.0, "lat": 58.0, "label": "North Sea shelf", "at": 3.0, "dx": 22, "dy": -12},
            ],
            "center": [-4.0, 48.0],
            "scale": 760,
            "draw_at": 1.1,
            "draw_seconds": 2.6,
            "caption": "Hancock's standing argument: the Sahara, the Amazon and the drowned coasts are unexplored",
            "source": "Ledger c34 — attributed, not endorsed",
        },
    },
    "act1_s033": {
        "_ledger": ["c32", "c33"],
        "type": "timeline",
        "props": {
            **ACT1,
            "sceneIndex": "S 033 / YOUNGER DRYAS",
            "kicker": "The claimed date",
            "title": "About 12,900 years ago",
            "events": [
                {"year": -10900, "label": "Younger Dryas onset", "at": 0.7, "accent": True},
                {"year": -1400, "label": "Tiryns at its peak", "at": 2.4},
                {"year": 170, "label": "Pausanias writes", "at": 3.6},
            ],
            "span": [-13500, 600],
            "caption": "Hancock dates the loss to the Younger Dryas; most relevant experts reject the impact claim",
            "source": "Ledger c32, c33",
        },
    },
    "act1_s036": {
        "_ledger": ["c33"],
        "type": "schematic",
        "props": {
            **ACT1,
            "sceneIndex": "S 036 / MECHANISMS",
            "kicker": "The mainstream account",
            "title": "Two explanations, neither cinematic",
            "caption": "Meltwater influx into the Atlantic, or volcanism",
            "source": "Ledger c33",
            "layers": [
                {"id": "divider", "kind": "line", "x": 960, "y": 360, "x2": 960, "y2": 880, "stroke": "#3A3630", "strokeWidth": 1.5},
                {"id": "seaL", "kind": "path", "d": "M 300 760 L 880 760 L 880 880 L 300 880 Z", "stroke": "#3A3630", "fill": "#14141A", "strokeWidth": 2},
                {"id": "ice", "kind": "path", "d": "M 330 640 L 470 540 L 610 616 L 700 560 L 760 650 L 760 760 L 330 760 Z", "stroke": "#EDE6D8", "fill": "#17171C", "strokeWidth": 3},
                {"id": "melt1", "kind": "line", "x": 700, "y": 690, "x2": 800, "y2": 756, "stroke": "#C08A3E", "strokeWidth": 3},
                {"id": "melt2", "kind": "line", "x": 740, "y": 650, "x2": 840, "y2": 752, "stroke": "#C08A3E", "strokeWidth": 3},
                {"id": "volc", "kind": "path", "d": "M 1080 880 L 1300 580 L 1520 880 Z", "stroke": "#EDE6D8", "fill": "#17171C", "strokeWidth": 3},
                {"id": "plume", "kind": "path", "d": "M 1300 580 C 1250 480 1360 440 1300 350", "stroke": "#C08A3E", "strokeWidth": 3, "dashed": True},
            ],
            "reveals": [
                {"layer_id": "divider", "at": 0.2, "effect": "fade"},
                {"layer_id": "seaL", "at": 0.5, "effect": "fade"},
                {"layer_id": "ice", "at": 0.9, "effect": "draw", "duration": 1.0},
                {"layer_id": "melt1", "at": 2.1, "effect": "draw", "duration": 0.4},
                {"layer_id": "melt2", "at": 2.3, "effect": "draw", "duration": 0.4},
                {"layer_id": "volc", "at": 3.1, "effect": "draw", "duration": 0.9},
                {"layer_id": "plume", "at": 4.1, "effect": "draw", "duration": 0.8},
            ],
            "labels": [
                {"text": "glacial meltwater", "x": 600, "y": 470, "at": 2.6, "anchor": "middle", "accent": True},
                {"text": "volcanism", "x": 1300, "y": 950, "at": 4.6, "anchor": "middle", "accent": True},
            ],
        },
    },
    "act1_s039": {
        "_ledger": ["c03"],
        "type": "document_reveal",
        "props": {
            **ACT1,
            "sceneIndex": "S 039 / DATING",
            "kicker": "The dating",
            "headline": "Tiryns — Mycenaean phase",
            "lines": [
                {"text": "Tiryns peaked between 1400 and 1200 BC.", "at": 0.6},
                {"text": "The Cyclopean masonry is dated to Late Helladic IIIA,", "at": 1.9},
                {"text": "roughly 1,400 to 1,500 years before Pausanias wrote.", "at": 3.1, "emphasis": True},
            ],
            "source": "Ledger c03",
            "paper": "light",
            "light_sweep": True,
            "sweep_at": 3.8,
        },
    },
    "act1_s042": {
        "_ledger": ["c03"],
        "type": "timeline",
        "props": {
            **ACT1,
            "sceneIndex": "S 042 / THE SAME GAP, TWICE",
            "kicker": "The same distance",
            "title": "Tiryns to Pausanias, laid against the Vikings to us",
            "events": [
                {"year": -1400, "label": "Tiryns built", "at": 0.5},
                {"year": 170, "label": "Pausanias writes", "at": 1.7, "accent": True},
                {"year": 800, "label": "the Viking age begins", "at": 2.9},
                {"year": 2026, "label": "now", "at": 4.0, "accent": True},
            ],
            "span": [-1700, 2300],
            "caption": "Two gaps of about fourteen centuries, drawn to the same scale",
            "source": "Ledger c03",
        },
    },
    "act1_s045_ANNOT": None,  # placeholder, removed at merge
}
SLOTS.pop("act1_s045_ANNOT", None)
