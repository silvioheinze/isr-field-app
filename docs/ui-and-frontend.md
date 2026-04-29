# UI and frontend

The UI is **server-rendered HTML** using Django templates. Interactive behavior on map-heavy screens relies on JavaScript in [`app/static/`](../app/static/).

## Template locations

| Directory | Purpose |
|-----------|---------|
| [`app/templates/datasets/`](../app/templates/datasets/) | Primary application pages (datasets, typologies, users, export status, errors). Includes **`_base.html`** as shared layout. |
| [`app/templates/registration/`](../app/templates/registration/) | Stock Django-auth templates overridden for login and password-reset flows (`login.html`, password reset steps). |

Email bodies used by exports may live under `datasets/emails/` (for example [`export_completion.html`](../app/templates/datasets/emails/export_completion.html)).

## Representative templates

- **Dashboard / routing hub**: `dashboard.html`, `dataset_list.html`.
- **Dataset lifecycle**: `dataset_create.html`, `dataset_detail.html`, `dataset_settings.html`, `dataset_access.html`, `dataset_transfer_ownership.html`, `dataset_field_config.html`, custom-field templates.
- **Import/export**: `dataset_csv_column_selection.html`, `dataset_csv_import.html`, `import_summary.html`, `dataset_export.html`, `dataset_files_export.html`, `export_task_status.html`.
- **Spatial editing**: `dataset_data_input.html`, geometry/entry templates (`entry_detail.html`, `entry_edit.html`, `dataset_entries_table.html`).
- **Typologies**: `typology_*.html`, import/export/select/delete templates.
- **Admin-style user UI**: `user_management.html`, create/edit user/group, `403.html`.

Exact filenames correspond one-to-one with views referenced in [Routing and views](routing-and-views.md).

## Static assets (editable source)

Editable assets live under **`app/static/`** (not `staticfiles/`):

| Asset | Role |
|-------|------|
| [`js/data-input.js`](../app/static/js/data-input.js) | Main client logic for the data-input experience (map interactions, saving entries, uploads where wired). |
| [`css/data-input.css`](../app/static/css/data-input.css) | Styles for data-input screens. |
| [`js/qrcode.min.js`](../app/static/js/qrcode.min.js) | QR helper when anonymous/share flows need QR generation. |

After changes, run **`collectstatic`** in deployments so `STATIC_ROOT` receives copies.

## Template tags

[`app/datasets/templatetags/dataset_extras.py`](../app/datasets/templatetags/dataset_extras.py) registers filters:

- **`get_field_value`** — Resolve `DataEntryField` values on an entry.
- **`get_choices_list`** — Choice lists from `DatasetField` / typology-backed fields.
- **`get_item`** — Dict lookup helper for templates.

Load with `{% load dataset_extras %}` where enabled.

## Related reading

- [Overview](overview.md) — Bootstrap-oriented styling mentioned at repo level.
- Root [`README.md`](../README.md) — brand colors and responsive layout notes.
