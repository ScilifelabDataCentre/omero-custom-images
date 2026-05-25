# OMERO Custom Images

Custom Docker images for the SciLifeLab OMERO.

## Images

| Image | Base | Purpose |
|---|---|---|
| [`omero-server-extended`](omero-server-extended/) | `openmicroscopy/omero-server:5.6.16` | OMERO server with extra scripts and tooling |
| [`omero-nfs-export`](omero-nfs-export/) | `rockylinux/rockylinux:10.1` | Lightweight NFS-utils sidecar |

## Quick start

Pull a prebuilt image:

```bash
docker pull ghcr.io/scilifelabdatacentre/omero-server-extended:latest
docker pull ghcr.io/scilifelabdatacentre/omero-nfs-export:latest
```

Build locally:

```bash
docker build -t omero-server-extended omero-server-extended/
docker build -t omero-nfs-export omero-nfs-export/
```

## CI/CD

Each image has its own GitHub Actions workflow:

- **omero-server-extended** -- built automatically on push to `main`, version tags, and pull requests.
- **omero-nfs-export** -- built on manual dispatch (`workflow_dispatch`).

See [`omero-server-extended/README.md`](omero-server-extended/README.md).
See [`omero-nfs-export/README.md`](omero-nfs-export/README.md).