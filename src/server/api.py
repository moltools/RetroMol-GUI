"""API endpoints for the server."""

import os
import time

from flask import jsonify

from routes.app import app
from routes.query import dsn_from_env, blp as query_blp


# Register blueprints
app.register_blueprint(query_blp)


@app.errorhandler(404)
def not_found(_) -> str:
    """
    Handle 404 errors by returning the main index page.

    :param _: the error, not used
    :return: the index HTML page
    """
    return app.send_static_file("index.html")


@app.route("/")
def index() -> str:
    """
    Serve the main index page.

    :return: the index HTML page
    """
    return app.send_static_file("index.html")


@app.route("/api/startup")
def startup() -> tuple[dict[str, int], int]:
    """
    Get the startup time of the server.
    
    :return: a dictionary with startup, current time, uptime and HTTP status code
    """
    startup_epoch = app.config["START_EPOCH"]
    return jsonify({
        "startup": startup_epoch,
        "current": int(time.time()),
        "uptime": int(time.time()) - startup_epoch,
    }), 200


@app.route("/api/health", methods=["GET"])
def health() -> tuple[dict[str, str], int]:
    """
    Health check endpoint.

    :return: a dictionary indicating the server is healthy and HTTP status code
    """
    return jsonify({
        "status": "ok",
        "time": int(time.time()),
        "uptime": int(time.time()) - app.config["START_EPOCH"],
        "version": os.getenv("APP_VERSION", "unknown"),
    }), 200


@app.route("/api/ready", methods=["GET"])
def ready() -> tuple[dict[str, str], int]:
    """
    Returns 200 only if the app can read from Postgres.

    :return: a dictionary indicating readiness and HTTP status code
    .. note:: this requires the `psycopg` package to be installed
    """
    try:
        import psycopg
    except ImportError:
        return jsonify({"status": "psycopg not installed"}), 500
    
    dsn = dsn_from_env()

    try:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return jsonify({"status": "ready"}), 200
    except Exception as e:
        return jsonify({"status": "not ready", "error": str(e)}), 503
        



