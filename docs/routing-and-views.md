# Routing and views

Root routes are defined in [`app/isrfield/urls.py`](../app/isrfield/urls.py). Most handlers come from `datasets_views`, imported from the **`datasets`** package (which resolves to [`datasets/views/__init__.py`](../app/datasets/views/__init__.py), aggregating submodules). The shim [`datasets/views.py`](../app/datasets/views.py) re-exports the same symbols for backward compatibility.

**Dedicated imports**: [`export_views`](../app/datasets/views/export_views.py) and [`mapping_area_views`](../app/datasets/views/mapping_area_views.py) are referenced explicitly in `urls.py`.

## View modules (by responsibility)

| Module | Typical concerns |
|--------|------------------|
| [`auth_views.py`](../app/datasets/views/auth_views.py) | Login (email), register, logout, dashboard, password reset variants, profile, user/group CRUD, health check |
| [`dataset_views.py`](../app/datasets/views/dataset_views.py) | Dataset list/detail/settings/access/copy/transfer/fields, map JSON, entries table, clear data, data-input UI |
| [`geometry_views.py`](../app/datasets/views/geometry_views.py) | Geometry CRUD, map-facing helpers |
| [`entry_views.py`](../app/datasets/views/entry_views.py) | Entries detail/edit/create, batch save (`save_entries`) |
| [`file_views.py`](../app/datasets/views/file_views.py) | Upload, download, delete, geometry-scoped file lists |
| [`import_views.py`](../app/datasets/views/import_views.py) | CSV column selection, import, summary, debug import |
| [`typology_views.py`](../app/datasets/views/typology_views.py) | Typology CRUD, import/export |
| [`export_views.py`](../app/datasets/views/export_views.py) | Attached-file ZIP export, task status, download |
| [`mapping_area_views.py`](../app/datasets/views/mapping_area_views.py) | Mapping-area CRUD and GeoJSON outlines |

[`datasets/views/__init__.py`](../app/datasets/views/__init__.py) also defines **`DatasetFieldInlineFormSet`** and related inline forms used by dataset field configuration screens.

## URL catalog

Listed as **HTTP path** → **Django route name** (namespace: none). Method behavior (GET/POST) is implemented per view.

### Authentication and account

| Path | Route name |
|------|------------|
| `/accounts/login/` | `login` |
| `/accounts/` | Django `django.contrib.auth.urls` (password change defaults, etc.) |
| `/logout/` | `logout` |
| `/password-reset/` | `password_reset_form` |
| `/password-reset/done/` | `password_reset_done` |
| `/password-reset-confirm/<uidb64>/<token>/` | `password_reset_confirm` |
| `/password-reset-complete/` | `password_reset_complete` |
| `/register/` | `register` |
| `/profile/` | `profile` |

### Users and groups (staff permission gates apply where configured)

| Path | Route name |
|------|------------|
| `/users/` | `user_management` |
| `/users/create/` | `create_user` |
| `/users/edit/<user_id>/` | `edit_user` |
| `/users/<user_id>/change-password/` | `admin_change_user_password` |
| `/users/delete/<user_id>/` | `delete_user` |
| `/groups/create/` | `create_group` |
| `/groups/edit/<group_id>/` | `edit_group` |
| `/users/groups/<user_id>/` | `modify_user_groups` |
| `/users/groups/<group_id>/delete/` | `delete_group` |

### Datasets (core)

| Path | Route name |
|------|------------|
| `/datasets/` | `dataset_list` |
| `/datasets/create/` | `dataset_create` |
| `/datasets/<dataset_id>/` | `dataset_detail` |
| `/datasets/<dataset_id>/settings/` | `dataset_settings` |
| `/datasets/<dataset_id>/copy/` | `dataset_copy` |
| `/datasets/<dataset_id>/field-config/` | `dataset_field_config` |
| `/datasets/<dataset_id>/custom-fields/create/` | `custom_field_create` |
| `/datasets/<dataset_id>/custom-fields/<field_id>/edit/` | `custom_field_edit` |
| `/datasets/<dataset_id>/custom-fields/<field_id>/delete/` | `custom_field_delete` |
| `/datasets/<dataset_id>/access/` | `dataset_access` |
| `/datasets/<dataset_id>/transfer-ownership/` | `dataset_transfer_ownership` |

### CSV import

| Path | Route name |
|------|------------|
| `/datasets/<dataset_id>/import/columns/` | `dataset_csv_column_selection` |
| `/datasets/<dataset_id>/import/` | `dataset_csv_import` |
| `/datasets/<dataset_id>/import/summary/` | `import_summary` |
| `/datasets/<dataset_id>/debug-import/` | `debug_import` |

### Export (tabular + files)

| Path | Route name |
|------|------------|
| `/datasets/<dataset_id>/export/` | `dataset_export_options` |
| `/datasets/<dataset_id>/export/csv/` | `dataset_csv_export` |
| `/datasets/<dataset_id>/export-files/` | `dataset_files_export` |
| `/datasets/<dataset_id>/export-files/zip/` | `export_files_zip` |
| `/export-task/<task_id>/` | `export_task_status` |
| `/export-task/<task_id>/download/` | `download_export_file` |

### Data input and listing

| Path | Route name |
|------|------------|
| `/datasets/<dataset_id>/data-input/` | `dataset_data_input` |
| `/datasets/<dataset_id>/data-input/anonymous/<token>/` | `dataset_data_input_anonymous` |
| `/datasets/<dataset_id>/register-virtual-user/` | `register_virtual_user` |
| `/datasets/<dataset_id>/entries/` | `dataset_entries_table` |
| `/datasets/<dataset_id>/fields/` | `dataset_fields` |
| `/datasets/<dataset_id>/map-data/` | `dataset_map_data` |

### Geometries and entries

| Path | Route name |
|------|------------|
| `/datasets/geometry/<geometry_id>/details/` | `geometry_details` |
| `/datasets/geometry/<geometry_id>/delete/` | `geometry_delete` |
| `/datasets/<dataset_id>/clear-data/` | `dataset_clear_data` |
| `/datasets/<dataset_id>/geometries/create/` | `geometry_create` |
| `/entries/<entry_id>/edit/` | `entry_edit` |
| `/entries/<entry_id>/` | `entry_detail` |
| `/entries/<entry_id>/upload/` | `file_upload` |
| `/files/<file_id>/download/` | `file_download` |
| `/geometries/<geometry_id>/entries/create/` | `entry_create` |
| `/entries/save/` | `save_entries` |

### Typologies

| Path | Route name |
|------|------------|
| `/typologies/` | `typology_list` |
| `/typologies/create/` | `typology_create` |
| `/typologies/<typology_id>/` | `typology_detail` |
| `/typologies/<typology_id>/edit/` | `typology_edit` |
| `/typologies/<typology_id>/delete/` | `typology_delete` |
| `/typologies/<typology_id>/import/` | `typology_import` |
| `/typologies/<typology_id>/export/` | `typology_export` |

### Files (bulk / geometry-scoped)

| Path | Route name |
|------|------------|
| `/datasets/upload-files/` | `upload_files` |
| `/datasets/geometry/<geometry_id>/files/` | `geometry_files` |
| `/datasets/files/<file_id>/delete/confirm/` | `file_delete` |
| `/datasets/files/<file_id>/delete/` | `delete_file` |

### Mapping areas

| Path | Route name |
|------|------------|
| `/datasets/<dataset_id>/mapping-areas/outlines/` | `mapping_area_outlines` |
| `/datasets/<dataset_id>/mapping-areas/` | `mapping_area_list` |
| `/datasets/<dataset_id>/mapping-areas/create/` | `mapping_area_create` |
| `/datasets/<dataset_id>/mapping-areas/<area_id>/update/` | `mapping_area_update` |
| `/datasets/<dataset_id>/mapping-areas/<area_id>/delete/` | `mapping_area_delete` |

*Outline routes are registered before the list route so `/outlines/` is not captured as an `<area_id>`.*

### Admin and app shell

| Path | Route name |
|------|------------|
| `/admin/` | Django admin |
| `/health/` | `health_check` |
| `/` | `dashboard` |

## Related reading

- [Security and access control](security-and-access-control.md)
- [Import, export, and background tasks](import-export-and-background-tasks.md)
