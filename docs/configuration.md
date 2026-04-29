# Configuration

Configuration lives in [`app/isrfield/settings.py`](../app/isrfield/settings.py). Values below reflect that file; override via **environment variables** where noted.

## Core Django

| Setting | Notes |
|---------|--------|
| `SECRET_KEY` | `DJANGO_SECRET_KEY`; insecure default present for dev only — set in production. |
| `DEBUG` | Hard-coded `True` in repo settings; production deployments should use env-controlled debug off. |
| `ALLOWED_HOSTS` | Hostnames including `localhost`, deployment host `isrfield.dataplexity.eu`. |
| `CSRF_TRUSTED_ORIGINS` | HTTPS/localhost origins for CSRF. |

## Database (PostGIS)

The default database uses the PostGIS engine:

| Env var | Default |
|---------|---------|
| `POSTGRES_DB` | `isrfield` |
| `POSTGRES_USER` | `isruser` |
| `POSTGRES_PASSWORD` | `isrpassword` |
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5432` |

## Installed applications

`INSTALLED_APPS` includes `django.contrib.gis` (GeoDjango widgets/admin) and `datasets`.

## Templates

`TEMPLATES['DIRS']` includes `BASE_DIR / 'templates'` ([`app/templates/`](../app/templates/)).

## Static and media files

| Purpose | Setting | Path / URL |
|---------|---------|------------|
| Static URL | `STATIC_URL` | `'static/'` |
| Static root (collectstatic) | `STATIC_ROOT` | `BASE_DIR / 'staticfiles'` |
| Extra static dirs | `STATICFILES_DIRS` | `[BASE_DIR / 'static']` → [`app/static/`](../app/static/) |
| Media URL | `MEDIA_URL` | `'/media/'` |
| Media root | `MEDIA_ROOT` | `BASE_DIR / 'media'` |

In **DEBUG**, [`urls.py`](../app/isrfield/urls.py) serves both media and static from these roots.

## Upload limits

The settings file raises Django defaults substantially (for example large ZIP/media uploads):

- `DATA_UPLOAD_MAX_MEMORY_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` — very large values (check [`settings.py`](../app/isrfield/settings.py) for current bytes).
- `FILE_UPLOAD_MAX_NUMBER_FIELDS` — increased for multi-file uploads.

## Email

| Env var | Role |
|---------|------|
| `EMAIL_BACKEND` | Defaults to console backend for development. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_USE_SSL` | SMTP settings when using SMTP. |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Credentials. |
| `DEFAULT_FROM_EMAIL`, `SERVER_EMAIL`, `EMAIL_SUBJECT_PREFIX` | From addresses and subject prefix (`[ISR Field]`). |

Password reset and export-completion emails depend on a working backend in production.

## Authentication redirects

- `LOGIN_URL`: `/accounts/login/`
- `LOGIN_REDIRECT_URL`: `/`
- `LOGOUT_REDIRECT_URL`: `/accounts/login/`

## Logging

`LOGGING` sends **`frontend.views`** loggers to console and to `BASE_DIR / 'debug.log'` (`datasets`-adjacent path under `app/`). The **`django`** logger uses console at INFO.

## Internationalization

`LANGUAGE_CODE` is `en-us`, `TIME_ZONE` is `UTC`, with `USE_I18N` and `USE_TZ` enabled.
