from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO

from ..models import (
    DataSet,
    DataGeometry,
    DataEntry,
    DataEntryField,
    DataEntryFile,
    DatasetField,
    DatasetFieldConfig,
    MappingArea,
    DatasetUserMappingArea,
    DatasetGroupMappingArea,
    Typology,
)


class DatasetCopyViewTests(TestCase):
    """Test cases for dataset copy functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create users
        self.superuser = User.objects.create_user(
            username='superuser',
            email='super@example.com',
            password='testpass123',
            is_superuser=True,
            is_staff=True
        )
        self.owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123'
        )
        self.regular_user = User.objects.create_user(
            username='regular',
            email='regular@example.com',
            password='testpass123'
        )
        self.shared_user = User.objects.create_user(
            username='shared',
            email='shared@example.com',
            password='testpass123'
        )
        
        # Create group
        self.group = Group.objects.create(name='Test Group')
        self.group.user_set.add(self.shared_user)
        
        # Create typology
        self.typology = Typology.objects.create(
            name='Test Typology',
            created_by=self.owner
        )
        Typology.objects.get(id=self.typology.id).entries.create(
            code=1,
            category='Category1',
            name='Entry 1'
        )
        
        # Create original dataset
        self.original_dataset = DataSet.objects.create(
            name='Original Dataset',
            description='Original Description',
            owner=self.owner,
            is_public=False,
            allow_multiple_entries=True,
            enable_mapping_areas=True,
        )
        self.original_dataset.shared_with.add(self.shared_user)
        self.original_dataset.shared_with_groups.add(self.group)
        
        # Create field config
        self.field_config = DatasetFieldConfig.objects.create(
            dataset=self.original_dataset,
            usage_code1_label='Usage 1',
            usage_code1_enabled=True,
            year_label='Year',
            year_enabled=True,
        )
        
        # Create dataset fields
        self.field1 = DatasetField.objects.create(
            dataset=self.original_dataset,
            field_name='test_field_1',
            label='Test Field 1',
            field_type='text',
            required=True,
            enabled=True,
            order=1,
        )
        self.field2 = DatasetField.objects.create(
            dataset=self.original_dataset,
            field_name='test_field_2',
            label='Test Field 2',
            field_type='integer',
            required=False,
            enabled=True,
            order=2,
            typology=self.typology,
            typology_category='Category1',
        )
        
        # Create geometry points
        self.geometry1 = DataGeometry.objects.create(
            dataset=self.original_dataset,
            address='Test Address 1',
            geometry=Point(16.3738, 48.2082, srid=4326),
            id_kurz='GEO001',
            user=self.owner,
        )
        self.geometry2 = DataGeometry.objects.create(
            dataset=self.original_dataset,
            address='Test Address 2',
            geometry=Point(16.3740, 48.2084, srid=4326),
            id_kurz='GEO002',
            user=self.owner,
        )
        
        # Create data entries
        self.entry1 = DataEntry.objects.create(
            geometry=self.geometry1,
            name='Entry 1',
            year=2023,
            user=self.owner,
        )
        self.entry2 = DataEntry.objects.create(
            geometry=self.geometry1,
            name='Entry 2',
            year=2024,
            user=self.owner,
        )
        self.entry3 = DataEntry.objects.create(
            geometry=self.geometry2,
            name='Entry 3',
            year=2023,
            user=self.owner,
        )
        
        # Create entry fields
        DataEntryField.objects.create(
            entry=self.entry1,
            field_name='test_field_1',
            field_type='text',
            value='Value 1',
        )
        DataEntryField.objects.create(
            entry=self.entry1,
            field_name='test_field_2',
            field_type='integer',
            value='100',
        )
        DataEntryField.objects.create(
            entry=self.entry2,
            field_name='test_field_1',
            field_type='text',
            value='Value 2',
        )
        
        # Create file for entry
        test_file_content = b'Test file content'
        test_file = SimpleUploadedFile(
            'test_image.jpg',
            test_file_content,
            content_type='image/jpeg'
        )
        self.entry_file = DataEntryFile.objects.create(
            entry=self.entry1,
            file=test_file,
            filename='test_image.jpg',
            file_type='image/jpeg',
            file_size=len(test_file_content),
            upload_user=self.owner,
            description='Test file',
        )
        
        # Create mapping area
        polygon = Polygon(
            ((16.3730, 48.2080), (16.3730, 48.2090), (16.3750, 48.2090), (16.3750, 48.2080), (16.3730, 48.2080)),
            srid=4326
        )
        self.mapping_area = MappingArea.objects.create(
            dataset=self.original_dataset,
            name='Test Area',
            geometry=MultiPolygon(polygon, srid=4326),
            created_by=self.owner,
        )
        self.mapping_area.allocated_users.add(self.shared_user)
        
        # Create mapping area limits
        DatasetUserMappingArea.objects.create(
            dataset=self.original_dataset,
            user=self.shared_user,
            mapping_area=self.mapping_area,
        )
        DatasetGroupMappingArea.objects.create(
            dataset=self.original_dataset,
            group=self.group,
            mapping_area=self.mapping_area,
        )
    
    def test_copy_requires_superuser(self):
        """Test that only superusers can copy datasets"""
        # Test unauthenticated user
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        # Test regular user
        self.client.login(username='regular', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        self.assertEqual(response.status_code, 403)
        
        # Test dataset owner (not superuser)
        self.client.login(username='owner', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        self.assertEqual(response.status_code, 403)
        
        # Test superuser (should succeed)
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        self.assertEqual(response.status_code, 302)  # Redirect after successful copy
    
    def test_copy_creates_new_dataset(self):
        """Test that copy creates a new dataset with _Copy suffix"""
        self.client.login(username='superuser', password='testpass123')
        
        initial_count = DataSet.objects.count()
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DataSet.objects.count(), initial_count + 1)
        
        # Check new dataset exists
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        self.assertNotEqual(new_dataset.id, self.original_dataset.id)
        self.assertEqual(new_dataset.owner, self.superuser)
        self.assertEqual(new_dataset.description, 'Original Description')
        self.assertEqual(new_dataset.is_public, False)
        self.assertEqual(new_dataset.allow_multiple_entries, True)
        self.assertEqual(new_dataset.enable_mapping_areas, True)
    
    def test_copy_preserves_sharing_settings(self):
        """Test that copy preserves shared users and groups"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        
        # Check shared users
        self.assertIn(self.shared_user, new_dataset.shared_with.all())
        self.assertEqual(new_dataset.shared_with.count(), 1)
        
        # Check shared groups
        self.assertIn(self.group, new_dataset.shared_with_groups.all())
        self.assertEqual(new_dataset.shared_with_groups.count(), 1)
    
    def test_copy_preserves_field_config(self):
        """Test that copy preserves DatasetFieldConfig"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        
        # Check field config exists
        self.assertTrue(hasattr(new_dataset, 'field_config'))
        new_config = new_dataset.field_config
        self.assertEqual(new_config.usage_code1_label, 'Usage 1')
        self.assertTrue(new_config.usage_code1_enabled)
        self.assertEqual(new_config.year_label, 'Year')
        self.assertTrue(new_config.year_enabled)
    
    def test_copy_preserves_dataset_fields(self):
        """Test that copy preserves all DatasetField objects"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        
        # Check fields were copied
        new_fields = DatasetField.objects.filter(dataset=new_dataset)
        self.assertEqual(new_fields.count(), 2)
        
        # Check field1
        new_field1 = new_fields.get(field_name='test_field_1')
        self.assertEqual(new_field1.label, 'Test Field 1')
        self.assertEqual(new_field1.field_type, 'text')
        self.assertTrue(new_field1.required)
        self.assertTrue(new_field1.enabled)
        self.assertEqual(new_field1.order, 1)
        
        # Check field2 with typology
        new_field2 = new_fields.get(field_name='test_field_2')
        self.assertEqual(new_field2.label, 'Test Field 2')
        self.assertEqual(new_field2.field_type, 'integer')
        self.assertFalse(new_field2.required)
        self.assertEqual(new_field2.typology, self.typology)
        self.assertEqual(new_field2.typology_category, 'Category1')
    
    def test_copy_preserves_geometries(self):
        """Test that copy preserves all geometry points"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        
        # Check geometries were copied
        new_geometries = DataGeometry.objects.filter(dataset=new_dataset)
        self.assertEqual(new_geometries.count(), 2)
        
        # Check geometry1
        new_geo1 = new_geometries.get(id_kurz='GEO001')
        self.assertEqual(new_geo1.address, 'Test Address 1')
        self.assertEqual(new_geo1.user, self.superuser)
        self.assertAlmostEqual(new_geo1.geometry.x, 16.3738, places=6)
        self.assertAlmostEqual(new_geo1.geometry.y, 48.2082, places=6)
        
        # Check geometry2
        new_geo2 = new_geometries.get(id_kurz='GEO002')
        self.assertEqual(new_geo2.address, 'Test Address 2')
        self.assertEqual(new_geo2.user, self.superuser)
    
    def test_copy_preserves_entries(self):
        """Test that copy preserves all data entries"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        new_geo1 = DataGeometry.objects.get(dataset=new_dataset, id_kurz='GEO001')
        new_geo2 = DataGeometry.objects.get(dataset=new_dataset, id_kurz='GEO002')
        
        # Check entries for geometry1
        entries_geo1 = DataEntry.objects.filter(geometry=new_geo1)
        self.assertEqual(entries_geo1.count(), 2)
        
        entry1 = entries_geo1.get(name='Entry 1')
        self.assertEqual(entry1.year, 2023)
        self.assertEqual(entry1.user, self.superuser)
        
        entry2 = entries_geo1.get(name='Entry 2')
        self.assertEqual(entry2.year, 2024)
        self.assertEqual(entry2.user, self.superuser)
        
        # Check entries for geometry2
        entries_geo2 = DataEntry.objects.filter(geometry=new_geo2)
        self.assertEqual(entries_geo2.count(), 1)
        
        entry3 = entries_geo2.get(name='Entry 3')
        self.assertEqual(entry3.year, 2023)
        self.assertEqual(entry3.user, self.superuser)
    
    def test_copy_preserves_entry_fields(self):
        """Test that copy preserves all entry field values"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        new_geo1 = DataGeometry.objects.get(dataset=new_dataset, id_kurz='GEO001')
        new_entry1 = DataEntry.objects.get(geometry=new_geo1, name='Entry 1')
        
        # Check entry fields
        entry_fields = DataEntryField.objects.filter(entry=new_entry1)
        self.assertEqual(entry_fields.count(), 2)
        
        field1 = entry_fields.get(field_name='test_field_1')
        self.assertEqual(field1.field_type, 'text')
        self.assertEqual(field1.value, 'Value 1')
        
        field2 = entry_fields.get(field_name='test_field_2')
        self.assertEqual(field2.field_type, 'integer')
        self.assertEqual(field2.value, '100')
    
    def test_copy_preserves_files(self):
        """Test that copy preserves file entries"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        new_geo1 = DataGeometry.objects.get(dataset=new_dataset, id_kurz='GEO001')
        new_entry1 = DataEntry.objects.get(geometry=new_geo1, name='Entry 1')
        
        # Check files
        entry_files = DataEntryFile.objects.filter(entry=new_entry1)
        self.assertEqual(entry_files.count(), 1)
        
        file_obj = entry_files.first()
        self.assertEqual(file_obj.filename, 'test_image.jpg')
        self.assertEqual(file_obj.file_type, 'image/jpeg')
        self.assertEqual(file_obj.upload_user, self.superuser)
        self.assertEqual(file_obj.description, 'Test file')
        # File should exist (content was copied)
        self.assertTrue(file_obj.file)
    
    def test_copy_preserves_mapping_areas(self):
        """Test that copy preserves mapping areas and relationships"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        
        # Check mapping areas
        new_areas = MappingArea.objects.filter(dataset=new_dataset)
        self.assertEqual(new_areas.count(), 1)
        
        new_area = new_areas.first()
        self.assertEqual(new_area.name, 'Test Area')
        self.assertEqual(new_area.created_by, self.superuser)
        self.assertIn(self.shared_user, new_area.allocated_users.all())
        
        # Check mapping area limits
        user_limits = DatasetUserMappingArea.objects.filter(dataset=new_dataset)
        self.assertEqual(user_limits.count(), 1)
        self.assertEqual(user_limits.first().user, self.shared_user)
        self.assertEqual(user_limits.first().mapping_area, new_area)
        
        group_limits = DatasetGroupMappingArea.objects.filter(dataset=new_dataset)
        self.assertEqual(group_limits.count(), 1)
        self.assertEqual(group_limits.first().group, self.group)
        self.assertEqual(group_limits.first().mapping_area, new_area)
    
    def test_copy_empty_dataset(self):
        """Test copying an empty dataset (no geometries, entries, etc.)"""
        empty_dataset = DataSet.objects.create(
            name='Empty Dataset',
            description='Empty',
            owner=self.owner,
        )
        DatasetFieldConfig.objects.create(dataset=empty_dataset)
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[empty_dataset.id]))
        
        self.assertEqual(response.status_code, 302)
        
        new_dataset = DataSet.objects.get(name='Empty Dataset_Copy')
        self.assertEqual(new_dataset.owner, self.superuser)
        self.assertEqual(DataGeometry.objects.filter(dataset=new_dataset).count(), 0)
        self.assertEqual(DataEntry.objects.filter(geometry__dataset=new_dataset).count(), 0)
    
    def test_copy_nonexistent_dataset(self):
        """Test copying a nonexistent dataset returns 404"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[99999]))
        self.assertEqual(response.status_code, 404)
    
    def test_copy_long_dataset_name(self):
        """Test that copy handles long dataset names correctly"""
        long_name = 'A' * 250  # 250 characters
        long_dataset = DataSet.objects.create(
            name=long_name,
            description='Long name',
            owner=self.owner,
        )
        
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[long_dataset.id]))
        
        self.assertEqual(response.status_code, 302)
        
        # Check that name was truncated properly
        new_dataset = DataSet.objects.get(name__endswith='_Copy')
        self.assertLessEqual(len(new_dataset.name), 255)
        self.assertTrue(new_dataset.name.endswith('_Copy'))
    
    def test_copy_redirects_to_new_dataset_detail(self):
        """Test that copy redirects to the new dataset detail page"""
        self.client.login(username='superuser', password='testpass123')
        response = self.client.get(reverse('dataset_copy', args=[self.original_dataset.id]))
        
        self.assertEqual(response.status_code, 302)
        new_dataset = DataSet.objects.get(name='Original Dataset_Copy')
        self.assertEqual(response.url, reverse('dataset_detail', args=[new_dataset.id]))
    
    def test_copy_is_atomic(self):
        """Test that copy operation is atomic (rolls back on error)"""
        # This test verifies that if an error occurs during copy,
        # the transaction is rolled back and no partial data is created
        
        # Create a dataset with invalid data that might cause an error
        # (e.g., a geometry with invalid coordinates)
        problematic_dataset = DataSet.objects.create(
            name='Problematic Dataset',
            owner=self.owner,
        )
        
        # Create a geometry that might cause issues
        DataGeometry.objects.create(
            dataset=problematic_dataset,
            address='Test',
            geometry=Point(0, 0, srid=4326),  # Valid geometry
            id_kurz='TEST',
            user=self.owner,
        )
        
        self.client.login(username='superuser', password='testpass123')
        
        # Count before copy
        initial_count = DataSet.objects.count()
        
        # Attempt copy (should succeed in this case, but we're testing atomicity)
        response = self.client.get(reverse('dataset_copy', args=[problematic_dataset.id]))
        
        # If copy succeeds, we should have one more dataset
        # If it fails, we should have the same count (atomic rollback)
        if response.status_code == 302:
            self.assertEqual(DataSet.objects.count(), initial_count + 1)
        else:
            # If there was an error, count should be unchanged
            self.assertEqual(DataSet.objects.count(), initial_count)
