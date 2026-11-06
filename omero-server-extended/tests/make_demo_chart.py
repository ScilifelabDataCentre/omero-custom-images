"""Draw quota_demo.png from made-up numbers, to look at the chart locally.

Run from omero-server-extended/:  python tests/make_demo_chart.py
"""

import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "scilifelab"))

import Quota_Usage as qu  # noqa: E402

GIB = qu.GIB
members = {
    "Alice Andersson": 31 * GIB,
    "Bo Berg": 18 * GIB,
    "Cecilia Carlsson": 9 * GIB,
    "Former user 42": 4 * GIB,
    "Dan Dahl": 1 * GIB,  # under 2%: goes into "Others"
}
total_used, limit = 66 * GIB, 100 * GIB

slices = qu.build_slices(members, total_used, limit)
title = qu.build_title(total_used, limit, status="started", allocation_gb=100)
out = Path(__file__).resolve().parent / "quota_demo.png"
qu.render_pie_png(slices, title, out)
print(f"Wrote {out}")
