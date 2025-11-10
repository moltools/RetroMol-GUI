# RetroMol-GUI

Graphical user interface for trying out RetroMol.

Repository contains product-ready docker setup that:
* builds and serves the frontend React app behind nginx
* runs the Flask backend with gunicorn
* runs PostgreSQL and initializes it from a dump on the server
* exposes a read-only DB user for the backend
