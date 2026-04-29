# Overview

ISR Field is a Django web application for managing **spatial datasets**: points on a map (**geometries**) with structured **entries** and dynamic **fields**, optional **typologies** for standardized codes, **CSV import/export**, **file attachments**, and fine-grained **access control** including optional **mapping-area** polygons.

## Technical stack

| Layer | Choice |
|-------|--------|
| Framework | Django 5.2 ([`app/isrfield/settings.py`](../app/isrfield/settings.py)) |
| Spatial | GeoDjango (`django.contrib.gis`), PostGIS backend |
| Database | PostgreSQL + PostGIS (`ENGINE`: `django.contrib.gis.db.backends.postgis`) |
| Auth | Django sessions; email-based login ([`EmailLoginView`](../app/datasets/views/auth_views.py)) |
| UI | Server-rendered templates; Bootstrap-oriented layouts under [`app/templates/`](../app/templates/) |
| Assets | Editable static files under [`app/static/`](../app/static/); `collectstatic` output lives under `app/staticfiles/` (do not edit generated copies) |

## Layout of `app/`

```
app/
├── manage.py                 # Django CLI entry point
├── isrfield/                 # Project package
│   ├── settings.py           # Configuration (DB, email, static, logging, …)
│   ├── urls.py               # Root URLconf (routes to datasets views)
│   ├── wsgi.py / asgi.py     # Deployment hooks
├── datasets/                 # Main application
│   ├── models.py             # Domain models (datasets, geometries, entries, …)
│   ├── forms.py              # Forms and field configuration
│   ├── admin.py              # Django admin registrations
│   ├── tasks.py              # ZIP export (background thread)
│   ├── views/                # Split view modules (see routing doc)
│   ├── migrations/           # Schema history
│   ├── management/commands/# CLI helpers (e.g. Managers group)
│   ├── templatetags/         # Template filters (dataset_extras)
│   └── tests/                # Test suite
├── templates/                # Global template directory (datasets/, registration/)
└── static/                   # CSS, JS, images for development
```

## Major features (code-aligned)

- **Datasets**: Owned by a user; can be public; shared with users and Django groups; configurable fields and optional mapping areas ([`DataSet`](../app/datasets/models.py)).
- **Geometries and entries**: One geometry per map point (`id_kurz`, address, coordinates); entries hold year/name and dynamic [`DataEntryField`](../app/datasets/models.py) values.
- **Typologies**: Reusable code lists; can drive choice fields on datasets ([`Typology`](../app/datasets/models.py), [`TypologyEntry`](../app/datasets/models.py)).
- **CSV import/export**: Column mapping, import pipeline, CSV export of tabular data ([`import_views`](../app/datasets/views/import_views.py), dataset export routes).
- **File uploads**: Files attached to entries; bulk ZIP export with optional email notification ([`ExportTask`](../app/datasets/models.py), [`tasks.py`](../app/datasets/tasks.py)).
- **Anonymous data input**: Shareable token URLs and [`VirtualContributor`](../app/datasets/models.py) when enabled on a dataset.
- **Mapping areas**: Polygons restricting which geometries a user or group may see ([`MappingArea`](../app/datasets/models.py) and related models).

## Related reading

- [Configuration](configuration.md) — how to configure the app.
- [Routing and views](routing-and-views.md) — URL map and view modules.
