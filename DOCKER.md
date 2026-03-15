# Postgres Docker setup

This project includes a minimal Docker setup to run a PostgreSQL backend using the official image.

Files:
- `Dockerfile` — image based on `postgres:latest` with a basic healthcheck.
- `docker-compose.yml` — service definition that exposes port 5432 and persists data to a volume.
- `.env.example` — example environment variables for database credentials.

Quick start

1. Copy `.env.example` to `.env` and edit if needed.

2. Start the database:

```bash
docker compose up -d
```

3. Confirm the container is healthy:

```bash
docker compose ps
```

4. Stop and remove containers and volumes:

```bash
docker compose down -v
```

Notes
- `compose` is a built-in plugin of the Docker CLI (v20.10+). The legacy standalone `docker-compose` binary is not required.
- The `Dockerfile` is provided if you want to build a custom image, but `docker-compose.yml` already pulls `postgres:latest` from Docker Hub.
- Change credentials in `.env` for production use.
