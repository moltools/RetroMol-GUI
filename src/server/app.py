"""Module for configuring the Flask app."""

import atexit
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask, jsonify

from routes.session import (
    blp_create_session,
    blp_delete_session,
    blp_get_session,
    blp_save_session,
)
from routes.query import dsn_from_env, blp as query_blp


# Initialize the Flask app
app = Flask(__name__)
sessions_key = "SESSIONS"
app.config[sessions_key] = dict()


# Set environment and debug mode
app.config["ENV"] = os.getenv("FLASK_ENV", "production")  # defaults to "production"
app.config["DEBUG"] = app.config["ENV"] == "development"
print("starting app in environment:", app.config["ENV"])
print("debug mode is:", app.debug)


# Log the environment
if app.config["ENV"] == "production":
    print("production environment detected")
elif app.config["ENV"] == "development":
    print("development environment detected")
else:
    print(f"unknown environment: {app.config['ENV']}")


# Add start epoch time of the server to the config
app.config["START_EPOCH"] = int(time.time())


def clear_sessions() -> None:
    """
    Clear the job results. 
    """
    for session in list(app.config[sessions_key]):

        # Find out how long the session has been stored
        timestamp = app.config[sessions_key][session]["created"]
        current_time = int(time.time())
        time_stored = current_time - timestamp

        # If stored longer than 1 day, delete the session
        if time_stored >= 86400 * 7:  # 7 days in seconds
            del app.config[sessions_key][session]


# Set up a scheduler to run the clear_sessions function every week
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=clear_sessions,
    trigger=IntervalTrigger(days=1),
    id="clear_sessions",
    name="clear sessions every week",
    replace_existing=True,
)


# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())


# Register api endpoints
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


# Register blueprints
app.register_blueprint(blp_create_session)
app.register_blueprint(blp_delete_session)
app.register_blueprint(blp_get_session)
app.register_blueprint(blp_save_session)
app.register_blueprint(query_blp)
