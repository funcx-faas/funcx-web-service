FROM postgres:12-alpine
COPY setupdb.sh ./
RUN chmod +x setupdb.sh

COPY funcx-schema.sql ./
ENTRYPOINT ./setupdb.sh