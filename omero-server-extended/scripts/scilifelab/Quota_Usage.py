"""Show the current group's storage quota usage per member as a pie chart (NOR-803).

This file has three layers:
- the data chain (pick_project, folder_bytes, member_usage, collect_quota) that
  reads the suprpy database and the group folder;
- pure chart functions (build_slices, build_title, render_pie_png);
- the OMERO script shell, added later, which imports omero only when run
  inside OMERO.
Everything except the shell is tested locally with pytest and needs only Pillow.
"""

import os
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GIB = 1024**3
SMALL_SLICE_FRACTION = 0.02  # member slices below 2% of the pie go into "Others"
NEARLY_FULL_PERCENT = 90
INACTIVE_STATUSES = ("ended", "deactivated")

# Where the omeroserver pod sees the data (set in ddls-k8s-gitops).
DB_PATH = "/data/local_projects/local_projects.db"  # suprpy database, mounted read-only
REPO_ROOT = "/OMERO/ManagedRepository"  # one folder per group, XFS project quota on each
CHART_NAMESPACE = "se.scilifelab.omero.quota"

# Colours: validated categorical palette (light mode) for members,
# two neutral greys for the non-member slices.
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
MEMBER_COLOURS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#6250d6",  # violet
    "#e34948",  # red
]
NEUTRAL_COLOURS = {"Others": "#8f8d87", "Other": "#b5b3ad", "Free": "#e4e3df"}


class QuotaError(Exception):
    """A problem the user should read about, e.g. no quota row for this group."""


# ---------- data chain: database + group folder -> chart input ----------


def group_dir_name(project_name):
    """SUPR project name -> group folder name; same rule as suprpy/utils.py."""
    return project_name.lower().replace(" ", "_").replace("/", "_")


def pick_project(db_path, group_name, timeout=5):
    """Return {name, status, allocation_gb} of the group's row in suprpy's database, or None.

    Opens the database read-only, so a wrong path fails instead of creating a file.
    If several rows map to the group, prefer rows that are not deactivated, then
    the most recently updated one.
    """
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=timeout)
    try:
        rows = con.execute(
            "SELECT name, status, allocation_GB, last_updated FROM projects"
        ).fetchall()
    finally:
        con.close()

    matches = [row for row in rows if row[0] and group_dir_name(row[0]) == group_name]
    if not matches:
        return None
    name, status, allocation_gb, _ = max(
        matches, key=lambda row: (row[1] != "deactivated", row[3] or "")
    )
    return {"name": name, "status": status, "allocation_gb": allocation_gb}


def quota_from_statvfs(stat):
    """Return (used, limit) in bytes. On an XFS project-quota folder these are the quota."""
    limit = stat.f_blocks * stat.f_frsize
    used = (stat.f_blocks - stat.f_bfree) * stat.f_frsize
    return used, limit


def folder_bytes(path):
    """Disk space really allocated under path (like `du`): st_blocks, not file length.

    Symlinks are not followed and a hard-linked file is counted once,
    which is also how XFS quota counts.
    """
    seen = set()
    total = 0
    paths = [path]
    for root, dirs, files in os.walk(path):  # os.walk does not enter symlinked folders
        paths.extend(os.path.join(root, name) for name in dirs + files)
    for item in paths:
        try:
            st = os.lstat(item)
        except OSError:  # removed or unreadable while we were counting
            continue
        key = (st.st_dev, st.st_ino)
        if key not in seen:
            seen.add(key)
            total += st.st_blocks * 512
    return total


def member_usage(group_dir, members):
    """Return {label: bytes} for each <userId> folder in group_dir.

    members: {user_id: label} for current group members. A user folder whose id
    is not in members is labelled "Former user <id>". Other folders and files are
    left out here; build_slices shows them as "Other".
    """
    usage = {}
    for entry in os.scandir(group_dir):
        name = entry.name
        if entry.is_dir(follow_symlinks=False) and name.isascii() and name.isdigit():
            user_id = int(name)
            label = members.get(user_id, f"Former user {user_id}")
            usage[label] = usage.get(label, 0) + folder_bytes(entry.path)
    return usage


def member_labels(users):
    """Return {user_id: label} for OMERO users (ExperimenterWrapper-like objects).

    The label is the full name; if two members share a full name, the username
    is added so they stay two separate slices.
    """
    names = {}
    for user in users:
        full_name = (user.getFullName() or "").strip()
        names[user.getId()] = (full_name or user.getName(), user.getName())
    counts = {}
    for full_name, _ in names.values():
        counts[full_name] = counts.get(full_name, 0) + 1
    return {
        user_id: f"{full_name} ({username})" if counts[full_name] > 1 else full_name
        for user_id, (full_name, username) in names.items()
    }


def collect_quota(db_path, repo_root, group_name, members, statvfs=os.statvfs):
    """Return (slices, title) for one group, or raise QuotaError with a clear message."""
    try:
        project = pick_project(db_path, group_name)
    except sqlite3.Error as exc:
        raise QuotaError(f"Cannot read the project database {db_path}: {exc}") from exc
    if project is None:
        raise QuotaError(f"No quota found for group '{group_name}' in the project database.")
    group_dir = Path(repo_root) / group_name
    if not group_dir.is_dir():
        raise QuotaError(f"The data folder for group '{group_name}' does not exist: {group_dir}")

    used, limit = quota_from_statvfs(statvfs(str(group_dir)))
    slices = build_slices(member_usage(group_dir, members), used, limit)
    title = build_title(used, limit, project["status"], project["allocation_gb"] or 0)
    return slices, title


# ---------- chart ----------


def build_slices(member_bytes, total_used, limit):
    """Return [(label, bytes), ...]: members largest first, then Others, Other, Free.

    member_bytes: {label: bytes on disk in that member's folder}
    total_used:   bytes used by the whole group folder (what XFS counts)
    limit:        bytes the group may use (the XFS hard limit)
    """
    member_sum = sum(member_bytes.values())
    other = total_used - member_sum  # usage outside the member folders
    free = limit - total_used
    pie_total = max(total_used, member_sum) + max(free, 0)
    threshold = SMALL_SLICE_FRACTION * pie_total

    slices = []
    others = 0
    for label, size in sorted(member_bytes.items(), key=lambda item: item[1], reverse=True):
        if size <= 0:
            continue
        # Only 8 member colours exist, so members beyond the 8th also merge.
        if size < threshold or len(slices) >= len(MEMBER_COLOURS):
            others += size
        else:
            slices.append((label, size))
    if others > 0:
        slices.append(("Others", others))
    if other > 0:
        slices.append(("Other", other))
    if free > 0:
        slices.append(("Free", free))
    return slices


def build_title(used, limit, status, allocation_gb):
    """Return e.g. '25.0 of 100.0 GiB used (25%) [quota change pending]'."""
    percent = 100 * used / limit if limit > 0 else 0
    title = f"{used / GIB:.1f} of {limit / GIB:.1f} GiB used ({percent:.0f}%)"

    flags = []
    if status in INACTIVE_STATUSES:
        flags.append(f"project {status}")
    if allocation_gb * GIB != limit:
        flags.append("quota change pending")
    # Integer arithmetic, so 90 GiB of 100 GiB is exactly 90%.
    if limit > 0 and used * 100 >= NEARLY_FULL_PERCENT * limit:
        flags.append("nearly full")
    if flags:
        title += " [" + ", ".join(flags) + "]"
    return title


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow older than 10.1 has no sized default font
        return ImageFont.load_default()


def _slice_colour(label, member_index):
    if label in NEUTRAL_COLOURS:
        return NEUTRAL_COLOURS[label]
    return MEMBER_COLOURS[member_index % len(MEMBER_COLOURS)]


def render_pie_png(slices, title, path):
    """Draw the pie chart with a legend and save it as a PNG at path."""
    width, height = 1000, 560
    image = Image.new("RGB", (width, height), SURFACE)
    draw = ImageDraw.Draw(image)
    draw.text((40, 28), title, fill=TEXT_PRIMARY, font=_font(22))

    total = sum(size for _, size in slices)
    pie_box = (40, 100, 460, 520)
    legend_font = _font(18)
    start = -90.0  # start at 12 o'clock, go clockwise
    member_index = 0
    for row, (label, size) in enumerate(slices):
        colour = _slice_colour(label, member_index)
        if label not in NEUTRAL_COLOURS:
            member_index += 1

        if total > 0:
            end = start + 360.0 * size / total
            # The surface-coloured outline leaves a thin gap between slices.
            draw.pieslice(pie_box, start, end, fill=colour, outline=SURFACE, width=2)
            start = end

        y = 120 + row * 34
        draw.rounded_rectangle((520, y, 540, y + 20), radius=4, fill=colour)
        share = 100 * size / total if total > 0 else 0
        draw.text((552, y), label, fill=TEXT_PRIMARY, font=legend_font)
        draw.text(
            (790, y), f"{size / GIB:.1f} GiB ({share:.0f}%)", fill=TEXT_SECONDARY, font=legend_font
        )

    image.save(path, format="PNG")


# ---------- OMERO script shell (runs only inside OMERO) ----------


def make_chart(conn):
    """Draw the chart for the user's current group; return (message, file_annotation)."""
    import tempfile

    group = conn.getGroupFromContext()
    owners, members = group.groupSummary()
    group_name = group.getName()
    slices, title = collect_quota(
        DB_PATH, REPO_ROOT, group_name, member_labels(list(owners) + list(members))
    )

    # Keep one chart per user and group: remove the user's earlier charts first.
    old = conn.getObjects(
        "FileAnnotation", attributes={"ns": CHART_NAMESPACE}, opts={"owner": conn.getUserId()}
    )
    old_ids = [ann.getId() for ann in old]
    if old_ids:
        conn.deleteObjects("Annotation", old_ids, wait=True)

    with tempfile.TemporaryDirectory() as tmp:
        png = os.path.join(tmp, f"quota_{group_name}.png")
        render_pie_png(slices, f"{group_name}: {title}", png)
        file_ann = conn.createFileAnnfromLocalFile(
            png, mimetype="image/png", ns=CHART_NAMESPACE, desc=title
        )
    return f"{group_name}: {title}", file_ann


def run_script():
    """Entry point when OMERO runs the script."""
    import omero.scripts as scripts
    from omero.gateway import BlitzGateway
    from omero.rtypes import robject, rstring

    client = scripts.client(
        "Quota_Usage.py",
        """Show how much of your current group's storage quota is used, per member.

The pie chart covers the group you have selected in OMERO.web. To see another
group, switch group first and run the script again.""",
        version="0.1.0",
        authors=["Team Berserkers"],
        institutions=["SciLifeLab Data Centre"],
        contact="https://github.com/ScilifelabDataCentre/omero-custom-images",
    )
    try:
        conn = BlitzGateway(client_obj=client)
        try:
            message, file_ann = make_chart(conn)
        except QuotaError as exc:
            client.setOutput("Message", rstring(str(exc)))
        else:
            client.setOutput("Message", rstring(message))
            client.setOutput("File_Annotation", robject(file_ann._obj))
    finally:
        client.closeSession()


if __name__ == "__main__":
    run_script()
