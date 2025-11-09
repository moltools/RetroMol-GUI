"""API endpoints for the server."""

import time

from retromol.version import __version__

from routes.app import app


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


@app.route("/api/getVersion")
def version() -> tuple[dict[str, str], int]:
    """
    Get the version of the server.
    
    :return: a dictionary with the version information and HTTP status code
    """
    return {"version": __version__}, 200


@app.route("/api/startup")
def startup() -> tuple[dict[str, int], int]:
    """
    Get the startup time of the server.
    
    :return: a dictionary with startup, current time, uptime and HTTP status code
    """
    startup_epoch = app.config["START_EPOCH"]
    return {
        "startup": startup_epoch,
        "current": int(time.time()),
        "uptime": int(time.time()) - startup_epoch,
    }, 200