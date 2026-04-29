# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P1: Scaffold

**Goal:** Working repo with charter committed, structural tooling in place, minimal Compose stack on the laptop, mkcert HTTPS fronting it. Each subsequent package adds the services it consumes (per D11).

**Sessions in this package:**
- S1: Repo bootstrap. Charter and log structure committed at repo root, README, CLAUDE.md, .gitignore, .env.example, Makefile stub. Done.
- S2: Minimal Docker Compose (Postgres with pgvector, Redis), Make targets for up, down, logs, ps, psql. Done.
- S3: mkcert HTTPS, Caddy as dev proxy in front of Compose. Active.

**Status:** S3 active.

**Notes:** P1 closes when `make up` brings a running, HTTPS-fronted minimal stack to life with charter committed. Caddy is the proxy choice for S3 per pre-S3 discussion: simplest config for the local case, no Docker-label coupling that becomes load-bearing later.
