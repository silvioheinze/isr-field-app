from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from ..models import DataSet, DataGeometry, DataEntry, DataEntryField, DatasetField


class SaveEntriesViewTest(TestCase):
    """Test cases for save entries functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.dataset = DataSet.objects.create(
            name='Test Dataset',
            description='Test Description',
            owner=self.user
        )
        
        # Create a geometry point
        self.geometry = DataGeometry.objects.create(
            dataset=self.dataset,
            geometry=Point(16.0, 48.0),
            id_kurz='TEST001',
            address='Test Address',
            user=self.user
        )
        
        # Create field configurations
        self.text_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_text',
            label='Test Text Field',
            field_type='text',
            enabled=True,
            order=1
        )
        
        self.number_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_number',
            label='Test Number Field',
            field_type='integer',
            enabled=True,
            order=2
        )
        
        self.choice_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_choice',
            label='Test Choice Field',
            field_type='choice',
            choices='Option1,Option2,Option3',
            enabled=True,
            order=3
        )
        
        # Create test entries
        self.entry1 = DataEntry.objects.create(
            geometry=self.geometry,
            name='Entry 1',
            year=2023,
            user=self.user
        )
        
        self.entry2 = DataEntry.objects.create(
            geometry=self.geometry,
            name='Entry 2',
            year=2024,
            user=self.user
        )
        
        # Create existing field values
        DataEntryField.objects.create(
            entry=self.entry1,
            field_name='test_text',
            value='Original Text 1'
        )
        
        DataEntryField.objects.create(
            entry=self.entry1,
            field_name='test_number',
            value='100'
        )
        
        DataEntryField.objects.create(
            entry=self.entry2,
            field_name='test_text',
            value='Original Text 2'
        )
    
    def test_save_entries_unauthenticated(self):
        """Test that unauthenticated users without anonymous token cannot save entries"""
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text'
        })
        self.assertEqual(response.status_code, 403)  # Access denied
    
    def test_save_entries_get_method(self):
        """Test that GET method is not allowed"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/entries/save/')
        self.assertEqual(response.status_code, 405)
    
    def test_save_entries_missing_geometry_id(self):
        """Test that missing geometry_id returns error"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/entries/save/', {
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text'
        })
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Geometry ID is required', data['error'])
    
    def test_save_entries_nonexistent_geometry(self):
        """Test that nonexistent geometry returns 404"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/entries/save/', {
            'geometry_id': 99999,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text'
        })
        self.assertEqual(response.status_code, 404)
    
    def test_save_entries_access_denied(self):
        """Test that users without access cannot save entries"""
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        self.client.login(username='otheruser', password='otherpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text'
        })
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Access denied', data['error'])
    
    def test_save_entries_success(self):
        """Test successful saving of entries"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text 1',
            'entries[0][fields][test_number]': '200',
            'entries[0][fields][test_choice]': 'Option2',
            'entries[1][id]': self.entry2.id,
            'entries[1][fields][test_text]': 'Updated Text 2',
            'entries[1][fields][test_number]': '300',
            'entries[1][fields][test_choice]': 'Option3'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Successfully updated 2 entries', data['message'])
        
        # Verify that field values were updated
        entry1_text = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_text'
        )
        self.assertEqual(entry1_text.value, 'Updated Text 1')
        
        entry1_number = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_number'
        )
        self.assertEqual(entry1_number.value, '200')
        
        entry1_choice = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_choice'
        )
        self.assertEqual(entry1_choice.value, 'Option2')
        
        entry2_text = DataEntryField.objects.get(
            entry=self.entry2,
            field_name='test_text'
        )
        self.assertEqual(entry2_text.value, 'Updated Text 2')
    
    def test_save_entries_create_new_fields(self):
        """Test that new field values are created when they don't exist"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create a new entry without any field values
        new_entry = DataEntry.objects.create(
            geometry=self.geometry,
            name='New Entry',
            year=2025,
            user=self.user
        )
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': new_entry.id,
            'entries[0][fields][test_text]': 'New Field Value',
            'entries[0][fields][test_number]': '500'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify that new field values were created
        text_field = DataEntryField.objects.get(
            entry=new_entry,
            field_name='test_text'
        )
        self.assertEqual(text_field.value, 'New Field Value')
        
        number_field = DataEntryField.objects.get(
            entry=new_entry,
            field_name='test_number'
        )
        self.assertEqual(number_field.value, '500')
    
    def test_save_entries_nonexistent_entry(self):
        """Test that nonexistent entries are skipped gracefully"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': 99999,  # Nonexistent entry ID
            'entries[0][fields][test_text]': 'Updated Text',
            'entries[1][id]': self.entry1.id,
            'entries[1][fields][test_text]': 'Updated Text 1'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Successfully updated 1 entries', data['message'])
        
        # Verify that the valid entry was updated
        entry1_text = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_text'
        )
        self.assertEqual(entry1_text.value, 'Updated Text 1')
    
    def test_save_entries_empty_data(self):
        """Test saving with empty field data"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': '',  # Empty value
            'entries[0][fields][test_number]': '0'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify that empty values are saved
        text_field = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_text'
        )
        self.assertEqual(text_field.value, '')
    
    def test_save_entries_malformed_data(self):
        """Test handling of malformed form data"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'invalid_key': 'invalid_value',
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Updated Text'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify that valid data was still processed
        text_field = DataEntryField.objects.get(
            entry=self.entry1,
            field_name='test_text'
        )
        self.assertEqual(text_field.value, 'Updated Text')
    
    def test_save_entries_multiple_field_types(self):
        """Test saving different field types"""
        self.client.login(username='testuser', password='testpass123')
        
        # Create additional field types
        boolean_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_boolean',
            label='Test Boolean Field',
            field_type='boolean',
            enabled=True,
            order=4
        )
        
        date_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_date',
            label='Test Date Field',
            field_type='date',
            enabled=True,
            order=5
        )
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Text Value',
            'entries[0][fields][test_number]': '42',
            'entries[0][fields][test_choice]': 'Option1',
            'entries[0][fields][test_boolean]': 'true',
            'entries[0][fields][test_date]': '2024-01-15'
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify all field types were saved correctly
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_text').value,
            'Text Value'
        )
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_number').value,
            '42'
        )
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_choice').value,
            'Option1'
        )
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_boolean').value,
            'true'
        )
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_date').value,
            '2024-01-15'
        )
    
    def test_save_entries_partial_update(self):
        """Test updating only some fields of an entry"""
        self.client.login(username='testuser', password='testpass123')
        
        response = self.client.post('/entries/save/', {
            'geometry_id': self.geometry.id,
            'entries[0][id]': self.entry1.id,
            'entries[0][fields][test_text]': 'Only Text Updated',
            # Note: not updating test_number or test_choice
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify that only the specified field was updated
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_text').value,
            'Only Text Updated'
        )
        
        # Verify that other fields remain unchanged
        self.assertEqual(
            DataEntryField.objects.get(entry=self.entry1, field_name='test_number').value,
            '100'  # Original value
        )
