# Backend Phase 1: PostgreSQL Local Setup + First Connection Check

This is the **first small backend step**: get PostgreSQL running locally and verify we can connect to it.

## What you will learn in this phase

- What PostgreSQL is responsible for in this project.
- How to run a local Postgres instance with Docker.
- How to verify that a database and user are working.
- Which actions are manual vs. which I can automate for you.

## Why this step comes first

Before we write API endpoints or business logic, we need a reliable data store. PostgreSQL is where we will persist:

- third-party developer records,
- content metadata (games/apps),
- publishing/payment configuration references,
- and later purchase/download lifecycle data.

If this step is stable, all later backend tasks become much easier.

## Prerequisites (manual)

You need to have these installed **on your machine**:

1. Docker Desktop (or Docker Engine + Compose)
2. Git
3. A terminal you are comfortable with

> Manual action required from you: install Docker if it is not already installed.

## Local PostgreSQL using Docker Compose

Create a file named `docker-compose.backend.yml` in the repository root with the following content:

```yaml
services:
  postgres:
    image: postgres:16
    container_name: board_tpl_postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: board_tpl
      POSTGRES_USER: board_tpl_user
      POSTGRES_PASSWORD: board_tpl_password
    ports:
      - "5432:5432"
    volumes:
      - board_tpl_pg_data:/var/lib/postgresql/data

volumes:
  board_tpl_pg_data:
```

Then run:

```bash
docker compose -f docker-compose.backend.yml up -d
```

## Verify the database is alive

Run this command:

```bash
docker exec -it board_tpl_postgres psql -U board_tpl_user -d board_tpl -c "SELECT current_database(), current_user;"
```

Expected result includes:

- `board_tpl` as database
- `board_tpl_user` as user

## Troubleshooting basics

If the container fails to start:

- Check logs: `docker logs board_tpl_postgres`
- Confirm port 5432 is free on your machine.
- If needed, change the host port from `5432:5432` to `5433:5432` and reconnect using port `5433`.

## How I can help vs. what you must do

### I can do automatically when you give access to files/commands

- Generate/update Compose files and `.env.example` files.
- Add backend app config with safe defaults for local development.
- Add migration tooling and create initial schema migrations.
- Validate commands and fix issues in repository scripts.

### You still need to do manually on your machine (unless running in an integrated environment)

- Install Docker and start Docker service.
- Run local containers.
- Provide secrets/credentials for non-local environments.

## Best ways to integrate me into your process

If you want me to perform more setup directly with fewer manual steps, these integrations help a lot:

1. **Initialize backend/frontend submodules after clone** so their files are checked out locally and I can edit code inside them.
   - Why this matters: a submodule being *defined* in `.gitmodules` is not the same thing as being *initialized* in your working tree.
   - Run: `git submodule update --init --recursive`
   - Verify: `git submodule status` should show entries without a leading `-`.
2. **Store setup scripts in-repo** (e.g., `scripts/dev-up.sh`) so I can edit and improve them incrementally.
3. **Use `.env.example` files** for each service; I can maintain these while you keep real `.env` private.
4. **Use CI (GitHub Actions)** for checks; I can adapt code/scripts to pass the same checks locally and in CI.
5. **Provide a single command workflow** (e.g., `make dev-up`, `make test`) so I can run/validate quickly each step.

## What we should do next (Phase 2 suggestion)

After you confirm PostgreSQL starts correctly, next small step should be:

- scaffold backend service (language/framework of your choice),
- add DB connection config,
- implement one health check endpoint that confirms DB connectivity.

That gives us a minimal but real backend slice end-to-end.
