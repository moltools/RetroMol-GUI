# RetroMol-GUI

Graphical user interface for trying out RetroMol.

This repository contains both a production-ready Docker setup and a developer-friendly local workflow.

## Build and run with Docker

The default setup runs everything containerized:
- Builds and serves the frontend React app behind nginx
- Runs the Flask backend with gunicorn
- Runs PostgreSQL and initializes it from a dump file
- Exposes a read-only DB user for the backend

---

### Start the full stack

First make sure to copy `.env.example` to `.env` and adjust any environment variables as needed.

Then run:

```bash
docker compose up -d --build
```

### Access the application 

- App UI: `http://<server-ip>/**`
- API endpoints: `http://<server-ip>/api/...**`

For local user, `<server-ip>` is typically `localhost:4005`.

---

### Database persistence

Postgres persists data inside the named Docker volume `db_data`.

Existing volumes can be listed with:

```bash
docker volume ls
```

To remove the volume (and all data inside), run:

```bash
docker volume rm <volume_name>
```

---

### Re-seed the database

Postgres will initialize once from the dump file specified in `.env` (make sure to copy `.env.example` to `.env` and edit before first build).

To re-seed the database:

```bash
docker compose down -v  # destroys db_data volume
docker compose up -d --build
```

---

### Check container health

Check that the backend and database are reachable through the API:

```bash
curl -i http://<server-ip>/api/health  # should return 200 OK (backend alive)
curl -i http://<server-ip>/api/ready  # should return 200 OK (DB connection OK)
```

For local runs, use:

```bash
curl -i http://localhost:4005/api/health  # should return 200 OK (backend alive)
curl -i http://localhost:4005/api/ready  # should return 200 OK (DB connection OK)
```

> Make sure scripts in `/db/init` are executable before first build:
> ```bash
> chmod +x db/init/*.sh
> ```

---

## Local development mode

You can develop with hot-reloading for both backend and frontend, while still using the database from Docker.

---

### Start only the database (in Docker)

Expose Postgres to your host for local development:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db
```

This keeps the database running at:
```
Host: localhost
Port: 5432
User: app_ro
Password: apppass_ro
DB name: bionexus
```

---

### Run the backend locally

First create a virtual environment and install backend dependencies listed in  `src/server/requirements.txt`.

Then, run the helper script:

```bash
./scripts/dev_backend.sh
```

This script:
- Sets up DB connection variables
- Runs Flask in debug mode with auto-reload on port 4000

Verify health endpoint to check backend is running:

```bash
curl -i http://localhost:4000/api/health
```

---

### Run the frontend locally

From the React client directory `src/client`, install dependencies and start the development server:

```bash
cd src/client
npm install
npm start
```

Ensure the `package.json` has the proxy set to the backend URL:

```json
{
    "proxy": "http://localhost:4000"
}
```

Requests to `/api/...` will automatically proxy to Flask.