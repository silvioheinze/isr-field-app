# ISR Field — application documentation

This folder documents the Django application that lives under [`app/`](../app/): project **`isrfield`**, main app **`datasets`**, GeoDjango/PostGIS storage, and server-rendered UI.

For Docker setup, migrations, backups, and repository-wide workflows, see the root [`README.md`](../README.md).

## Contents

| Document | Description |
|----------|-------------|
| [Overview](overview.md) | Purpose, tech stack, layout of the `app/` directory |
| [Configuration](configuration.md) | Settings, environment variables, static/media, email, logging |
| [Data model](data-model.md) | Models, relationships, access helpers, ER diagram |
| [Routing and views](routing-and-views.md) | URL patterns and which Python modules implement them |
| [Security and access control](security-and-access-control.md) | Dataset access, Managers role, mapping areas, anonymous input |
| [Import, export, and background tasks](import-export-and-background-tasks.md) | CSV flows, file ZIP export, threaded tasks |
| [UI and frontend](ui-and-frontend.md) | Templates, static assets, template tags |
| [Operations and testing](operations-and-testing.md) | Django admin, management commands, test suite |

All paths in these docs are relative to the **repository root** unless stated otherwise (for example `app/isrfield/settings.py`).
