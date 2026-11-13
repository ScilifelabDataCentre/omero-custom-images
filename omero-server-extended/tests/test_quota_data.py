"""Tests for the data chain in scripts/scilifelab/Quota_Usage.py (NOR-803).

Everything here runs on fake data: fixture snapshots in tests/fixtures/ shaped
like the projects.json the suprpy job exports, and a fake ManagedRepository
folder in pytest's tmp_path.
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import Quota_Usage as qu

GIB = 1024**3
MIB = 1024**2

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SNAPSHOT = FIXTURES / "projects.json"


def write_file(path, size):
    """Write size real bytes, so the disk really allocates blocks for them."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(os.urandom(size))


def fake_statvfs(limit, used, block=4096):
    """Return a stand-in for os.statvfs that reports an XFS-style quota."""
    return lambda _path: SimpleNamespace(
        f_frsize=block, f_blocks=limit // block, f_bfree=(limit - used) // block
    )


# ---------- group_dir_name: SUPR project name -> folder name ----------


def test_group_dir_name_matches_suprpy():
    # Same rule as suprpy/utils.py: lower case, spaces and slashes become "_".
    assert qu.group_dir_name("NOR Demo Lab/Imaging") == "nor_demo_lab_imaging"


# ---------- pick_project: which snapshot row belongs to the group ----------


def test_pick_project_prefers_a_row_that_is_not_deactivated():
    # "Lab A" has a newer deactivated row and an older started row.
    project = qu.pick_project(SNAPSHOT, "lab_a")
    assert project["allocation_gb"] == 100
    assert project["status"] == "started"


def test_pick_project_prefers_the_newest_active_row():
    # "Lab B" and "lab b" map to the same folder; the newer row wins.
    assert qu.pick_project(SNAPSHOT, "lab_b")["allocation_gb"] == 80


def test_pick_project_converts_spaces_and_slashes():
    project = qu.pick_project(SNAPSHOT, "omerotest_2024_10")
    assert project["name"] == "OMEROTEST 2024/10"


def test_pick_project_returns_none_when_no_row_matches():
    assert qu.pick_project(SNAPSHOT, "lab_z") is None


# ---------- quota_from_statvfs: limit and usage of the group folder ----------


def test_quota_from_statvfs_reads_limit_and_used():
    stat = SimpleNamespace(f_frsize=4096, f_blocks=1000, f_bfree=250)
    used, limit = qu.quota_from_statvfs(stat)
    assert limit == 1000 * 4096
    assert used == 750 * 4096


# ---------- folder_bytes: disk space a folder really takes ----------


def test_folder_bytes_counts_real_data(tmp_path):
    write_file(tmp_path / "a" / "image.tif", 1 * MIB)
    assert qu.folder_bytes(tmp_path / "a") >= 1 * MIB


def test_folder_bytes_counts_allocated_blocks_not_file_length(tmp_path):
    # A sparse file claims 100 MiB but takes almost no disk space.
    sparse = tmp_path / "a" / "sparse.bin"
    sparse.parent.mkdir()
    with open(sparse, "wb") as f:
        f.seek(100 * MIB)
        f.write(b"x")
    assert qu.folder_bytes(tmp_path / "a") < 1 * MIB


def test_folder_bytes_counts_a_hard_linked_file_once(tmp_path):
    write_file(tmp_path / "a" / "image.tif", 1 * MIB)
    os.link(tmp_path / "a" / "image.tif", tmp_path / "a" / "same_image.tif")
    assert qu.folder_bytes(tmp_path / "a") < 2 * MIB


def test_folder_bytes_does_not_follow_symlinks(tmp_path):
    write_file(tmp_path / "elsewhere" / "big.tif", 4 * MIB)
    (tmp_path / "a").mkdir()
    os.symlink(tmp_path / "elsewhere" / "big.tif", tmp_path / "a" / "link.tif")
    assert qu.folder_bytes(tmp_path / "a") < 1 * MIB


# ---------- member_usage: one entry per <userId> folder ----------


def test_member_usage_labels_members_and_former_users(tmp_path):
    group_dir = tmp_path / "lab_a"
    write_file(group_dir / "2" / "2026_10" / "x.tif", 64 * 1024)
    write_file(group_dir / "3" / "2026_10" / "y.tif", 64 * 1024)
    write_file(group_dir / "999" / "2026_01" / "z.tif", 64 * 1024)  # left the group
    write_file(group_dir / "import_logs" / "log.txt", 64 * 1024)  # not a user folder
    write_file(group_dir / "stray_file.txt", 64 * 1024)

    usage = qu.member_usage(group_dir, {2: "Alice", 3: "Bob"})

    assert set(usage) == {"Alice", "Bob", "Former user 999"}
    assert all(size > 0 for size in usage.values())


# ---------- build_slices: at most 8 member colours ----------


def test_at_most_8_member_slices_rest_go_into_others():
    # 10 members, all above 2%; only 8 colours exist, so the 2 smallest merge.
    members = {f"User {i}": (20 - i) * GIB for i in range(10)}  # 20, 19, ... 11 GiB
    total = sum(members.values())
    slices = qu.build_slices(members, total_used=total, limit=total)
    labels = [label for label, _ in slices]
    assert labels == [f"User {i}" for i in range(8)] + ["Others"]
    assert slices[-1] == ("Others", 12 * GIB + 11 * GIB)


# ---------- collect_quota: the whole chain, snapshot + folders -> chart input ----------


def test_collect_quota_runs_the_whole_chain(tmp_path):
    repo = tmp_path / "ManagedRepository"
    write_file(repo / "nor_demo_lab" / "2" / "a.tif", 1 * MIB)
    used = qu.folder_bytes(repo / "nor_demo_lab")

    slices, title = qu.collect_quota(
        SNAPSHOT, repo, "nor_demo_lab", {2: "Alice"}, statvfs=fake_statvfs(10 * MIB, used)
    )

    labels = [label for label, _ in slices]
    # Limit 10 MiB keeps Alice's 1 MiB above the 2% "Others" threshold.
    assert labels[0] == "Alice"
    assert labels[-1] == "Free"
    # suprpy says 2 GB, but the folder limit is only 10 MiB.
    assert "quota change pending" in title


def test_collect_quota_explains_a_missing_snapshot_row(tmp_path):
    (tmp_path / "ManagedRepository" / "lab_z").mkdir(parents=True)
    with pytest.raises(qu.QuotaError, match="No quota found for group 'lab_z'"):
        qu.collect_quota(SNAPSHOT, tmp_path / "ManagedRepository", "lab_z", {})


def test_collect_quota_explains_a_missing_group_folder(tmp_path):
    (tmp_path / "ManagedRepository").mkdir()
    with pytest.raises(qu.QuotaError, match="folder"):
        qu.collect_quota(SNAPSHOT, tmp_path / "ManagedRepository", "nor_demo_lab", {})


# ---------- member_labels: OMERO users -> pie chart labels ----------


def fake_user(user_id, full_name, username):
    """Stand-in for an OMERO ExperimenterWrapper: only the three getters we use."""
    return SimpleNamespace(
        getId=lambda: user_id, getFullName=lambda: full_name, getName=lambda: username
    )


def test_member_labels_uses_full_names():
    users = [fake_user(2, "Alice Andersson", "alice"), fake_user(3, "Bo Berg", "bo")]
    assert qu.member_labels(users) == {2: "Alice Andersson", 3: "Bo Berg"}


def test_member_labels_adds_username_when_full_names_clash():
    # Two people with the same name must stay two slices, not merge into one.
    users = [fake_user(2, "Anna Svensson", "anna1"), fake_user(3, "Anna Svensson", "anna2")]
    assert qu.member_labels(users) == {2: "Anna Svensson (anna1)", 3: "Anna Svensson (anna2)"}


def test_member_labels_falls_back_to_username_without_full_name():
    assert qu.member_labels([fake_user(2, " ", "alice")]) == {2: "alice"}


# ---------- collect_quota: a snapshot that cannot be used gives a clear message ----------


def test_collect_quota_explains_a_missing_snapshot(tmp_path):
    # E.g. the suprpy job has not run yet: say so instead of a traceback.
    (tmp_path / "ManagedRepository" / "nor_demo_lab").mkdir(parents=True)
    with pytest.raises(qu.QuotaError, match="Cannot read the quota snapshot"):
        qu.collect_quota(
            tmp_path / "missing.json", tmp_path / "ManagedRepository", "nor_demo_lab", {}
        )


def test_collect_quota_explains_a_snapshot_that_is_not_json(tmp_path):
    # E.g. a file cut off half-way.
    snapshot = tmp_path / "projects.json"
    snapshot.write_text('{"exported_at": "2026-11-12T13:00:05+00:00", "projects": [')
    (tmp_path / "ManagedRepository" / "nor_demo_lab").mkdir(parents=True)
    with pytest.raises(qu.QuotaError, match="Cannot read the quota snapshot"):
        qu.collect_quota(snapshot, tmp_path / "ManagedRepository", "nor_demo_lab", {})


def test_collect_quota_explains_a_snapshot_with_the_wrong_shape(tmp_path):
    (tmp_path / "ManagedRepository" / "nor_demo_lab").mkdir(parents=True)
    with pytest.raises(qu.QuotaError, match="Cannot read the quota snapshot"):
        qu.collect_quota(
            FIXTURES / "projects_bad_shape.json",
            tmp_path / "ManagedRepository",
            "nor_demo_lab",
            {},
        )
