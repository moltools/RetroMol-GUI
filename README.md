# RetroMol-GUI

Graphical user interface for trying out RetroMol.

Repository contains product-ready docker setup that:
* builds and serves the frontend React app behind nginx
* runs the Flask backend with gunicorn
* runs PostgreSQL and initializes it from a dump on the server
* exposes a read-only DB user for the backend

## Build and run with Docker

```bash
docker compose up -d --build
```

* App: `http://<server-ip/`
* API proxied at: `http://<server-ip>/api/...`
* Postgres persists in the named volume `db_data` (Docker manages it)

NOTE: make sure to make the scripts in `/db/init` executable (`chmod +x`) before first build.

### Re-seed the DB

Postgres will initialize once from the dump file specified in `.env` (make sure to copy `.env.example` and edit it first).

To re-seed, run `docker compose down -v` (destroys `db_data` volume) and then `docker compose up -d --build` again.

### Check health containers

#### Reachability from the frontend

```bash
curl -i http://<server-ip>/api/health  # should return 200 OK for backend
curl -i http://<server-ip>/api/ready  # should return 200 OK for DB connection
```

For local development, `server-ip` equals to `localhost:4005`.
