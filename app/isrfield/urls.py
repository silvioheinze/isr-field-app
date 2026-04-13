"""
URL configuration for isrfield project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from datasets import views as datasets_views
from datasets.views import export_views, mapping_area_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/login/', datasets_views.EmailLoginView.as_view(), name='login'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('logout/', datasets_views.logout_view, name='logout'),
    path('password-reset/', datasets_views.password_reset_view, name='password_reset_form'),
    path('password-reset/done/', datasets_views.password_reset_done_view, name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', datasets_views.password_reset_confirm_view, name='password_reset_confirm'),
    path('password-reset-complete/', datasets_views.password_reset_complete_view, name='password_reset_complete'),
    path('register/', datasets_views.register_view, name='register'),
    path('profile/', datasets_views.profile_view, name='profile'),
    path('users/', datasets_views.user_management_view, name='user_management'),
    path('users/create/', datasets_views.create_user_view, name='create_user'),
    path('users/edit/<int:user_id>/', datasets_views.edit_user_view, name='edit_user'),
    path('users/<int:user_id>/change-password/', datasets_views.admin_change_user_password_view, name='admin_change_user_password'),
    path('users/delete/<int:user_id>/', datasets_views.delete_user_view, name='delete_user'),
    path('groups/create/', datasets_views.create_group_view, name='create_group'),
    path('groups/edit/<int:group_id>/', datasets_views.edit_group_view, name='edit_group'),
    path('users/groups/<int:user_id>/', datasets_views.modify_user_groups_view, name='modify_user_groups'),
    path('users/groups/<int:group_id>/delete/', datasets_views.delete_group_view, name='delete_group'),
    path('datasets/', datasets_views.dataset_list_view, name='dataset_list'),
    path('datasets/create/', datasets_views.dataset_create_view, name='dataset_create'),
    path('datasets/<int:dataset_id>/', datasets_views.dataset_detail_view, name='dataset_detail'),
    path('datasets/<int:dataset_id>/settings/', datasets_views.dataset_edit_view, name='dataset_settings'),
    path('datasets/<int:dataset_id>/copy/', datasets_views.dataset_copy_view, name='dataset_copy'),
    path('datasets/<int:dataset_id>/field-config/', datasets_views.dataset_field_config_view, name='dataset_field_config'),
    path('datasets/<int:dataset_id>/custom-fields/create/', datasets_views.custom_field_create_view, name='custom_field_create'),
    path('datasets/<int:dataset_id>/custom-fields/<int:field_id>/edit/', datasets_views.custom_field_edit_view, name='custom_field_edit'),
    path('datasets/<int:dataset_id>/custom-fields/<int:field_id>/delete/', datasets_views.custom_field_delete_view, name='custom_field_delete'),
    path('datasets/<int:dataset_id>/access/', datasets_views.dataset_access_view, name='dataset_access'),
    path('datasets/<int:dataset_id>/transfer-ownership/', datasets_views.dataset_transfer_ownership_view, name='dataset_transfer_ownership'),
    path('datasets/<int:dataset_id>/import/columns/', datasets_views.dataset_csv_column_selection_view, name='dataset_csv_column_selection'),
    path('datasets/<int:dataset_id>/import/', datasets_views.dataset_csv_import_view, name='dataset_csv_import'),
    path('datasets/<int:dataset_id>/import/summary/', datasets_views.import_summary_view, name='import_summary'),
    path('datasets/<int:dataset_id>/debug-import/', datasets_views.debug_import_view, name='debug_import'),
    path('datasets/<int:dataset_id>/export/', datasets_views.dataset_export_options_view, name='dataset_export_options'),
    path('datasets/<int:dataset_id>/export/csv/', datasets_views.dataset_csv_export_view, name='dataset_csv_export'),
    # File export URLs
    path('datasets/<int:dataset_id>/export-files/', export_views.dataset_files_export_view, name='dataset_files_export'),
    path('datasets/<int:dataset_id>/export-files/zip/', export_views.export_files_zip_view, name='export_files_zip'),
    path('export-task/<str:task_id>/', export_views.export_task_status_view, name='export_task_status'),
    path('export-task/<str:task_id>/download/', export_views.download_export_file_view, name='download_export_file'),
    path('datasets/<int:dataset_id>/data-input/', datasets_views.dataset_data_input_view, name='dataset_data_input'),
    path('datasets/<int:dataset_id>/data-input/anonymous/<str:token>/', datasets_views.dataset_data_input_anonymous_view, name='dataset_data_input_anonymous'),
    path('datasets/<int:dataset_id>/register-virtual-user/', datasets_views.register_virtual_user_view, name='register_virtual_user'),
    path('datasets/<int:dataset_id>/entries/', datasets_views.dataset_entries_table_view, name='dataset_entries_table'),
    path('datasets/<int:dataset_id>/fields/', datasets_views.dataset_fields_view, name='dataset_fields'),
    path('datasets/<int:dataset_id>/map-data/', datasets_views.dataset_map_data_view, name='dataset_map_data'),
    path('datasets/geometry/<int:geometry_id>/details/', datasets_views.geometry_details_view, name='geometry_details'),
    path('datasets/geometry/<int:geometry_id>/delete/', datasets_views.geometry_delete_view, name='geometry_delete'),
    path('datasets/<int:dataset_id>/clear-data/', datasets_views.dataset_clear_data_view, name='dataset_clear_data'),
    path('datasets/<int:dataset_id>/geometries/create/', datasets_views.geometry_create_view, name='geometry_create'),
    path('entries/<int:entry_id>/edit/', datasets_views.entry_edit_view, name='entry_edit'),
    path('entries/<int:entry_id>/', datasets_views.entry_detail_view, name='entry_detail'),
    path('entries/<int:entry_id>/upload/', datasets_views.file_upload_view, name='file_upload'),
    path('files/<int:file_id>/download/', datasets_views.file_download_view, name='file_download'),
    path('geometries/<int:geometry_id>/entries/create/', datasets_views.entry_create_view, name='entry_create'),
    path('typologies/', datasets_views.typology_list_view, name='typology_list'),
    path('typologies/create/', datasets_views.typology_create_view, name='typology_create'),
    path('typologies/<int:typology_id>/', datasets_views.typology_detail_view, name='typology_detail'),
    path('typologies/<int:typology_id>/edit/', datasets_views.typology_edit_view, name='typology_edit'),
    path('typologies/<int:typology_id>/delete/', datasets_views.typology_delete_view, name='typology_delete'),
    path('typologies/<int:typology_id>/import/', datasets_views.typology_import_view, name='typology_import'),
    path('typologies/<int:typology_id>/export/', datasets_views.typology_export_view, name='typology_export'),
    path('datasets/upload-files/', datasets_views.upload_files_view, name='upload_files'),
    path('datasets/geometry/<int:geometry_id>/files/', datasets_views.geometry_files_view, name='geometry_files'),
    path('datasets/files/<int:file_id>/delete/confirm/', datasets_views.file_delete_view, name='file_delete'),
    path('datasets/files/<int:file_id>/delete/', datasets_views.delete_file_view, name='delete_file'),
    path('entries/save/', datasets_views.save_entries_view, name='save_entries'),
    # Mapping area URLs (outlines must be registered before the list path)
    path(
        'datasets/<int:dataset_id>/mapping-areas/outlines/',
        mapping_area_views.mapping_area_outlines_view,
        name='mapping_area_outlines',
    ),
    path('datasets/<int:dataset_id>/mapping-areas/', mapping_area_views.mapping_area_list_view, name='mapping_area_list'),
    path('datasets/<int:dataset_id>/mapping-areas/create/', mapping_area_views.mapping_area_create_view, name='mapping_area_create'),
    path('datasets/<int:dataset_id>/mapping-areas/<int:area_id>/update/', mapping_area_views.mapping_area_update_view, name='mapping_area_update'),
    path('datasets/<int:dataset_id>/mapping-areas/<int:area_id>/delete/', mapping_area_views.mapping_area_delete_view, name='mapping_area_delete'),
    path('health/', datasets_views.health_check_view, name='health_check'),
    path('', datasets_views.dashboard_view, name='dashboard'),
]

# Serve media and static files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
