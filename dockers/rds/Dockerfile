FROM postgres:latest
ENV POSTGRES_USER funcx
ENV POSTGRES_PASSWORD local-dev-password

COPY rds-schema.sql /docker-entrypoint-initdb.d/rds-schema.sql
