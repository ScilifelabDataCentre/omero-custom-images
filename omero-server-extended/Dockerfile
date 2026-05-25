FROM openmicroscopy/omero-server:5.6.16

USER root

RUN dnf -y install epel-release && \
    dnf -y install jq curl-minimal ca-certificates && \
    dnf -y clean all && rm -rf /var/cache

RUN . /opt/omero/server/venv3/bin/activate && \
    pip install --no-cache-dir omero-metadata

COPY scripts/  /opt/omero/server/OMERO.server-5.6.16-ice36/lib/scripts/omero/

# change the ownership of the scripts folder to omero-server
RUN chown -R omero-server:omero /opt/omero/server/OMERO.server-5.6.16-ice36/lib/scripts/omero/

USER omero-server

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]