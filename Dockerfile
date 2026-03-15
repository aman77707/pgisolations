FROM postgres:latest

ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV POSTGRES_DB=pgisolations

VOLUME ["/var/lib/postgresql/data"]

EXPOSE 5432

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=5 \
  CMD pg_isready -U "$POSTGRES_USER" || exit 1
