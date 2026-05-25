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

Each image has its own GitHub Actions workflow, triggered manually via `workflow_dispatch` from the GitHub Actions UI or CLI. When triggered, you provide a version tag (e.g. `v1.0.0`) and the workflow builds, pushes, scans (Trivy), and signs (cosign) the image.

- **omero-server-extended** -- [`build-omero-server-image.yml`](.github/workflows/build-omero-server-image.yml)
- **omero-nfs-export** -- [`build-omero-nfs-export-image.yml`](.github/workflows/build-omero-nfs-export-image.yml)

See [`omero-server-extended/README.md`](omero-server-extended/README.md).
See [`omero-nfs-export/README.md`](omero-nfs-export/README.md).

## Contact

The SciLifeLab OMERO prototype is being developed by the SciLifeLab Data Centre. This service is supported by SciLifeLab and the Knut and Alice Wallenberg foundation through the Data-Driven Life Science (DDLS) program, as well as by the Swedish Foundation for Strategic Research (SSF).

Please contact the development team for SciLifeLab OMERO with any questions at *omero@scilifelab.se*.