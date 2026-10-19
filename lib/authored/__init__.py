"""Authored scene props for the narrated-documentary run.

Split by act so each file stays readable. Every figure here is bound to a
`data_points` entry in research_brief.json by its ledger id (c01..c43); the
`_ledger` key on a slot records which. Nothing may state a date, name or figure
that has no ledger entry — that rule governs the graphics exactly as it governs
the script.
"""
from .act_cold_open_1 import SLOTS as _A
from .act_2_3 import SLOTS as _B
from .act_4_outro import SLOTS as _C
from .textures import SLOTS as _D
from .process_shots import SLOTS as _E

SLOTS = {**_A, **_B, **_C, **_D, **_E}

_dupes = [k for k in _D if k in {**_A, **_B, **_C}] + [k for k in _E if k in {**_A, **_B, **_C, **_D}]
if _dupes:
    raise AssertionError(f"authored slot defined twice: {_dupes}")
