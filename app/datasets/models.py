import logging
import uuid

from django.contrib.auth.models import Group, User
from django.contrib.gis.db import models as gis_models
from django.contrib.gis.geos import GEOSException, Point
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=255)
    target = models.CharField(max_length=255, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.timestamp}: {self.user} - {self.action} - {self.target}"


class DataSet(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_datasets')
    shared_with = models.ManyToManyField(User, related_name='shared_datasets', blank=True)
    shared_with_groups = models.ManyToManyField('auth.Group', related_name='shared_datasets', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_public = models.BooleanField(default=False)
    allow_multiple_entries = models.BooleanField(default=False, help_text="Allow multiple data entries per geometry point")
    enable_mapping_areas = models.BooleanField(default=False, help_text="Enable mapping areas functionality for this dataset")
    allow_anonymous_data_input = models.BooleanField(default=False, help_text="Allow data input without login via shareable URL")
    anonymous_access_token = models.CharField(max_length=64, unique=True, null=True, blank=True, help_text="Secret token for anonymous access URL")
    map_default_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Default map center latitude when opening data input")
    map_default_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Default map center longitude when opening data input")
    map_default_zoom = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Default map zoom level (1–20) when opening data input",
        validators=[MinValueValidator(1), MaxValueValidator(20)],
    )

    def __str__(self):
        return self.name

    def can_access(self, user):
        """Check if a user can access this dataset"""
        # Superusers have access to all datasets
        if user.is_superuser:
            return True
        if self.is_public:
            return True
        if user == self.owner:
            return True
        if user in self.shared_with.all():
            return True
        # Check if user is in any of the shared groups
        if self.shared_with_groups.filter(user=user).exists():
            return True
        return False

    def get_user_mapping_area_ids(self, user):
        """
        Return a list of mapping area IDs that restrict this user's access,
        or None if there are no restrictions (full dataset access).

        Areas come from: per-user limits on dataset access, per-group limits,
        and users listed as allocated on a mapping area (polygon allocation).
        """
        # Superusers and owners have full access (no restrictions)
        if user.is_superuser or user == self.owner:
            return None

        if not self.mapping_areas.exists():
            return None

        direct_ids = list(
            self.user_mapping_area_limits.filter(user=user).values_list('mapping_area_id', flat=True)
        )

        group_ids = list(user.groups.values_list('id', flat=True))
        group_area_ids = list(
            self.group_mapping_area_limits.filter(group_id__in=group_ids).values_list('mapping_area_id', flat=True)
        ) if group_ids else []

        # Collaborators allocated to an area via the mapping-area UI see all data in that polygon
        allocated_ids = list(
            self.mapping_areas.filter(allocated_users=user).values_list('id', flat=True)
        )

        combined = set(direct_ids) | set(group_area_ids) | set(allocated_ids)
        return list(combined) if combined else None

    def filter_geometries_for_user(self, geometries_qs, user):
        """
        Apply mapping area restrictions to a geometry queryset for the given user.
        """
        allowed_ids = self.get_user_mapping_area_ids(user)
        if allowed_ids is None:
            return geometries_qs

        if not allowed_ids:
            return geometries_qs.none()

        allowed_areas = list(self.mapping_areas.filter(id__in=allowed_ids))
        if not allowed_areas:
            return geometries_qs.none()

        condition = Q()
        for area in allowed_areas:
            condition |= Q(geometry__within=area.geometry)

        if condition:
            return geometries_qs.filter(condition)
        return geometries_qs.none()

    def ensure_anonymous_access_token(self):
        """Generate anonymous_access_token if allow_anonymous_data_input is True and token is missing."""
        if self.allow_anonymous_data_input and not self.anonymous_access_token:
            import secrets
            self.anonymous_access_token = secrets.token_urlsafe(48)
            self.save(update_fields=['anonymous_access_token'])
        return self.anonymous_access_token

    def user_has_geometry_access(self, user, geometry_obj):
        """
        Check whether a user is allowed to access the given geometry, considering mapping area limits.
        """
        allowed_ids = self.get_user_mapping_area_ids(user)
        if allowed_ids is None:
            return True
        if not allowed_ids:
            return False

        return self.mapping_areas.filter(
            id__in=allowed_ids,
            geometry__covers=geometry_obj.geometry
        ).exists()

    class Meta:
        ordering = ['-created_at']


class VirtualContributor(models.Model):
    """Anonymous contributor for datasets with allow_anonymous_data_input. Tracks contributions without login."""
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    display_name = models.CharField(max_length=255, blank=True)
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name='virtual_contributors')
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.display_name or 'Anonymous'} ({self.uuid})"

    class Meta:
        ordering = ['-created_at']


class DataGeometry(models.Model):
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name='geometries')
    address = models.CharField(max_length=500)
    geometry = gis_models.PointField(srid=4326)  # WGS84 coordinate system
    id_kurz = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_geometries')
    virtual_contributor = models.ForeignKey('VirtualContributor', on_delete=models.CASCADE, null=True, blank=True, related_name='created_geometries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id_kurz} - {self.address}"

    def get_creator_display_name(self):
        """Return display name of the creator (user or virtual contributor)."""
        if self.user:
            return self.user.username
        if self.virtual_contributor:
            return self.virtual_contributor.display_name or 'Anonymous'
        return 'Unknown'

    def save(self, *args, **kwargs):
        # Ensure the geometry is properly set if not already done
        if not self.geometry:
            # Default to a point if no geometry is provided
            self.geometry = Point(0, 0, srid=4326)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Data Geometries"
        constraints = [
            models.UniqueConstraint(fields=['dataset', 'id_kurz'], condition=models.Q(virtual_contributor__isnull=True), name='unique_user_geometry'),
            models.UniqueConstraint(fields=['dataset', 'id_kurz', 'virtual_contributor'], condition=models.Q(virtual_contributor__isnull=False), name='unique_vc_geometry'),
        ]


class DataEntry(models.Model):
    geometry = models.ForeignKey(DataGeometry, on_delete=models.CASCADE, related_name='entries')
    name = models.CharField(max_length=255, blank=True, null=True)
    year = models.IntegerField(blank=True, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_entries')
    virtual_contributor = models.ForeignKey('VirtualContributor', on_delete=models.CASCADE, null=True, blank=True, related_name='created_entries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        year_str = f" ({self.year})" if self.year else ""
        name_str = self.name or "Unnamed Entry"
        return f"{name_str} - {self.geometry.id_kurz}{year_str}"

    def get_creator_display_name(self):
        """Return display name of the creator (user or virtual contributor)."""
        if self.user:
            return self.user.username
        if self.virtual_contributor:
            return self.virtual_contributor.display_name or 'Anonymous'
        return 'Unknown'

    def get_field_value(self, field_name):
        """Get the value of a specific field for this entry"""
        try:
            field = self.fields.get(field_name=field_name)
            return field.value
        except DataEntryField.DoesNotExist:
            return None

    def set_field_value(self, field_name, value, field_type='text'):
        """Set the value of a specific field for this entry"""
        field, created = self.fields.get_or_create(
            field_name=field_name,
            defaults={'field_type': field_type, 'value': value}
        )
        if not created:
            field.value = value
            field.field_type = field_type
            field.save()
        return field

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Data Entries"


class DataEntryField(models.Model):
    """Dynamic field values for data entries - represents CSV columns"""
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('textarea', 'Large Text'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('choice', 'Choice'),
        ('multiple_choice', 'Multiple Choice'),
    ]
    
    entry = models.ForeignKey(DataEntry, on_delete=models.CASCADE, related_name='fields')
    field_name = models.CharField(max_length=100, help_text="Field name (column name from CSV)")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    value = models.TextField(blank=True, null=True, help_text="Field value")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.entry.geometry.id_kurz} - {self.field_name}: {self.value}"

    def get_typed_value(self):
        """Get the value converted to the appropriate Python type"""
        if not self.value:
            if self.field_type == 'multiple_choice':
                return []
            return None
            
        try:
            if self.field_type == 'integer':
                return int(self.value)
            elif self.field_type == 'decimal':
                return float(self.value)
            elif self.field_type == 'boolean':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.field_type == 'date':
                from datetime import datetime
                return datetime.strptime(self.value, '%Y-%m-%d').date()
            elif self.field_type == 'multiple_choice':
                import json
                try:
                    # Try parsing as JSON array
                    parsed = json.loads(self.value)
                    if isinstance(parsed, list):
                        return [str(v) for v in parsed]
                    else:
                        return [str(parsed)]
                except (json.JSONDecodeError, TypeError):
                    # Fallback: treat as comma-separated string
                    if ',' in str(self.value):
                        return [v.strip() for v in str(self.value).split(',') if v.strip()]
                    elif str(self.value).strip():
                        return [str(self.value).strip()]
                    else:
                        return []
            else:  # text, textarea, choice
                return str(self.value)
        except (ValueError, TypeError):
            if self.field_type == 'multiple_choice':
                return []
            return self.value

    class Meta:
        ordering = ['field_name']
        verbose_name = "Data Entry Field"
        verbose_name_plural = "Data Entry Fields"
        unique_together = ['entry', 'field_name']


class DataEntryFile(models.Model):
    entry = models.ForeignKey(DataEntry, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=50)  # e.g., 'image/jpeg', 'image/png'
    file_size = models.IntegerField()  # Size in bytes
    upload_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_files')
    upload_date = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.filename} - {self.entry.name}"

    def get_file_extension(self):
        """Get file extension from filename"""
        return self.filename.split('.')[-1].lower() if '.' in self.filename else ''

    def is_image(self):
        """Check if file is an image"""
        return self.file_type.startswith('image/')

    class Meta:
        ordering = ['-upload_date']
        verbose_name_plural = "Data Entry Files"


class Typology(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_typologies')
    is_public = models.BooleanField(default=False, help_text="Make this typology visible to all users")
    
    def __str__(self):
        return self.name
    
    def can_access(self, user):
        """Check if a user can access this typology"""
        # Superusers have access to all typologies
        if user.is_superuser:
            return True
        if self.is_public:
            return True
        if user == self.created_by:
            return True
        return False
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Typologies"


class TypologyEntry(models.Model):
    typology = models.ForeignKey(Typology, on_delete=models.CASCADE, related_name='entries')
    code = models.IntegerField()
    category = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.category})"
    
    class Meta:
        ordering = ['code']
        verbose_name_plural = "Typology Entries"
        unique_together = ['typology', 'code']


class DatasetFieldConfig(models.Model):
    """Configuration for dataset fields - allows customization of field names and visibility per dataset"""
    dataset = models.OneToOneField(DataSet, on_delete=models.CASCADE, related_name='field_config')
    
    # Usage Code fields
    usage_code1_label = models.CharField(max_length=100, default='Usage Code 1')
    usage_code1_enabled = models.BooleanField(default=True)
    usage_code2_label = models.CharField(max_length=100, default='Usage Code 2')
    usage_code2_enabled = models.BooleanField(default=True)
    usage_code3_label = models.CharField(max_length=100, default='Usage Code 3')
    usage_code3_enabled = models.BooleanField(default=True)
    
    # Category fields
    cat_inno_label = models.CharField(max_length=100, default='Category Innovation')
    cat_inno_enabled = models.BooleanField(default=True)
    cat_wert_label = models.CharField(max_length=100, default='Category Value')
    cat_wert_enabled = models.BooleanField(default=True)
    cat_fili_label = models.CharField(max_length=100, default='Category Filial')
    cat_fili_enabled = models.BooleanField(default=True)
    
    # Year field
    year_label = models.CharField(max_length=100, default='Year')
    year_enabled = models.BooleanField(default=True)
    
    # Entry name field
    name_label = models.CharField(max_length=100, default='Entry Name')
    name_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Field Config for {self.dataset.name}"
    
    class Meta:
        verbose_name = "Dataset Field Configuration"
        verbose_name_plural = "Dataset Field Configurations"


class DatasetField(models.Model):
    """Field configuration for datasets - defines which CSV columns are shown in data input"""
    FIELD_TYPE_CHOICES = [
        ('text', 'Text'),
        ('textarea', 'Large Text'),
        ('integer', 'Integer'),
        ('decimal', 'Decimal'),
        ('boolean', 'Boolean'),
        ('date', 'Date'),
        ('choice', 'Choice'),
        ('headline', 'Headline'),
        ('multiple_choice', 'Multiple Choice'),
    ]
    
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name='dataset_fields')
    field_name = models.CharField(max_length=100, help_text="Field name (CSV column name)")
    label = models.CharField(max_length=100, help_text="Display label for the field")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES, default='text')
    required = models.BooleanField(default=False)
    enabled = models.BooleanField(default=True)
    non_editable = models.BooleanField(default=False, help_text="If enabled, this field cannot be edited in data entry forms")
    help_text = models.TextField(blank=True, null=True, help_text="Help text to display to users")
    choices = models.TextField(blank=True, null=True, help_text="Comma-separated choices for choice fields")
    order = models.IntegerField(default=0, help_text="Display order (0 = first, -1 = last)")
    is_coordinate_field = models.BooleanField(default=False, help_text="Whether this field represents coordinates")
    is_id_field = models.BooleanField(default=False, help_text="Whether this field is the unique identifier")
    is_address_field = models.BooleanField(default=False, help_text="Whether this field represents the address")
    typology = models.ForeignKey(Typology, on_delete=models.SET_NULL, null=True, blank=True, help_text="Typology to use for this field (for choice fields)")
    typology_category = models.CharField(max_length=100, blank=True, null=True, help_text="Limit typology options to a specific category")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.label} ({self.dataset.name})"
    
    def get_choices_list(self):
        """Get choices as a list for choice and multiple_choice fields"""
        # If typology is assigned, use typology entries regardless of stored field_type
        if self.typology:
            entries = self.typology.entries.all()
            if self.typology_category:
                entries = entries.filter(category=self.typology_category)
            return [
                {'value': str(entry.code), 'label': f"{entry.code} - {entry.name}"}
                for entry in entries.order_by('code')
            ]
        # Otherwise, fall back to manual choices for choice and multiple_choice fields
        if self.field_type in ('choice', 'multiple_choice') and self.choices:
            return [choice.strip() for choice in self.choices.split(',') if choice.strip()]
        return []
    
    class Meta:
        ordering = ['order', 'field_name']
        verbose_name = "Dataset Field"
        verbose_name_plural = "Dataset Fields"
        unique_together = ['dataset', 'field_name']  # Field names must be unique per dataset
    
    @staticmethod
    def order_fields(queryset):
        """Order queryset treating negative order values as last (appear after all positive values)"""
        from django.db.models import Case, When, Value, IntegerField
        return queryset.annotate(
            sort_order=Case(
                When(order__lt=0, then=Value(999999)),  # Treat negative as very large number
                default='order',
                output_field=IntegerField()
            )
        ).order_by('sort_order', 'field_name')


class ExportTask(models.Model):
    """Model to track file export tasks"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name='export_tasks')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='export_tasks')
    task_id = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    file_path = models.CharField(max_length=500, blank=True, null=True)
    file_size = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Export parameters
    file_types = models.JSONField(default=list)
    date_from = models.DateField(null=True, blank=True)
    date_to = models.DateField(null=True, blank=True)
    organize_by = models.CharField(max_length=20, default='geometry')
    include_metadata = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Export Task {self.task_id} - {self.dataset.name}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Export Task"
        verbose_name_plural = "Export Tasks"


class MappingArea(models.Model):
    """Mapping area as one or more polygons (GeoJSON Polygon or MultiPolygon)."""
    dataset = models.ForeignKey(DataSet, on_delete=models.CASCADE, related_name='mapping_areas')
    name = models.CharField(max_length=255)
    geometry = gis_models.MultiPolygonField(srid=4326)  # WGS84; single-part areas use one polygon
    allocated_users = models.ManyToManyField(User, related_name='allocated_mapping_areas', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_mapping_areas')
    
    def __str__(self):
        return f"{self.name} ({self.dataset.name})"
    
    def get_point_count(self):
        """Get the number of geometry points inside this polygon"""
        if not self.geometry:
            return 0
        try:
            return self.dataset.geometries.filter(geometry__within=self.geometry).count()
        except Exception:  # pragma: no cover - defensive
            logging.getLogger(__name__).exception(
                "Failed to count geometries within mapping area %s (dataset %s)",
                self.id,
                self.dataset_id,
            )
            return 0
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Mapping Areas" 


class DatasetUserMappingArea(models.Model):
    """Limit a user's dataset access to specific mapping areas."""
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
        related_name='user_mapping_area_limits'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dataset_mapping_area_limits'
    )
    mapping_area = models.ForeignKey(
        MappingArea,
        on_delete=models.CASCADE,
        related_name='user_access_limits'
    )

    class Meta:
        unique_together = ('dataset', 'user', 'mapping_area')
        verbose_name = "Dataset User Mapping Area"
        verbose_name_plural = "Dataset User Mapping Areas"


class DatasetGroupMappingArea(models.Model):
    """Limit a group's dataset access to specific mapping areas."""
    dataset = models.ForeignKey(
        DataSet,
        on_delete=models.CASCADE,
        related_name='group_mapping_area_limits'
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='dataset_mapping_area_limits'
    )
    mapping_area = models.ForeignKey(
        MappingArea,
        on_delete=models.CASCADE,
        related_name='group_access_limits'
    )

    class Meta:
        unique_together = ('dataset', 'group', 'mapping_area')
        verbose_name = "Dataset Group Mapping Area"
        verbose_name_plural = "Dataset Group Mapping Areas"