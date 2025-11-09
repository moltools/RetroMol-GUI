"""Module for configuring the Flask app."""

import atexit
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask


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