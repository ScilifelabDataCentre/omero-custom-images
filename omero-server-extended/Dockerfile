FROM openmicroscopy/omero-server:5.6.16

USER root

RUN dnf config-manager --disable pgdg13 && \
    dnf -y install epel-release && \
    dnf -y install jq curl-minimal ca-certificates && \
    dnf -y remove webkit2gtk3-jsc && \
    dnf -y clean all && rm -rf /var/cache

RUN . /opt/omero/server/venv3/bin/activate && \
    pip install --no-cache-dir omero-metadata \
        "pillow>=13.0.0" "certifi>=2026.10.18" "urllib3>=2.8.0" \
        "msgpack>=1.2.3" "setuptools>=78.1.1,<81" && \
    pip check && \
    python -c "import pkg_resources, omego.main"


COPY scripts/  /opt/omero/server/OMERO.server-5.6.16-ice36/lib/scripts/omero/

# change the ownership of the scripts folder to omero-server
RUN chown -R omero-server:omero /opt/omero/server/OMERO.server-5.6.16-ice36/lib/scripts/omero/

USER omero-server

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]