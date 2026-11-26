"""Tests for the pure functions in scripts/scilifelab/Quota_Usage.py (NOR-803)."""

import pytest
from PIL import Image

import Quota_Usage as qu

GIB = 1024**3


# ---------- build_slices: which slices the pie chart gets ----------


def test_one_slice_per_member_largest_first_then_free():
    slices = qu.build_slices(
        {"Alice": 20 * GIB, "Bob": 30 * GIB}, total_used=50 * GIB, limit=100 * GIB
    )
    assert slices == [("Bob", 30 * GIB), ("Alice", 20 * GIB), ("Free", 50 * GIB)]


def test_members_under_2_percent_are_merged_into_others():
    # 1 GiB of a 100 GiB pie is 1%, below the 2% threshold.
    slices = qu.build_slices(
        {"Alice": 40 * GIB, "Bob": 1 * GIB, "Carol": 1 * GIB},
        total_used=42 * GIB,
        limit=100 * GIB,
    )
    assert slices == [("Alice", 40 * GIB), ("Others", 2 * GIB), ("Free", 58 * GIB)]


def test_usage_outside_member_folders_becomes_other():
    slices = qu.build_slices({"Alice": 30 * GIB}, total_used=35 * GIB, limit=100 * GIB)
    assert slices == [("Alice", 30 * GIB), ("Other", 5 * GIB), ("Free", 65 * GIB)]


def test_no_free_slice_when_quota_is_full():
    slices = qu.build_slices({"Alice": 100 * GIB}, total_used=100 * GIB, limit=100 * GIB)
    assert slices == [("Alice", 100 * GIB)]


def test_member_with_no_data_gets_no_slice():
    slices = qu.build_slices({"Alice": 10 * GIB, "Bob": 0}, total_used=10 * GIB, limit=10 * GIB)
    assert slices == [("Alice", 10 * GIB)]


def test_member_slices_plus_other_add_up_to_total_used():
    # Jira acceptance criterion: per-member slices plus "Other" equal the total used.
    slices = qu.build_slices(
        {"A": 10 * GIB, "B": 1 * GIB, "C": 3 * GIB}, total_used=20 * GIB, limit=50 * GIB
    )
    assert sum(size for label, size in slices if label != "Free") == 20 * GIB


# ---------- build_title: the line above the chart ----------


def test_title_shows_used_total_and_percent():
    title = qu.build_title(used=25 * GIB, limit=100 * GIB, status="started", allocation_gb=100)
    assert title == "25.0 of 100.0 GiB used (25%)"


@pytest.mark.parametrize("status", ["ended", "deactivated"])
def test_title_flags_ended_or_deactivated_project(status):
    title = qu.build_title(used=25 * GIB, limit=100 * GIB, status=status, allocation_gb=100)
    assert f"project {status}" in title


def test_title_flags_pending_quota_change():
    # suprpy has stored 50 GB, but XFS still enforces 100 GiB.
    title = qu.build_title(used=25 * GIB, limit=100 * GIB, status="started", allocation_gb=50)
    assert "quota change pending" in title


def test_title_flags_usage_at_90_percent():
    title = qu.build_title(used=90 * GIB, limit=100 * GIB, status="started", allocation_gb=100)
    assert "nearly full" in title


def test_title_has_no_nearly_full_flag_below_90_percent():
    title = qu.build_title(used=89 * GIB, limit=100 * GIB, status="started", allocation_gb=100)
    assert "nearly full" not in title


# ---------- render_pie_png: the picture ----------


def test_render_writes_a_png(tmp_path):
    out = tmp_path / "quota.png"
    qu.render_pie_png(
        [("Alice", 30 * GIB), ("Free", 70 * GIB)], "30.0 of 100.0 GiB used (30%)", out
    )
    with Image.open(out) as img:
        assert img.format == "PNG"
        assert img.width >= 600 and img.height >= 400


def test_render_handles_a_single_full_slice(tmp_path):
    out = tmp_path / "quota.png"
    qu.render_pie_png([("Free", 100 * GIB)], "0.0 of 100.0 GiB used (0%)", out)
    assert out.exists()
