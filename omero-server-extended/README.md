## OMERO Server Extended

Custom OMERO.server image based on the official `openmicroscopy/omero-server:5.6.16` that bundles extra OMERO scripts and useful tooling. The image:

- Installs `jq`, `curl-minimal`, and CA certificates for scripting inside the container
- Installs the Python package `omero-metadata` in the OMERO server venv
- Copies all scripts from `scripts/` into `OMERO.server/lib/scripts/omero/` so they are available in OMERO clients (OMERO.web/Insight).

### What’s in this repo

- `Dockerfile`: Builds on top of the official OMERO server image, adds packages and Python deps, and copies scripts into the server
- `scripts/`: Collection of OMERO scripts grouped by purpose
  - `analysis_scripts/`
  - `annotation_scripts/`
  - `export_scripts/`
  - `figure_scripts/`
  - `import_scripts/`
  - `util_scripts/`

**NOTE**: The core scripts are available in OMERO clients under the `omero-scripts` [git repository](https://github.com/ome/omero-scripts/tree/develop) except `Figure_To_Pdf.py` which is available in the `omero-figure` [git repository](https://github.com/ome/omero-figure/tree/master/omero_figure/scripts/omero/figure_scripts).

### Requirements

- Docker 20.10+ (or compatible)
- A running PostgreSQL instance accessible by the OMERO server (or use your existing DB setup; see the base image docs for environment variables)

### Image

Prebuilt image:

```bash
docker pull ghcr.io/scilifelabdatacentre/omero-server-extended:latest
```

### Run (basic example)

Expose OMERO ports and configure DB connection via environment variables understood by the base image:

```bash
docker run -d --name omero-server \
  -p 4063:4063 -p 4064:4064 \
  -e OMERO_DB_HOST=postgres \
  -e OMERO_DB_NAME=omero \
  -e OMERO_DB_USER=omero \
  -e OMERO_DB_PASS=omero \
  -e OMERO_ROOT_PASSWORD=change-me \
  ghcr.io/scilifelabdatacentre/omero-server-extended:latest
```

- To iterate on scripts without rebuilding the image, you can bind-mount your local `scripts/` into the container:

```bash
docker run -d --name omero-dev \
  -p 4063:4063 -p 4064:4064 \
  -v "$(pwd)/scripts:/opt/omero/server/OMERO.server/lib/scripts/omero:ro" \
  -e OMERO_DB_HOST=postgres -e OMERO_DB_NAME=omero -e OMERO_DB_USER=omero -e OMERO_DB_PASS=omero \
  -e OMERO_ROOT_PASSWORD=change-me \
  ghcr.io/scilifelabdatacentre/omero-server-extended:latest
```

- To add Python dependencies for the scripts, update the `Dockerfile` to `pip install` them inside `/opt/omero/server/venv3`
- To update the OMERO base version, change the tag on the `FROM openmicroscopy/omero-server:<tag>` line

### Kubernetes (manifests example)

Below is a minimal example showing how to deploy this image on Kubernetes. 


Deployment and Service:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: omero-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: omero-server
  template:
    metadata:
      labels:
        app: omero-server
    spec:
      containers:
        - name: omero-server
          image: ghcr.io/scilifelabdatacentre/omero-server-extended:latest
          imagePullPolicy: IfNotPresent
# the rest of the manifest...
```
