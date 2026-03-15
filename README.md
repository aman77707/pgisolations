# pgisolations

Postgres isolation level prototypes.

---

## Prerequisites

Two tools are required: **Docker** (with the Compose plugin) and **uv** (Python package manager).

---

### Docker

Docker Desktop ships with the `docker compose` plugin included. Install it for your platform:

#### macOS

```bash
# Homebrew (recommended)
brew install --cask docker

# Or download Docker Desktop from https://www.docker.com/products/docker-desktop/
```

After install, open **Docker Desktop** once to complete setup, then verify:

```bash
docker --version
docker compose version
```

#### Linux

```bash
# Official convenience script (Ubuntu / Debian / Fedora / RHEL)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # add yourself to the docker group
newgrp docker                   # apply without logging out

# Verify
docker --version
docker compose version
```

> For other distros see the [official install docs](https://docs.docker.com/engine/install/).

#### Windows

```powershell
# WinGet
winget install Docker.DockerDesktop

# Or download the installer from https://www.docker.com/products/docker-desktop/
```

After install, open **Docker Desktop** once to complete setup.

---

### uv (Python package manager)

#### macOS / Linux

```bash
# Official installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv

# Or via asdf
asdf plugin add uv
asdf install uv latest
asdf global uv latest
```

#### Windows

```powershell
# WinGet
winget install astral-sh.uv

# Or via the official installer
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```bash
uv --version
```

---

## Project setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd pgisolations

# 2. Copy env file and adjust credentials if needed
cp .env.example .env

# 3. Install Python dependencies
uv sync

# 4. Start the Postgres backend
docker compose up -d
```

See [DOCKER.md](DOCKER.md) for more Docker-specific details.
