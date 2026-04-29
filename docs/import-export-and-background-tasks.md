# Import, export, and background tasks

## CSV import

CSV workflows are implemented under [`app/datasets/views/import_views.py`](../app/datasets/views/import_views.py) and wired in [`urls.py`](../app/isrfield/urls.py):

1. **`dataset_csv_column_selection`** — Choose/import mapping of CSV columns to dataset fields.
2. **`dataset_csv_import`** — Upload/process CSV according to that mapping.
3. **`import_summary`** — Summary after import completes.
4. **`debug_import`** — Debugging aids during development/troubleshooting.

Delimiters, encoding, and column behaviors have dedicated tests (for example [`test_csv_delimiter.py`](../app/datasets/tests/test_csv_delimiter.py), [`test_csv_import.py`](../app/datasets/tests/test_csv_import.py)).

## CSV export (tabular data)

Dataset CSV export is exposed as **`dataset_export_options`** (choose options) and **`dataset_csv_export`** (generate download). These operate on structured entry/field data rather than raw uploads folder trees.

## Entry attachments: bulk ZIP export

Attached files live in **`DataEntryFile`** ([`models.py`](../app/datasets/models.py)). The UI flow:

1. **`dataset_files_export`** — Dashboard-style page with statistics and filters ([`export_views.dataset_files_export_view`](../app/datasets/views/export_views.py)); requires **`dataset.can_access`**.
2. **`export_files_zip`** — POST submits filters (`file_types`, optional date range, **`organize_by`**, **`include_metadata`**, email notification flag). Calls **`start_export_task`** from [`tasks.py`](../app/datasets/tasks.py), then redirects to **`export_task_status`** with the new **`task_id`**.
3. **`export_task_status`** — Poll-friendly status page; shows download link when **`ExportTask.status`** is **`completed`**.
4. **`download_export_file`** — Streams the ZIP when the task completed and file exists under **`MEDIA_ROOT`**.

### Background execution model

[`start_export_task`](../app/datasets/tasks.py) creates an **`ExportTask`** row and starts **`generate_zip_export`** in a **`threading.Thread`** (daemon). This is **not** Celery/RQ; workers restart may lose in-flight threads.

Completion updates the **`ExportTask`** record (`status`, **`file_path`**, **`file_size`**, **`completed_at`**, **`error_message`** on failure).

Optional **email** notification uses Django **`send_mail`** when configured ([see configuration](configuration.md)); if the user has no email, the UI may downgrade to in-app messaging only.

### ZIP contents

[`generate_zip_export`](../app/datasets/tasks.py) builds under **`MEDIA_ROOT/exports/<task_id>/`**, adds entry files with prefixed names (`organize_by` controls grouping), and may embed metadata JSON.

### Statistics helpers

[`calculate_file_statistics`](../app/datasets/views/export_views.py) aggregates counts by type, user, geometry id, and upload date range for the export landing page.

## Other save endpoints

**`/entries/save/`** (`save_entries`) batches client-side edits from the data-input UI — see [`entry_views`](../app/datasets/views/entry_views.py) for behavior and permission checks.

## Related reading

- [Data model](data-model.md) — `ExportTask`, `DataEntryFile`.
- [Routing and views](routing-and-views.md) — exact route names.
