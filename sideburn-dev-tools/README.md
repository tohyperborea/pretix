# sideburn-dev-tools

Dev-only Django app with SideBurn staging fixtures and helper management commands.
**Not a pretix plugin** — do not install in production Docker images.

## Setup (local / staging dummy DB)

```bash
pip install -e ./sideburn-dev-tools
```

Add the app to `INSTALLED_APPS` via the provided settings overlay (not production settings):

```bash
# Docker / staging: use deployment/docker/dev_settings.py on PYTHONPATH
export DJANGO_SETTINGS_MODULE=dev_settings

# Or Option B: personal overlay (e.g. src/pretix/local_settings.py, gitignored):
# INSTALLED_APPS = list(INSTALLED_APPS) + ["sideburn_devtools"]
```

Then:

```bash
cd src
python manage.py migrate
python manage.py load_fixtures
python manage.py load_fixtures --only base
python manage.py dump_fixtures pretixbase.Event --indent 2 -o out.json
```

## What this package contains

| Path | Purpose |
|------|---------|
| `sideburn_devtools/fixtures/*.json` | SideBurn staging organizer/event/tickets/settings |
| `management/commands/load_fixtures` | Ordered `loaddata` with django-scopes disabled |
| `management/commands/dump_fixtures` | `dumpdata` wrapper with django-scopes disabled |

Production Dockerfile must **not** `pip install` this package or add it to `INSTALLED_APPS`.
