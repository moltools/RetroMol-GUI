# Python backend with gunicorn
FROM python:3.10-slim

WORKDIR /app

# System deps (psycopg binary + git if needed)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Copy backend; Flask code lives in src/server
COPY src/server /app

# Install requirements
RUN pip install --no-cache-dir -r requirements.txt

# gunicorn entry (Flask app is created in routes/app.py as `app`)
# expose 4000 internally on the network
ENV PORT=4000
EXPOSE 4000

# Let Flask/gunicorn find the app: "app:app"
CMD ["gunicorn", "-w", "3", "-b", "0.0.0.0:4000", "--access-logfile", "-", "--error-logfile", "-", "--log-level", "info", "--timeout", "120", "app:app"]