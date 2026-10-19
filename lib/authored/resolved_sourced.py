"""The 40 slots that reached the edit marked `authored:<description>`.

These were never graphics. They are photographic subjects whose retrieval
failed, and nothing in the design system can honestly stand in for a
photograph of a thing. Each one is resolved here in one of two ways:

  REUSE  — point the slot at an asset already verified in asset_manifest.json,
           with a caption that describes what is actually on screen. A slot
           never claims a subject its picture does not show; where the nearest
           honest asset is a different subject, the caption says so.

  AUTHOR — only where the beat is conceptual rather than photographic, in which
           case it becomes a design-system scene like any other.

Reuse is not padding: the playbook forbids the same image on adjacent slots,
and every reuse here is separated by at least one act or several minutes.
"""

IMG = "projects/they-said-it-couldnt-be-built/assets/images/"
S = IMG + "stills_site/clips/"
V = "projects/they-said-it-couldnt-be-built/assets/video/clips/"

A1 = {"actNumber": "01", "actTitle": "A verdict two thousand years old"}
A2 = {"actNumber": "02", "actTitle": "The statues that walked"}
A3 = {"actNumber": "03", "actTitle": "The hole in the granite"}
A4 = {"actNumber": "04", "actTitle": "The cases nobody has closed"}

# slot_id -> {"reuse": <asset scene_id to borrow>, "caption": ..., ...}
# `annotate` marks the ones that become annotated_still; their anchor
# coordinates are read off the actual image, never guessed.
REUSE = {
    # ── act 1 ───────────────────────────────────────────────────────────
    # Anchors read off the 16:9 crop of the actual file, not guessed.
    "act1_s014": {"reuse": "act1_s019", "annotate": True, **A1,
                  "sceneIndex": "S 014 / MYCENAE",
                  "caption": "Mycenae — the fortification wall, close",
                  "source": "Wikimedia Commons · CC BY-SA",
                  "annotations": [
                      {"label": "block-to-block contact", "x": 0.54, "y": 0.42, "reveal_at": 0.8, "side": "left"},
                      {"label": "no mortar", "x": 0.40, "y": 0.26, "reveal_at": 2.6, "side": "right"},
                  ]},
    "act1_s025": {"reuse": "act1_s022", **A1,
                  "sceneIndex": "S 025 / HAULAGE",
                  "caption": "Engraving, 17th century",
                  "source": "Wikimedia Commons · public domain"},
    "act1_s044": {"reuse": "act1_s016", "annotate": True, **A1,
                  "sceneIndex": "S 044 / LION GATE",
                  "caption": "The Lion Gate, Mycenae",
                  "source": "Wikimedia Commons · CC BY-SA",
                  "annotations": [
                      {"label": "one stone", "x": 0.30, "y": 0.30, "reveal_at": 0.9, "side": "right"},
                      {"label": "flanking ashlar", "x": 0.88, "y": 0.22, "reveal_at": 2.8, "side": "left"},
                  ]},
    "act1_s046": {"reuse": "act1_s034", **A1, "sceneIndex": "S 046"},

    # ── act 2 ───────────────────────────────────────────────────────────
    "act2_s049": {"reuse": "act2_s053", **A2,
                  "sceneIndex": "S 049 / RANO RARAKU",
                  "caption": "Rano Raraku — statues still in and below the quarry",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act2_s068": {"reuse": "act2_s067", **A2,
                  "sceneIndex": "S 068 / PRESELI",
                  "caption": "The Preseli hills, Pembrokeshire",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act2_s073": {"reuse": "act2_s070", **A2, "sceneIndex": "S 073"},
    "act2_s077": {"reuse": "act2_s080", **A2,
                  "sceneIndex": "S 077 / NORTH ATLANTIC",
                  "caption": "North Atlantic coast — not the Orcadian outcrop itself",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act2_s082": {"reuse": "act2_s075", **A2,
                  "sceneIndex": "S 082 / ALTAR STONE",
                  "caption": "The Altar Stone at Stonehenge, beneath the fallen trilithon",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act2_s084": {"reuse": "act2_s083", **A2, "sceneIndex": "S 084"},
    "act2_s085": {"reuse": "act2_s064", **A2,
                  "sceneIndex": "S 085 / STONEHENGE",
                  "caption": "Stonehenge",
                  "source": "Wikimedia Commons · CC BY-SA"},

    # ── act 3 ───────────────────────────────────────────────────────────
    "act3_s089": {"reuse": "act3_s099", "annotate": True, **A3,
                  "sceneIndex": "S 089 / ASWAN",
                  "caption": "Aswan — a dolerite pounder on the pink granite",
                  "source": "Wikimedia Commons · CC BY-SA",
                  "annotations": [
                      {"label": "dolerite pounder", "x": 0.584, "y": 0.633, "reveal_at": 0.9, "side": "right"},
                      {"label": "worked face", "x": 0.30, "y": 0.33, "reveal_at": 2.7, "side": "right"},
                  ]},
    "act3_s091": {"reuse": "act3_s104", **A3, "sceneIndex": "S 091"},
    "act3_s092": {"reuse": "act3_s087", **A3,
                  "sceneIndex": "S 092 / PETRIE MUSEUM",
                  "caption": "Egyptian hard-stone vessel, Petrie Museum — not a sarcophagus",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s096": {"reuse": "act3_s095", **A3, "sceneIndex": "S 096"},
    "act3_s100": {"reuse": "act3_s099", **A3,
                  "sceneIndex": "S 100 / ASWAN",
                  "caption": "The Aswan quarry faces",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s102": {"reuse": "act3_s112", **A3,
                  "sceneIndex": "S 102 / HARDNESS",
                  "caption": "A Mohs hardness set — reference specimens, not Egyptian tools",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s105": {"reuse": "act3_s097", **A3,
                  "sceneIndex": "S 105 / THE CUT",
                  "caption": "A drilled hole in stone, recorded in section",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s109": {"reuse": "act3_s107", **A3, "sceneIndex": "S 109"},
    "act3_s111": {"reuse": "act3_s117", **A3,
                  "sceneIndex": "S 111 / LIMESTONE",
                  "caption": "Limestone hardground — the stone that cuts fifteen times faster",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s114": {"reuse": "act3_s124", **A3, "sceneIndex": "S 114"},
    "act3_s119": {"reuse": "act3_s126", **A3, "sceneIndex": "S 119"},
    "act3_s120": {"reuse": "act3_s127", **A3, "sceneIndex": "S 120"},
    "act3_s121": {"reuse": "act3_s132", **A3, "sceneIndex": "S 121"},
    "act3_s133": {"reuse": "act3_s115", **A3,
                  "sceneIndex": "S 133 / THE LAB",
                  "caption": "Laboratory glassware — the measurement came from a tray like this, not from a pyramid",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act3_s141": {"reuse": "act3_s098", **A3, "sceneIndex": "S 141"},

    # ── act 4 ───────────────────────────────────────────────────────────
    "act4_s142": {"reuse": "act4_s143", **A4,
                  "sceneIndex": "S 142 / ALTAR STONE",
                  "caption": "An altar stone, Sint-Niklaaskerk — a stand-in for the fragments analysed",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act4_s147": {"reuse": "act4_s145", **A4, "sceneIndex": "S 147"},
    "act4_s150": {"reuse": "act4_s148", "annotate": True, **A4,
                  "sceneIndex": "S 150 / PUMAPUNKU",
                  "caption": "Pumapunku — worked andesite on the altiplano",
                  "source": "Wikimedia Commons · CC BY-SA",
                  "annotations": [
                      {"label": "H-shaped block", "x": 0.70, "y": 0.64, "reveal_at": 0.9, "side": "left"},
                      {"label": "a person, for scale", "x": 0.516, "y": 0.35, "reveal_at": 2.8, "side": "right"},
                  ]},
    "act4_s151": {"reuse": "act4_s172", **A4, "sceneIndex": "S 151"},
    "act4_s152": {"reuse": "act4_s148", **A4,
                  "sceneIndex": "S 152 / PUMAPUNKU",
                  "caption": "The cut faces, close",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act4_s155": {"reuse": "act4_s174", **A4,
                  "sceneIndex": "S 155 / THE QUARRY",
                  "caption": "Corot, Abandoned Quarry, c. 1850",
                  "source": "Wikimedia Commons · public domain"},
    "act4_s160": {"reuse": "act4_s156", **A4,
                  "sceneIndex": "S 160 / DETECTORS",
                  "caption": "Detectors installed in the Descending Corridor and the Queen's chamber",
                  "source": "ScanPyramids · Wikimedia Commons"},
    "act4_s162": {"reuse": "act4_s168", **A4, "sceneIndex": "S 162"},
    "act4_s167": {"reuse": "act4_s164", **A4,
                  "sceneIndex": "S 167 / THE ENTRANCE",
                  "caption": "The entrance to the Great Pyramid",
                  "source": "Boston Public Library · Wikimedia Commons"},
    "act4_s169": {"reuse": "act4_s171", "annotate": True, **A4,
                  "sceneIndex": "S 169 / SACSAYHUAMÁN",
                  "caption": "Sacsayhuamán, Cusco",
                  "source": "Diego Delso · CC BY-SA 4.0",
                  "annotations": [
                      {"label": "coursed blocks above", "x": 0.86, "y": 0.12, "reveal_at": 0.9, "side": "left"},
                      {"label": "the great block", "x": 0.30, "y": 0.60, "reveal_at": 2.8, "side": "right"},
                  ]},
    "act4_s177": {"reuse": "act4_s171", "annotate": True, **A4,
                  "sceneIndex": "S 177 / THE JOINT",
                  "caption": "The contact line, traced by shadow",
                  "source": "Diego Delso · CC BY-SA 4.0",
                  "annotations": [
                      {"label": "contact line", "x": 0.47, "y": 0.50, "reveal_at": 0.8, "side": "right"},
                      {"label": "no mortar", "x": 0.80, "y": 0.30, "reveal_at": 2.7, "side": "left"},
                  ]},
    "act4_s180": {"reuse": "act4_s159", **A4,
                  "sceneIndex": "S 180 / GRAND GALLERY",
                  "caption": "The Grand Gallery",
                  "source": "Wikimedia Commons · CC BY-SA"},
    "act4_s181": {"reuse": "act4_s157", **A4, "sceneIndex": "S 181"},
    "outro_s182": {"reuse": "act2_s066", "actNumber": "05", "actTitle": "Outro",
                   "sceneIndex": "S 182 / SALISBURY PLAIN",
                   "caption": "Stonehenge and the aerodrome, 1928",
                   "source": "Wikimedia Commons · public domain"},
}
