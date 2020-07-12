FROM funcx-web-base
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
COPY entrypoint.sh entrypoint.sh
CMD sh entrypoint.sh
#CMD tail -f /dev/null