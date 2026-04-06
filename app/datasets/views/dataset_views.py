from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.urls import reverse
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q, Max

from ..models import (
    DataSet,
    DataGeometry,
    DataEntry,
    DataEntryField,
    DataEntryFile,
    DatasetField,
    DatasetFieldConfig,
    AuditLog,
    Typology,
    DatasetUserMappingArea,
    DatasetGroupMappingArea,
    MappingArea,
    VirtualContributor,
)
from ..forms import DatasetFieldConfigForm, DatasetFieldForm, TransferOwnershipForm
def _get_typology_categories_map(user=None):
    categories = {}
    # Get typologies the user can access
    if user and user.is_superuser:
        typologies = Typology.objects.all()
    else:
        public_typologies = Typology.objects.filter(is_public=True)
        user_typologies = Typology.objects.filter(created_by=user) if user else Typology.objects.none()
        typologies = (public_typologies | user_typologies).distinct()
    
    for typology in typologies.order_by('name'):
        category_values = (
            typology.entries.order_by('category')
            .values_list('category', flat=True)
            .distinct()
        )
        categories[str(typology.id)] = [value for value in category_values if value]
    return categories
from .auth_views import is_manager


def resolve_data_input_actor(request, dataset, require_virtual_contributor=False):
    """
    Resolve the actor (user or virtual contributor) for data input access.
    Returns (user, virtual_contributor). Denied: (None, None).
    For logged-in: (request.user, None). For anonymous with valid token: (None, vc).
    When require_virtual_contributor=False, anonymous with valid token but no VC yet
    returns (None, 'pending') to allow e.g. empty map load before name modal.
    """
    if request.user.is_authenticated:
        if dataset.can_access(request.user):
            return (request.user, None)
        return (None, None)
    token = request.session.get(f'anonymous_token_{dataset.id}')
    if not getattr(dataset, 'allow_anonymous_data_input', False) or not token or dataset.anonymous_access_token != token:
        return (None, None)
    vc_uuid_str = request.session.get(f'virtual_contributor_uuid_{dataset.id}')
    if not vc_uuid_str:
        return (None, 'pending') if not require_virtual_contributor else (None, None)
    import uuid as uuid_mod
    try:
        vc_uuid = uuid_mod.UUID(vc_uuid_str)
        vc = VirtualContributor.objects.filter(dataset=dataset, uuid=vc_uuid).first()
        if vc:
            return (None, vc)
    except (ValueError, TypeError):
        pass
    return (None, 'pending') if not require_virtual_contributor else (None, None)


def ensure_dataset_field_config(dataset: DataSet) -> DatasetFieldConfig:
    """
    Ensure a DatasetFieldConfig instance exists for the dataset.

    The legacy behaviour of auto-creating fixed standard fields
    (name, usage_code1-3, cat_*, year) has been removed so that
    all fields behave like normal custom fields.
    """
    config, _ = DatasetFieldConfig.objects.get_or_create(dataset=dataset)
    return config


@login_required
def dataset_list_view(request):
    """List all datasets accessible to the user"""
    # Superusers can see all datasets regardless of access permissions
    if request.user.is_superuser:
        all_datasets = DataSet.objects.all().order_by('-created_at')
    else:
        # Get datasets owned by user or shared with user
        owned_datasets = DataSet.objects.filter(owner=request.user)
        shared_datasets = DataSet.objects.filter(shared_with=request.user)
        group_shared_datasets = DataSet.objects.filter(shared_with_groups__in=request.user.groups.all())
        public_datasets = DataSet.objects.filter(is_public=True)
        
        # Combine and deduplicate
        all_datasets = (owned_datasets | shared_datasets | group_shared_datasets | public_datasets).distinct()
    
    return render(request, 'datasets/dataset_list.html', {
        'datasets': all_datasets,
        'can_create_datasets': is_manager(request.user)
    })


@login_required
def dataset_create_view(request):
    """Create a new dataset"""
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        
        if name:
            dataset = DataSet.objects.create(
                name=name,
                description=description,
                owner=request.user
            )
            messages.success(request, f'Dataset "{name}" created successfully!')
            return redirect('dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'Dataset name is required.')
    
    return render(request, 'datasets/dataset_create.html')


@login_required
def dataset_detail_view(request, dataset_id):
    """View dataset details and manage fields"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Check if user has access to this dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)

    # Handle field configuration updates
    if request.method == 'POST' and request.POST.get('action') == 'update_fields':
        if dataset.owner == request.user:
            try:
                # Update field configurations
                for field in DatasetField.objects.filter(dataset=dataset):
                    field_id = field.id
                    
                    # Update label
                    if f'field_{field_id}_label' in request.POST:
                        field.label = request.POST[f'field_{field_id}_label']
                    
                    # Update order
                    if f'field_{field_id}_order' in request.POST:
                        try:
                            field.order = int(request.POST[f'field_{field_id}_order'])
                        except ValueError:
                            pass
                    
                    # Update enabled status
                    field.enabled = f'field_{field_id}_enabled' in request.POST
                    
                    # Update required status
                    field.required = f'field_{field_id}_required' in request.POST
                    
                    # Update non_editable status
                    field.non_editable = f'field_{field_id}_non_editable' in request.POST
                    
                    field.save()
                
                messages.success(request, 'Field configuration updated successfully.')
            except Exception as e:
                messages.error(request, f'Error updating field configuration: {str(e)}')
        
        return redirect('dataset_detail', dataset_id=dataset.id)
    
    # Get counts for geometries and data entries
    geometries_count = DataGeometry.objects.filter(dataset=dataset).count()
    data_entries_count = DataEntry.objects.filter(geometry__dataset=dataset).count()
    
    # Get all fields for this dataset
    all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset))

    anonymous_data_input_url = None
    if getattr(dataset, 'allow_anonymous_data_input', False) and dataset.anonymous_access_token:
        anonymous_data_input_url = request.build_absolute_uri(
            reverse('dataset_data_input_anonymous', kwargs={'dataset_id': dataset.id, 'token': dataset.anonymous_access_token})
        )

    return render(request, 'datasets/dataset_detail.html', {
        'dataset': dataset,
        'geometries_count': geometries_count,
        'data_entries_count': data_entries_count,
        'all_fields': all_fields,
        'anonymous_data_input_url': anonymous_data_input_url
    })


@login_required
def dataset_edit_view(request, dataset_id):
    """Edit dataset details"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Only dataset owner or superuser can edit
    if dataset.owner != request.user and not request.user.is_superuser:
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        if 'delete_dataset' in request.POST:
            # Handle dataset deletion
            dataset_name = dataset.name
            dataset.delete()
            messages.success(request, f'Dataset "{dataset_name}" deleted successfully!')
            return redirect('dataset_list')
        
        # Handle dataset update
        name = request.POST.get('name')
        description = request.POST.get('description')
        is_public = request.POST.get('is_public') == 'on'
        allow_multiple_entries = request.POST.get('allow_multiple_entries') == 'on'
        enable_mapping_areas = request.POST.get('enable_mapping_areas') == 'on'
        allow_anonymous_data_input = request.POST.get('allow_anonymous_data_input') == 'on'
        map_default_lat = request.POST.get('map_default_lat')
        map_default_lng = request.POST.get('map_default_lng')
        map_default_zoom = request.POST.get('map_default_zoom')
        
        if name:
            dataset.name = name
            dataset.description = description
            dataset.is_public = is_public
            # Handle allow_multiple_entries field (graceful handling for migration)
            try:
                dataset.allow_multiple_entries = allow_multiple_entries
            except AttributeError:
                pass  # Field doesn't exist yet, skip
            # Handle enable_mapping_areas field (graceful handling for migration)
            try:
                dataset.enable_mapping_areas = enable_mapping_areas
            except AttributeError:
                pass  # Field doesn't exist yet, skip
            # Handle allow_anonymous_data_input
            try:
                dataset.allow_anonymous_data_input = allow_anonymous_data_input
                if allow_anonymous_data_input:
                    dataset.ensure_anonymous_access_token()
                else:
                    dataset.anonymous_access_token = None
            except AttributeError:
                pass
            # Map defaults (graceful handling if migration not yet applied)
            try:
                dataset.map_default_lat = float(map_default_lat) if map_default_lat else None
                dataset.map_default_lng = float(map_default_lng) if map_default_lng else None
                z = int(map_default_zoom) if map_default_zoom else None
                dataset.map_default_zoom = max(1, min(18, z)) if z is not None else None
            except (ValueError, TypeError, AttributeError):
                pass
            dataset.save()
            
            messages.success(request, 'Dataset updated successfully!')
            return redirect('dataset_detail', dataset_id=dataset.id)
        else:
            messages.error(request, 'Dataset name is required.')
    
    return render(request, 'datasets/dataset_settings.html', {
        'dataset': dataset,
        'geometries_count': DataGeometry.objects.filter(dataset=dataset).count(),
        'entries_count': DataEntry.objects.filter(geometry__dataset=dataset).count(),
        'field_count': DatasetField.objects.filter(dataset=dataset).count()
    })


@login_required
@transaction.atomic
def dataset_copy_view(request, dataset_id):
    """Copy a dataset with all its configuration and data (fields, mapping areas, geometry points, entries, files, etc.)"""
    # Only superusers can copy datasets
    if not request.user.is_superuser:
        return render(request, 'datasets/403.html', status=403)
    
    original_dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Check if user has access to the original dataset
    if not original_dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    
    # Create new dataset with "_Copy" suffix
    new_name = f"{original_dataset.name}_Copy"
    # Ensure name doesn't exceed max_length (255)
    if len(new_name) > 255:
        new_name = original_dataset.name[:250] + "_Copy"
    
    # Create the new dataset
    create_kwargs = {
        'name': new_name,
        'description': original_dataset.description,
        'owner': request.user,
        'is_public': original_dataset.is_public,
        'allow_multiple_entries': original_dataset.allow_multiple_entries,
        'enable_mapping_areas': original_dataset.enable_mapping_areas,
    }
    if hasattr(original_dataset, 'map_default_lat'):
        create_kwargs['map_default_lat'] = original_dataset.map_default_lat
        create_kwargs['map_default_lng'] = original_dataset.map_default_lng
        create_kwargs['map_default_zoom'] = original_dataset.map_default_zoom
    new_dataset = DataSet.objects.create(**create_kwargs)
    
    # Copy ManyToMany relationships (shared_with and shared_with_groups)
    new_dataset.shared_with.set(original_dataset.shared_with.all())
    new_dataset.shared_with_groups.set(original_dataset.shared_with_groups.all())
    
    # Copy DatasetFieldConfig if it exists
    try:
        original_config = original_dataset.field_config
        DatasetFieldConfig.objects.create(
            dataset=new_dataset,
            usage_code1_label=original_config.usage_code1_label,
            usage_code1_enabled=original_config.usage_code1_enabled,
            usage_code2_label=original_config.usage_code2_label,
            usage_code2_enabled=original_config.usage_code2_enabled,
            usage_code3_label=original_config.usage_code3_label,
            usage_code3_enabled=original_config.usage_code3_enabled,
            cat_inno_label=original_config.cat_inno_label,
            cat_inno_enabled=original_config.cat_inno_enabled,
            cat_wert_label=original_config.cat_wert_label,
            cat_wert_enabled=original_config.cat_wert_enabled,
            cat_fili_label=original_config.cat_fili_label,
            cat_fili_enabled=original_config.cat_fili_enabled,
            year_label=original_config.year_label,
            year_enabled=original_config.year_enabled,
            name_label=original_config.name_label,
            name_enabled=original_config.name_enabled,
        )
    except DatasetFieldConfig.DoesNotExist:
        pass  # No config to copy
    
    # Copy all DatasetField objects
    for original_field in original_dataset.dataset_fields.all():
        DatasetField.objects.create(
            dataset=new_dataset,
            field_name=original_field.field_name,
            label=original_field.label,
            field_type=original_field.field_type,
            required=original_field.required,
            enabled=original_field.enabled,
            non_editable=original_field.non_editable,
            help_text=original_field.help_text,
            choices=original_field.choices,
            order=original_field.order,
            is_coordinate_field=original_field.is_coordinate_field,
            is_id_field=original_field.is_id_field,
            is_address_field=original_field.is_address_field,
            typology=original_field.typology,  # Reference to same typology
            typology_category=original_field.typology_category,
        )
    
    # Copy MappingArea objects and their relationships
    mapping_area_map = {}  # Map original area ID to new area
    for original_area in original_dataset.mapping_areas.all():
        new_area = MappingArea.objects.create(
            dataset=new_dataset,
            name=original_area.name,
            geometry=original_area.geometry,  # Copy the geometry
            created_by=request.user,
        )
        # Copy allocated_users ManyToMany
        new_area.allocated_users.set(original_area.allocated_users.all())
        mapping_area_map[original_area.id] = new_area
    
    # Copy DatasetUserMappingArea relationships
    for original_user_area in DatasetUserMappingArea.objects.filter(dataset=original_dataset):
        if original_user_area.mapping_area_id in mapping_area_map:
            DatasetUserMappingArea.objects.create(
                dataset=new_dataset,
                user=original_user_area.user,
                mapping_area=mapping_area_map[original_user_area.mapping_area_id],
            )
    
    # Copy DatasetGroupMappingArea relationships
    for original_group_area in DatasetGroupMappingArea.objects.filter(dataset=original_dataset):
        if original_group_area.mapping_area_id in mapping_area_map:
            DatasetGroupMappingArea.objects.create(
                dataset=new_dataset,
                group=original_group_area.group,
                mapping_area=mapping_area_map[original_group_area.mapping_area_id],
            )
    
    # Copy DataGeometry objects (geometry points)
    geometry_map = {}  # Map original geometry ID to new geometry
    for original_geometry in original_dataset.geometries.all():
        new_geometry = DataGeometry.objects.create(
            dataset=new_dataset,
            address=original_geometry.address,
            geometry=original_geometry.geometry,  # Copy the geometry
            id_kurz=original_geometry.id_kurz,
            user=request.user,  # Set to current user
        )
        geometry_map[original_geometry.id] = new_geometry
    
    # Copy DataEntry objects and their related data
    entry_map = {}  # Map original entry ID to new entry
    for original_geometry_id, new_geometry in geometry_map.items():
        original_geometry = DataGeometry.objects.get(id=original_geometry_id)
        for original_entry in original_geometry.entries.all():
            new_entry = DataEntry.objects.create(
                geometry=new_geometry,
                name=original_entry.name,
                year=original_entry.year,
                user=request.user,  # Set to current user
            )
            entry_map[original_entry.id] = new_entry
            
            # Copy DataEntryField objects (field values)
            for original_field in original_entry.fields.all():
                DataEntryField.objects.create(
                    entry=new_entry,
                    field_name=original_field.field_name,
                    field_type=original_field.field_type,
                    value=original_field.value,
                )
            
            # Copy DataEntryFile objects (files)
            for original_file in original_entry.files.all():
                # Copy the actual file content if it exists
                if original_file.file and original_file.file.name:
                    try:
                        # Open the original file and copy its content
                        original_file.file.open('rb')
                        file_content = original_file.file.read()
                        original_file.file.close()
                        
                        # Create new file entry with the copied file
                        new_file = DataEntryFile.objects.create(
                            entry=new_entry,
                            filename=original_file.filename,
                            file_type=original_file.file_type,
                            file_size=original_file.file_size,
                            upload_user=request.user,  # Set to current user
                            description=original_file.description,
                        )
                        # Save the file content to the new file field
                        from django.core.files.base import ContentFile
                        new_file.file.save(
                            original_file.filename,
                            ContentFile(file_content),
                            save=True
                        )
                    except Exception as e:
                        # If file copy fails, create entry without file but log the error
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"Failed to copy file {original_file.filename}: {e}")
                        # Still create the file entry record without the actual file
                        DataEntryFile.objects.create(
                            entry=new_entry,
                            filename=original_file.filename,
                            file_type=original_file.file_type,
                            file_size=0,  # Set to 0 since file wasn't copied
                            upload_user=request.user,
                            description=f"{original_file.description or ''} (File copy failed: {str(e)})".strip(),
                        )
                else:
                    # No file to copy, just create the entry record
                    DataEntryFile.objects.create(
                        entry=new_entry,
                        filename=original_file.filename,
                        file_type=original_file.file_type,
                        file_size=original_file.file_size,
                        upload_user=request.user,
                        description=original_file.description,
                    )
    
    messages.success(request, f'Dataset "{original_dataset.name}" copied successfully as "{new_name}"!')
    return redirect('dataset_detail', dataset_id=new_dataset.id)


@login_required
def dataset_field_config_view(request, dataset_id):
    """
    Manage dataset field configuration (labels, enabled flags).

    Note: The legacy fixed standard fields have been removed.
    This view now only manages the separate DatasetFieldConfig
    object (labels, enabled flags metadata) and the existing
    DatasetField instances for the dataset.
    """
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    if dataset.owner != request.user and not request.user.is_superuser:
        return render(request, 'datasets/403.html', status=403)
    
    config = ensure_dataset_field_config(dataset)
    form = DatasetFieldConfigForm(instance=config)
    
    if request.method == 'POST':
        config_field_names = set(DatasetFieldConfigForm.Meta.fields)
        config_fields_present = any(field_name in request.POST for field_name in config_field_names)
        
        form_valid = True
        if config_fields_present:
            form = DatasetFieldConfigForm(request.POST, instance=config)
            if form.is_valid():
                form.save()
            else:
                form_valid = False
        
        dataset_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset))
        dataset_fields_updated = False
        for field in dataset_fields:
            field_prefix = f'field_{field.id}'
            label_key = f'{field_prefix}_label'
            order_key = f'{field_prefix}_order'
            help_text_key = f'{field_prefix}_help_text'
            enabled_key = f'{field_prefix}_enabled'
            required_key = f'{field_prefix}_required'
            
            changed = False
            
            if label_key in request.POST:
                new_label = request.POST.get(label_key, '').strip()
                if new_label and new_label != field.label:
                    field.label = new_label
                    changed = True
            
            if order_key in request.POST:
                try:
                    new_order = int(request.POST[order_key])
                except (ValueError, TypeError):
                    new_order = field.order
                if new_order != field.order:
                    field.order = new_order
                    changed = True
            
            if help_text_key in request.POST:
                new_help_text = request.POST.get(help_text_key, '').strip()
                if new_help_text != (field.help_text or ''):
                    field.help_text = new_help_text
                    changed = True
            
            enabled_value = request.POST.get(enabled_key) == 'on'
            if enabled_value != field.enabled:
                field.enabled = enabled_value
                changed = True
            
            required_value = request.POST.get(required_key) == 'on'
            if required_value != field.required:
                field.required = required_value
                changed = True
            
            non_editable_key = f'{field_prefix}_non_editable'
            non_editable_value = request.POST.get(non_editable_key) == 'on'
            if non_editable_value != field.non_editable:
                field.non_editable = non_editable_value
                changed = True
            
            if changed:
                field.save()
                dataset_fields_updated = True
        
        if (config_fields_present and form_valid) or dataset_fields_updated:
            messages.success(request, 'Field configuration updated successfully.')
            return redirect('dataset_field_config', dataset_id=dataset.id)
        if config_fields_present and not form_valid:
            messages.error(request, 'Please correct the errors below.')
    
    all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset))
    
    return render(request, 'datasets/dataset_field_config.html', {
        'dataset': dataset,
        'form': form,
        'all_fields': all_fields,
    })


@login_required
def dataset_access_view(request, dataset_id):
    """Manage dataset access permissions"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Only dataset owner or superuser can manage access
    if dataset.owner != request.user and not request.user.is_superuser:
        return render(request, 'datasets/403.html', status=403)
    
    mapping_areas = list(dataset.mapping_areas.order_by('name'))
    
    if request.method == 'POST':
        # Handle bulk user access changes
        selected_user_ids = [
            int(uid) for uid in request.POST.getlist('shared_users') if uid.isdigit()
        ]
        selected_group_ids = [
            int(gid) for gid in request.POST.getlist('shared_groups') if gid.isdigit()
        ]
        selected_user_set = set(selected_user_ids)
        selected_group_set = set(selected_group_ids)
        
        # Update user access
        current_user_ids = set(dataset.shared_with.values_list('id', flat=True))
        # Add new users
        users_to_add = selected_user_set - current_user_ids
        if users_to_add:
            users_to_add_objects = User.objects.filter(id__in=users_to_add)
            dataset.shared_with.add(*users_to_add_objects)
            messages.success(request, f'Added {len(users_to_add_objects)} users to dataset access.')
        
        # Remove users
        users_to_remove = current_user_ids - selected_user_set
        if users_to_remove:
            users_to_remove_objects = User.objects.filter(id__in=users_to_remove)
            dataset.shared_with.remove(*users_to_remove_objects)
            messages.success(request, f'Removed {len(users_to_remove_objects)} users from dataset access.')
        
        # Update group access
        current_group_ids = set(dataset.shared_with_groups.values_list('id', flat=True))
        # Add new groups
        groups_to_add = selected_group_set - current_group_ids
        if groups_to_add:
            groups_to_add_objects = Group.objects.filter(id__in=groups_to_add)
            dataset.shared_with_groups.add(*groups_to_add_objects)
            messages.success(request, f'Added {len(groups_to_add_objects)} groups to dataset access.')
        
        # Remove groups
        groups_to_remove = current_group_ids - selected_group_set
        if groups_to_remove:
            groups_to_remove_objects = Group.objects.filter(id__in=groups_to_remove)
            dataset.shared_with_groups.remove(*groups_to_remove_objects)
            messages.success(request, f'Removed {len(groups_to_remove_objects)} groups from dataset access.')
        
        # If no changes were made
        # Handle mapping area restrictions
        if mapping_areas:
            valid_area_ids = set(area.id for area in mapping_areas)
            
            if selected_user_set:
                DatasetUserMappingArea.objects.filter(dataset=dataset).exclude(user_id__in=selected_user_set).delete()
            else:
                DatasetUserMappingArea.objects.filter(dataset=dataset).delete()
            
            for user_id in selected_user_ids:
                raw_area_ids = request.POST.getlist(f'user_mapping_areas_{user_id}')
                area_ids = [
                    int(area_id)
                    for area_id in raw_area_ids
                    if area_id.isdigit() and int(area_id) in valid_area_ids
                ]
                DatasetUserMappingArea.objects.filter(dataset=dataset, user_id=user_id).delete()
                if area_ids:
                    DatasetUserMappingArea.objects.bulk_create([
                        DatasetUserMappingArea(
                            dataset=dataset,
                            user_id=user_id,
                            mapping_area_id=area_id
                        ) for area_id in area_ids
                    ])
            
            if selected_group_set:
                DatasetGroupMappingArea.objects.filter(dataset=dataset).exclude(group_id__in=selected_group_set).delete()
            else:
                DatasetGroupMappingArea.objects.filter(dataset=dataset).delete()
            
            for group_id in selected_group_ids:
                raw_area_ids = request.POST.getlist(f'group_mapping_areas_{group_id}')
                area_ids = [
                    int(area_id)
                    for area_id in raw_area_ids
                    if area_id.isdigit() and int(area_id) in valid_area_ids
                ]
                DatasetGroupMappingArea.objects.filter(dataset=dataset, group_id=group_id).delete()
                if area_ids:
                    DatasetGroupMappingArea.objects.bulk_create([
                        DatasetGroupMappingArea(
                            dataset=dataset,
                            group_id=group_id,
                            mapping_area_id=area_id
                        ) for area_id in area_ids
                    ])
        else:
            DatasetUserMappingArea.objects.filter(dataset=dataset).delete()
            DatasetGroupMappingArea.objects.filter(dataset=dataset).delete()
        
        if not (users_to_add or users_to_remove or groups_to_add or groups_to_remove):
            messages.info(request, 'No changes were made to access settings.')
        
        return redirect('dataset_access', dataset_id=dataset.id)
    
    # Get all users and groups for selection
    all_users = list(User.objects.exclude(id=dataset.owner.id).order_by('username'))
    all_groups = list(Group.objects.order_by('name'))
    
    # Attach existing mapping area selections
    user_area_lookup = {}
    for relation in DatasetUserMappingArea.objects.filter(dataset=dataset):
        user_area_lookup.setdefault(relation.user_id, []).append(relation.mapping_area_id)
    
    group_area_lookup = {}
    for relation in DatasetGroupMappingArea.objects.filter(dataset=dataset):
        group_area_lookup.setdefault(relation.group_id, []).append(relation.mapping_area_id)
    
    for user in all_users:
        user.mapping_area_ids = user_area_lookup.get(user.id, [])
    
    for group in all_groups:
        group.mapping_area_ids = group_area_lookup.get(group.id, [])
    
    # Get currently shared users and groups
    shared_users = list(dataset.shared_with.values_list('id', flat=True))
    shared_groups = list(dataset.shared_with_groups.values_list('id', flat=True))
    
    return render(request, 'datasets/dataset_access.html', {
        'dataset': dataset,
        'all_users': all_users,
        'all_groups': all_groups,
        'shared_users': shared_users,
        'shared_groups': shared_groups,
        'mapping_areas': mapping_areas,
    })


@login_required
def dataset_data_input_view(request, dataset_id):
    """Data input view with map and entry editing"""
    dataset = get_object_or_404(DataSet, pk=dataset_id)
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)

    # Get all geometries for this dataset with their entries, respecting mapping area limits
    geometries_qs = DataGeometry.objects.filter(dataset=dataset).prefetch_related('entries')
    geometries = dataset.filter_geometries_for_user(geometries_qs, request.user)
    geometries = list(geometries)
    
    # Prepare map data
    map_data = []
    for geometry in geometries:
        map_point = {
            'id': geometry.id,
            'id_kurz': geometry.id_kurz,
            'address': geometry.address,
            'lat': geometry.geometry.y,
            'lng': geometry.geometry.x,
            'entries_count': geometry.entries.count(),
            'user': geometry.user.username if geometry.user else 'Unknown',
            'entries': []
        }
        
        # Add entry data for this geometry
        for entry in geometry.entries.all():
            entry_data = {
                'id': entry.id,
                'name': entry.name,
                'year': entry.year,
                'user': entry.user.username if entry.user else 'Unknown'
            }
            
            # Add dynamic field values
            for field in entry.fields.all():
                entry_data[field.field_name] = field.get_typed_value()
            
            map_point['entries'].append(entry_data)
        
        map_data.append(map_point)
    
    # Typology data is now handled at the field level, not dataset level
    typology_data = None
    
    # Get all enabled fields for this dataset
    all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))
    
    # If no enabled fields found, get all fields and enable them
    if not all_fields.exists():
        all_fields_qs = DatasetField.objects.filter(dataset=dataset)
        if all_fields_qs.exists():
            # Enable all fields
            all_fields_qs.update(enabled=True)
            # Re-query to get the updated fields
            all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))
    # If some enabled fields exist, respect that configuration as-is
    # Prepare fields data for JavaScript with typology choices
    fields_data = []
    for field in all_fields:
        field_data = {
            'id': field.id,
            'name': field.label,  # Use label for display
            'label': field.label,
            'field_type': field.field_type,
            'field_name': field.field_name,
            'required': field.required,
            'enabled': field.enabled,
            'non_editable': field.non_editable,
            'help_text': field.help_text or '',
            'choices': field.choices or '',
            'order': field.order,
            'typology_choices': field.get_choices_list(),
            'typology_category': field.typology_category or ''
        }
        fields_data.append(field_data)
    
    # Handle case where allow_multiple_entries field might not exist yet (migration not applied)
    try:
        allow_multiple_entries = dataset.allow_multiple_entries
    except AttributeError:
        allow_multiple_entries = False  # Default to False if field doesn't exist
    
    # Handle case where enable_mapping_areas field might not exist yet (migration not applied)
    try:
        enable_mapping_areas = dataset.enable_mapping_areas
    except AttributeError:
        enable_mapping_areas = False  # Default to False if field doesn't exist
    
    # Get all users for allocation dropdown (only for dataset owner or superuser)
    users_for_allocation = []
    if dataset.owner == request.user or request.user.is_superuser:
        users_for_allocation = User.objects.filter(is_active=True).order_by('username')
    
    map_default_lat = getattr(dataset, 'map_default_lat', None)
    map_default_lng = getattr(dataset, 'map_default_lng', None)
    map_default_zoom = getattr(dataset, 'map_default_zoom', None)

    # Collaborators restricted to mapping areas: show read-only outlines on the map (not for owner/superuser)
    show_collaborator_mapping_area_outlines = False
    if enable_mapping_areas:
        if not (request.user.is_superuser or dataset.owner == request.user):
            restricted_ids = dataset.get_user_mapping_area_ids(request.user)
            show_collaborator_mapping_area_outlines = bool(restricted_ids)

    return render(request, 'datasets/dataset_data_input.html', {
        'dataset': dataset,
        'geometries': geometries,
        'typology_data': typology_data,
        'all_fields': all_fields,
        'fields_data': fields_data,
        'enable_mapping_areas': enable_mapping_areas,
        'allow_multiple_entries': allow_multiple_entries,
        'users_for_allocation': users_for_allocation,
        'is_anonymous_data_input': False,
        'show_name_modal': False,
        'virtual_contributor_display_name': None,
        'map_default_lat': float(map_default_lat) if map_default_lat is not None else None,
        'map_default_lng': float(map_default_lng) if map_default_lng is not None else None,
        'map_default_zoom': int(map_default_zoom) if map_default_zoom is not None else None,
        'show_collaborator_mapping_area_outlines': show_collaborator_mapping_area_outlines,
    })


def register_virtual_user_view(request, dataset_id):
    """Create or update a virtual contributor for anonymous data input. No login required."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    dataset = get_object_or_404(DataSet, pk=dataset_id)
    token = request.session.get(f'anonymous_token_{dataset_id}')
    if not getattr(dataset, 'allow_anonymous_data_input', False) or not token or dataset.anonymous_access_token != token:
        return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
    import uuid as uuid_mod
    import json
    try:
        body = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        body = {}
    vc_uuid_str = body.get('uuid')
    display_name = (body.get('display_name') or '').strip()[:255]
    if not vc_uuid_str:
        return JsonResponse({'success': False, 'error': 'UUID is required'}, status=400)
    try:
        vc_uuid = uuid_mod.UUID(vc_uuid_str)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Invalid UUID'}, status=400)
    vc, created = VirtualContributor.objects.get_or_create(
        dataset=dataset,
        uuid=vc_uuid,
        defaults={'display_name': display_name}
    )
    if not created and display_name:
        vc.display_name = display_name
        vc.save(update_fields=['display_name', 'last_seen_at'])
    request.session[f'virtual_contributor_uuid_{dataset_id}'] = str(vc_uuid)
    request.session.modified = True
    return JsonResponse({'success': True, 'display_name': vc.display_name or 'Anonymous'})


def dataset_data_input_anonymous_view(request, dataset_id, token):
    """Data input view for anonymous access - virtual contributors see only their own geometries/entries."""
    dataset = get_object_or_404(DataSet, pk=dataset_id)
    if not getattr(dataset, 'allow_anonymous_data_input', False) or dataset.anonymous_access_token != token:
        return render(request, 'datasets/403.html', status=403)

    # Store token in session so API calls from this page can be validated
    request.session[f'anonymous_token_{dataset_id}'] = token
    request.session.modified = True

    # Get or resolve virtual contributor from session
    session_key = f'virtual_contributor_uuid_{dataset_id}'
    vc_uuid_str = request.session.get(session_key)
    virtual_contributor = None
    if vc_uuid_str:
        try:
            import uuid as uuid_mod
            vc_uuid = uuid_mod.UUID(vc_uuid_str)
            virtual_contributor = VirtualContributor.objects.filter(
                dataset=dataset, uuid=vc_uuid
            ).first()
        except (ValueError, TypeError):
            pass

    # Filter geometries: virtual contributors see only their own
    if virtual_contributor:
        geometries_qs = DataGeometry.objects.filter(
            dataset=dataset, virtual_contributor=virtual_contributor
        ).prefetch_related('entries')
        geometries = list(geometries_qs)
    else:
        geometries = []

    # Prepare map data (same structure as logged-in view)
    map_data = []
    for geometry in geometries:
        map_point = {
            'id': geometry.id,
            'id_kurz': geometry.id_kurz,
            'address': geometry.address,
            'lat': geometry.geometry.y,
            'lng': geometry.geometry.x,
            'entries_count': geometry.entries.count(),
            'user': geometry.get_creator_display_name(),
            'entries': []
        }
        for entry in geometry.entries.all():
            entry_data = {
                'id': entry.id,
                'name': entry.name,
                'year': entry.year,
                'user': entry.get_creator_display_name()
            }
            for field in entry.fields.all():
                entry_data[field.field_name] = field.get_typed_value()
            map_point['entries'].append(entry_data)
        map_data.append(map_point)

    all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))
    if not all_fields.exists():
        all_fields_qs = DatasetField.objects.filter(dataset=dataset)
        if all_fields_qs.exists():
            all_fields_qs.update(enabled=True)
            all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))

    fields_data = []
    for field in all_fields:
        field_data = {
            'id': field.id,
            'name': field.label,
            'label': field.label,
            'field_type': field.field_type,
            'field_name': field.field_name,
            'required': field.required,
            'enabled': field.enabled,
            'non_editable': field.non_editable,
            'help_text': field.help_text or '',
            'choices': field.choices or '',
            'order': field.order,
            'typology_choices': field.get_choices_list(),
            'typology_category': field.typology_category or ''
        }
        fields_data.append(field_data)

    allow_multiple_entries = getattr(dataset, 'allow_multiple_entries', False)
    enable_mapping_areas = False  # Hide for anonymous users

    virtual_contributor_display_name = virtual_contributor.display_name if virtual_contributor and virtual_contributor.display_name else None
    map_default_lat = getattr(dataset, 'map_default_lat', None)
    map_default_lng = getattr(dataset, 'map_default_lng', None)
    map_default_zoom = getattr(dataset, 'map_default_zoom', None)
    
    return render(request, 'datasets/dataset_data_input.html', {
        'dataset': dataset,
        'geometries': geometries,
        'typology_data': None,
        'all_fields': all_fields,
        'fields_data': fields_data,
        'enable_mapping_areas': enable_mapping_areas,
        'allow_multiple_entries': allow_multiple_entries,
        'users_for_allocation': [],
        'is_anonymous_data_input': True,
        'anonymous_access_token': token,
        'show_name_modal': virtual_contributor is None,
        'virtual_contributor_display_name': virtual_contributor_display_name,
        'map_default_lat': float(map_default_lat) if map_default_lat is not None else None,
        'map_default_lng': float(map_default_lng) if map_default_lng is not None else None,
        'map_default_zoom': int(map_default_zoom) if map_default_zoom is not None else None,
        'show_collaborator_mapping_area_outlines': False,
    })


@login_required
def dataset_entries_table_view(request, dataset_id):
    """Display all dataset entries in a table format"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Check if user has access to this dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    
    # Get all entries for this dataset
    entries = DataEntry.objects.filter(geometry__dataset=dataset).select_related('geometry', 'user').prefetch_related('fields')

    mapping_area_ids = dataset.get_user_mapping_area_ids(request.user)
    if mapping_area_ids is not None:
        restricted_geometries = dataset.filter_geometries_for_user(
            DataGeometry.objects.filter(dataset=dataset),
            request.user,
        )
        entries = entries.filter(geometry__in=restricted_geometries)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        entries = entries.filter(
            Q(name__icontains=search_query) |
            Q(geometry__id_kurz__icontains=search_query) |
            Q(geometry__address__icontains=search_query)
        )
    
    # Get all enabled fields for this dataset (exclude headline - display-only, no data)
    all_fields = DatasetField.order_fields(
        DatasetField.objects.filter(dataset=dataset, enabled=True).exclude(field_type='headline')
    )
    
    # Sorting
    sort_by = request.GET.get('sort', 'id_kurz')
    reverse = request.GET.get('order', 'asc') == 'desc'
    
    if sort_by == 'id_kurz' or sort_by == 'geometry':
        entries = entries.order_by('geometry__id_kurz')
    elif sort_by == 'user':
        entries = entries.order_by('user__username')
    elif sort_by.startswith('field_'):
        # Sort by custom field
        field_name = sort_by.replace('field_', '')
        # This is a simplified approach - in a real scenario you might need more complex sorting
        entries = entries.order_by('geometry__id_kurz')
    else:
        entries = entries.order_by('geometry__id_kurz')
    
    if reverse:
        entries = entries.reverse()
    
    # Pagination
    paginator = Paginator(entries, 25)  # Show 25 entries per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'datasets/dataset_entries_table.html', {
        'dataset': dataset,
        'page_obj': page_obj,
        'all_fields': all_fields,
        'search_query': search_query,
        'sort_by': sort_by,
        'order': 'desc' if reverse else 'asc'
    })


@login_required
def dataset_fields_view(request, dataset_id):
    """API endpoint to get dataset fields"""
    try:
        dataset = get_object_or_404(DataSet, pk=dataset_id)
        if not dataset.can_access(request.user):
            return JsonResponse({'error': 'Access denied'}, status=403)

        # Get all enabled fields for this dataset
        all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))
        
        # If no enabled fields found, get all fields and enable them
        if not all_fields.exists():
            all_fields_qs = DatasetField.objects.filter(dataset=dataset)
            if all_fields_qs.exists():
                # Enable all fields
                all_fields_qs.update(enabled=True)
                # Re-query to get the updated fields
                all_fields = DatasetField.order_fields(DatasetField.objects.filter(dataset=dataset, enabled=True))
        # If some enabled fields exist, respect that configuration as-is
        
        # Prepare fields data for JavaScript
        fields_data = []
        for field in all_fields:
            field_data = {
                'id': field.id,
                'name': field.label,
                'label': field.label,
                'field_type': field.field_type,
                'field_name': field.field_name,
                'required': field.required,
                'enabled': field.enabled,
                'non_editable': field.non_editable,
                'help_text': field.help_text or '',
                'choices': field.choices or '',
                'order': field.order,
                'typology_choices': field.get_choices_list(),
                'typology_category': field.typology_category or ''
            }
            fields_data.append(field_data)
        
        return JsonResponse({'fields': fields_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def dataset_map_data_view(request, dataset_id):
    """API endpoint to get lightweight map data for a dataset (coordinates only)"""
    try:
        dataset = get_object_or_404(DataSet, pk=dataset_id)
        user, vc = resolve_data_input_actor(request, dataset, require_virtual_contributor=False)
        if user is None and vc is None:
            return JsonResponse({'error': 'Access denied'}, status=403)
        if vc == 'pending':
            return JsonResponse({'map_data': []})

        # Get map bounds from request parameters
        bounds = request.GET.get('bounds')
        if bounds:
            try:
                from django.contrib.gis.geos import Polygon
                south, west, north, east = map(float, bounds.split(','))
                bbox = Polygon.from_bbox((west, south, east, north))
                geometries = DataGeometry.objects.filter(
                    dataset=dataset,
                    geometry__within=bbox
                ).select_related('user', 'virtual_contributor')
            except (ValueError, TypeError):
                geometries = DataGeometry.objects.filter(dataset=dataset).select_related('user', 'virtual_contributor')
        else:
            geometries = DataGeometry.objects.filter(dataset=dataset).select_related('user', 'virtual_contributor')

        if user:
            geometries = dataset.filter_geometries_for_user(geometries, user)
        else:
            geometries = geometries.filter(virtual_contributor=vc)

        map_data = []
        for geometry in geometries:
            try:
                map_point = {
                    'id': geometry.id,
                    'id_kurz': geometry.id_kurz,
                    'address': geometry.address,
                    'lat': geometry.geometry.y,
                    'lng': geometry.geometry.x,
                    'user': geometry.get_creator_display_name()
                }
                map_data.append(map_point)
            except Exception:
                continue

        return JsonResponse({'map_data': map_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def dataset_clear_data_view(request, dataset_id):
    """Clear all geometry points and data entries from a dataset"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Only dataset owner or superuser can clear data
    if dataset.owner != request.user and not request.user.is_superuser:
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        # Delete all geometries and their related data
        geometries_count = DataGeometry.objects.filter(dataset=dataset).count()
        DataGeometry.objects.filter(dataset=dataset).delete()
        
        messages.success(request, f'Cleared {geometries_count} geometry points and all related data from dataset "{dataset.name}".')
        return redirect('dataset_detail', dataset_id=dataset.id)
    
    return render(request, 'datasets/dataset_clear_data.html', {
        'dataset': dataset
    })


@login_required
def custom_field_create_view(request, dataset_id):
    """Create a new custom field for a dataset"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Check if user has access to this dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        form = DatasetFieldForm(request.POST, user=request.user, dataset=dataset)
        if form.is_valid():
            field = form.save(commit=False)
            field.dataset = dataset
            field.save()
            messages.success(request, f'Field "{field.label}" created successfully!')
            return redirect('dataset_detail', dataset_id=dataset.id)
        # Form is invalid - will be re-rendered with errors below
    else:
        form = DatasetFieldForm(user=request.user, dataset=dataset)
    
    # Calculate the next available order number (max order + 1, or 0 if no fields exist)
    max_order = DatasetField.objects.filter(dataset=dataset).aggregate(
        max_order=Max('order')
    )['max_order']
    next_order = (max_order + 1) if max_order is not None else 0
    
    return render(request, 'datasets/custom_field_form.html', {
        'dataset': dataset,
        'form': form,
        'title': 'Create Custom Field',
        'typology_categories': _get_typology_categories_map(request.user),
        'next_order': next_order
    })


@login_required
def custom_field_edit_view(request, dataset_id, field_id):
    """Edit a custom field for a dataset"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    field = get_object_or_404(DatasetField, id=field_id, dataset=dataset)
    
    # Check if user has access to this dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        form = DatasetFieldForm(request.POST, instance=field, user=request.user, dataset=dataset)
        if form.is_valid():
            form.save()
            messages.success(request, f'Field "{field.label}" updated successfully!')
            return redirect('dataset_detail', dataset_id=dataset.id)
        # Form is invalid - will be re-rendered with errors below
    else:
        form = DatasetFieldForm(instance=field, user=request.user, dataset=dataset)
    
    # Calculate the next available order number (max order + 1, or 0 if no fields exist)
    max_order = DatasetField.objects.filter(dataset=dataset).aggregate(
        max_order=Max('order')
    )['max_order']
    next_order = (max_order + 1) if max_order is not None else 0
    
    return render(request, 'datasets/custom_field_form.html', {
        'dataset': dataset,
        'field': field,
        'form': form,
        'title': 'Edit Custom Field',
        'typology_categories': _get_typology_categories_map(request.user),
        'next_order': next_order
    })


@login_required
def custom_field_delete_view(request, dataset_id, field_id):
    """Delete a custom field for a dataset"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    field = get_object_or_404(DatasetField, id=field_id, dataset=dataset)
    
    # Check if user has access to this dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        field_name = field.label
        field.delete()
        messages.success(request, f'Field "{field_name}" deleted successfully!')
        return redirect('dataset_detail', dataset_id=dataset.id)
    
    return render(request, 'datasets/custom_field_delete.html', {
        'dataset': dataset,
        'field': field,
        'custom_field': field  # Backward compatibility for tests/templates expecting this key
    })


@login_required
def dataset_transfer_ownership_view(request, dataset_id):
    """Transfer ownership of a dataset to another user"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    
    # Only the current owner or superuser can transfer ownership
    if dataset.owner != request.user and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to transfer ownership of this dataset.')
        return redirect('dataset_detail', dataset_id=dataset.id)
    
    if request.method == 'POST':
        form = TransferOwnershipForm(request.POST, current_owner=dataset.owner)
        if form.is_valid():
            new_owner = form.cleaned_data['new_owner']
            old_owner = dataset.owner
            
            # Transfer ownership
            dataset.owner = new_owner
            dataset.save()
            
            messages.success(request, f'Ownership of "{dataset.name}" has been transferred to {new_owner.username}.')
            return redirect('dataset_detail', dataset_id=dataset.id)
    else:
        form = TransferOwnershipForm(current_owner=dataset.owner)
    
    return render(request, 'datasets/dataset_transfer_ownership.html', {
        'dataset': dataset,
        'form': form
    })
