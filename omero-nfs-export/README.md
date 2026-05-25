## OMERO NFS Export

Lightweight sidecar container with NFS utilities, intended for exporting or mounting NFS shares alongside OMERO deployments. Based on Rocky Linux 10.1.

### What's included

- **Base image:** `rockylinux/rockylinux:10.1`
- **Installed packages:**
  - `nfs-utils` -- NFS client/server tools (`mount.nfs`, `exportfs`, etc.)
  - `procps-ng` -- process utilities (`ps`, `top`, etc.)

### Image

Prebuilt image:

```bash
docker pull ghcr.io/scilifelabdatacentre/omero-nfs-export:latest
```


