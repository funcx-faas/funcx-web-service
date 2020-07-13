FROM funcx-web-base
WORKDIR /data
RUN apk add netcat-openbsd bash
RUN pip install jupyter

# Add Tini. Tini operates as a process subreaper for jupyter. This prevents
# kernel crashes.
ENV TINI_VERSION v0.6.0
ADD https://github.com/krallin/tini/releases/download/${TINI_VERSION}/tini-static /usr/bin/tini
RUN chmod +x /usr/bin/tini
ENTRYPOINT ["/usr/bin/tini", "--"]

ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
EXPOSE 8888
EXPOSE 55000-56000
COPY entrypoint.sh /entrypoint.sh
CMD sh /entrypoint.sh
#CMD tail -f /dev/null