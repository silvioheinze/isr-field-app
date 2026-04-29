# Operations and testing

## Django admin

[`app/datasets/admin.py`](../app/datasets/admin.py) registers:

- `AuditLog`, `DataSet`, `DataGeometry`, `DataEntry`, `DataEntryFile` — default `ModelAdmin`.
- **`MappingArea`** — custom admin with list display (including **`get_point_count`**), filters, search, **`filter_horizontal`** for **`allocated_users`**.

Other models (for example `DatasetField`, `Typology`) may be managed via custom views instead of admin — check admin file when adding operator tooling.

Reach admin at **`/admin/`** ([`urls.py`](../app/isrfield/urls.py)).

## Management commands

Run from `app/` with **`python manage.py <command>`** (or Docker per root README).

| Command | Purpose |
|---------|---------|
| [`setup_groups`](../app/datasets/management/commands/setup_groups.py) | Ensures **`Managers`** group exists. |
| [`make_manager <username>`](../app/datasets/management/commands/make_manager.py) | Adds user to **`Managers`** so they can create datasets (subject to view logic). |
| [`test_email --to <email>`](../app/datasets/management/commands/test_email.py) | Sends a test message; prints email backend/host settings (SMTP debugging). |

## Monitoring

- **`GET /health/`** — JSON health payload ([`health_check_view`](../app/datasets/views/auth_views.py)).

## Logging

See [Configuration](configuration.md): application logging may write to **`app/debug.log`** depending on logger configuration.

## Tests

Automated tests live under [`app/datasets/tests/`](../app/datasets/tests/). Organization and example commands are documented in [`app/datasets/tests/README.md`](../app/datasets/tests/README.md).

Typical invocation:

```bash
python manage.py test datasets.tests
```

Coverage includes models, forms, CSV handling, permissions, mapping areas, JS-assisted flows (where tested), and integration scenarios — see individual `test_*.py` modules for scope.

For Docker-based commands, follow the root [`README.md`](../README.md).

## Related reading

- [Security and access control](security-and-access-control.md) — who may run operator-only views.
- [Import, export, and background tasks](import-export-and-background-tasks.md) — export reliability notes.
