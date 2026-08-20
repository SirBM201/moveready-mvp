"""MoveReady service package bootstrap."""

# Keep scanner hardening additive so the stable discovery module retains its
# public API while production receives stricter vacancy validation, clearer
# source failures, and conservative employer-board pagination.
from app.services import job_discovery_hardening as _job_discovery_hardening

_job_discovery_hardening.install()
