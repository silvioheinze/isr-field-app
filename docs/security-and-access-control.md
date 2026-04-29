# Security and access control

This application relies on **Django’s authentication framework** (sessions, `User`, `Group`) plus application logic on [`DataSet`](../app/datasets/models.py) and related models.

## Dataset visibility (`can_access`)

For an authenticated user, **`DataSet.can_access(user)`** grants access if **any** of the following holds:

1. User is **superuser**.
2. Dataset **`is_public`** is true (everyone with an account can see it on the dashboard/list paths that honor `can_access`).
3. User is the **`owner`**.
4. User appears in **`shared_with`**.
5. User belongs to at least one **`shared_with_groups`** group.

Anonymous browsers use separate anonymous-data-input URLs when enabled (see below).

Implementation reference: [`DataSet.can_access`](../app/datasets/models.py).

## Who can create datasets (`is_manager`)

The dashboard passes **`can_create_datasets`** based on **`is_manager(request.user)`** in [`auth_views.py`](../app/datasets/views/auth_views.py). A user is treated as a manager if **any** of:

- **`user.is_superuser`**
- **`user.is_staff`**
- User is in the Django group named **`Managers`**

The **`Managers`** group can be created with [`setup_groups`](../app/datasets/management/commands/setup_groups.py) and users added with [`make_manager <username>`](../app/datasets/management/commands/make_manager.py).

Automated tests around this behavior live in [`test_is_manager_permissions.py`](../app/datasets/tests/test_is_manager_permissions.py).

## Typology visibility (`Typology.can_access`)

[`Typology.can_access(user)`](../app/datasets/models.py) allows superusers, **`is_public`** typologies, or the **`created_by`** user.

## Mapping-area restrictions

When **`enable_mapping_areas`** is enabled and the dataset defines **`MappingArea`** rows, collaborators who are **not** owner or superuser may be limited to geometries falling inside specific polygons.

- **`DataSet.get_user_mapping_area_ids(user)`** merges:
  - Per-user limits (`DatasetUserMappingArea`),
  - Per-group limits for the user’s groups (`DatasetGroupMappingArea`),
  - Areas where the user is in **`MappingArea.allocated_users`**.

- **`filter_geometries_for_user`** / **`user_has_geometry_access`** apply these rules when listing or touching geometries.

See [Data model](data-model.md) for details.

## Administrative UI permissions

- **`user_management_view`** is decorated with **`@permission_required('auth.add_user')`** — users need Django’s **`auth.add_user`** permission (typically staff/superuser setups).

- **`admin_change_user_password_view`** requires **`request.user.is_superuser`** (see [`auth_views.py`](../app/datasets/views/auth_views.py)).

Individual dataset views typically call **`dataset.can_access(request.user)`** and render **`datasets/403.html`** with status 403 when denied.

## Anonymous / virtual contributors

If **`allow_anonymous_data_input`** is enabled on a dataset:

- **`anonymous_access_token`** stores a secret token for shareable URLs ([`DataSet.ensure_anonymous_access_token`](../app/datasets/models.py)).
- Routes such as **`dataset_data_input_anonymous`** ([`urls.py`](../app/isrfield/urls.py)) accept that token without normal login.
- Geometries and entries created without a logged-in user may reference **`VirtualContributor`** instead of **`User`**.

Uniqueness rules for geometries combine **`id_kurz`** with **`virtual_contributor`** when applicable.

## Health endpoint

**`/health/`** (`health_check_view`) returns JSON `{ status, timestamp, version }` **without** requiring authentication — suitable for load balancers; do not expose sensitive data there (current implementation does not).

## Related reading

- [Configuration](configuration.md) — `LOGIN_URL`, CSRF, email for resets.
- [Routing and views](routing-and-views.md) — protected routes.
