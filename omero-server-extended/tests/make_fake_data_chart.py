"""Run the whole data chain on fake data and draw quota_fake_data.png (NOR-803, M3).

Builds, in a temporary folder that is deleted afterwards:
- a fake suprpy database (local_projects.db) with two rows for one group;
- a fake ManagedRepository/<group>/<userId>/ tree with real bytes in it.
The folder limit is faked at 1 GiB while suprpy says 2 GB, so the title
must show "quota change pending".

Run from omero-server-extended/:  python tests/make_fake_data_chart.py
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "scilifelab"))

import Quota_Usage as qu  # noqa: E402

MIB = 1024**2
LIMIT = 1 * qu.GIB  # what XFS enforces on the group folder (faked)


def write_file(path, size):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        for _ in range(size // MIB):
            f.write(os.urandom(MIB))


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)

    # 1. Fake suprpy database: an old deactivated row and the current row.
    db = tmp / "local_projects.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE projects (project_id INTEGER PRIMARY KEY, name TEXT,"
        " allocation_GB INTEGER, status TEXT, last_updated DATETIME,"
        " last_synchronized_storage_quota DATETIME)"
    )
    con.executemany(
        "INSERT INTO projects (project_id, name, allocation_GB, status, last_updated)"
        " VALUES (?, ?, ?, ?, ?)",
        [
            (6, "NOR Demo Lab", 5, "deactivated", "2026-11-04 09:00:00"),
            (7, "NOR Demo Lab", 2, "started", "2026-11-01 10:00:00"),
        ],
    )
    con.commit()
    con.close()

    # 2. Fake ManagedRepository/<group>/<userId>/... with real data.
    group = qu.group_dir_name("NOR Demo Lab")  # -> "nor_demo_lab"
    group_dir = tmp / "ManagedRepository" / group
    write_file(group_dir / "2" / "2026_10" / "a.tif", 300 * MIB)  # Alice
    write_file(group_dir / "3" / "2026_10" / "b.tif", 150 * MIB)  # Bo
    write_file(group_dir / "4" / "2026_11" / "c.tif", 5 * MIB)  # Cecilia: under 2%
    write_file(group_dir / "999" / "2025_03" / "d.tif", 60 * MIB)  # left the group
    write_file(group_dir / "import_logs" / "e.log", 40 * MIB)  # not a user folder

    # 3. Fake os.statvfs: on the real server XFS reports the group quota here.
    used = qu.folder_bytes(group_dir)

    def statvfs(_path):
        return SimpleNamespace(
            f_frsize=4096, f_blocks=LIMIT // 4096, f_bfree=(LIMIT - used) // 4096
        )

    # 4. The real chain, then the chart.
    members = {2: "Alice Andersson", 3: "Bo Berg", 4: "Cecilia Carlsson"}
    slices, title = qu.collect_quota(
        db, tmp / "ManagedRepository", group, members, statvfs=statvfs
    )

out = Path(__file__).resolve().parent / "quota_fake_data.png"
qu.render_pie_png(slices, title, out)
print(title)
for label, size in slices:
    print(f"  {label:<20} {size / MIB:8.0f} MiB")
print(f"Wrote {out}")
