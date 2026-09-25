"""Dev/staging settings that enable Sideburn fixture tooling.

Not used in production. Production uses production_settings (no sideburn_devtools).

Docker / staging:
  COPY deployment/docker/dev_settings.py /pretix/src/dev_settings.py
  export DJANGO_SETTINGS_MODULE=dev_settings
  (and pip install -e ./sideburn-dev-tools — not in the production Dockerfile)

Local:
  Prefer DJANGO_SETTINGS_MODULE pointing at this module once it is on PYTHONPATH,
  or add "sideburn_devtools" to a personal local_settings overlay.
"""
try:
    from production_settings import *  # noqa: F403 — Docker: sibling of this file under /pretix/src/
except ImportError:
    from pretix.settings import *  # noqa: F403

INSTALLED_APPS = list(INSTALLED_APPS) + ["sideburn_devtools"]  # noqa: F405
