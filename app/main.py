import logging

from flask import jsonify
from werkzeug.exceptions import HTTPException

from app import create_app
from app.core.config import API_PREFIX
from app.routes import job_application_readiness

app = create_app()
app.register_blueprint(job_application_readiness.bp, url_prefix=f"{API_PREFIX}/jobs")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


@app.errorhandler(Exception)
def handle_any(err):
    if isinstance(err, HTTPException):
        return jsonify({"ok": False, "error": err.name}), err.code
    logging.exception("Unhandled error: %s", err)
    return jsonify({"ok": False, "error": "Internal Server Error"}), 500
