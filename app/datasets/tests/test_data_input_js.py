from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.template.loader import render_to_string
from django.template import Context, Template
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
import json
import re

from ..models import DataSet, DataGeometry, DataEntry, DataEntryField, DatasetField


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class DataInputJavaScriptTestCase(TestCase):
    """Test the data input JavaScript functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.dataset = DataSet.objects.create(
            name='Test Dataset',
            description='Test dataset for JavaScript testing',
            owner=self.user
        )
        
        # Create test fields
        self.field1 = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_field_1',
            label='Test Field 1',
            field_type='text',
            enabled=True,
            required=True,
            order=1
        )
        
        self.field2 = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='test_field_2',
            label='Test Field 2',
            field_type='choice',
            enabled=True,
            required=False,
            order=2,
            choices='Option A,Option B,Option C'
        )
        
        # Create test geometry
        from django.contrib.gis.geos import Point
        self.geometry = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='TEST001',
            address='Test Address',
            geometry=Point(15.0, 48.0),
            user=self.user
        )
        
        # Create test entry
        self.entry = DataEntry.objects.create(
            geometry=self.geometry,
            name='Test Entry',
            year=2023,
            user=self.user
        )
        
        # Create field values
        DataEntryField.objects.create(
            entry=self.entry,
            field_name='test_field_1',
            value='Test Value 1'
        )
        
        DataEntryField.objects.create(
            entry=self.entry,
            field_name='test_field_2',
            value='Option A'
        )
    
    def test_data_input_template_renders_correctly(self):
        """Test that the data input template renders with correct field data"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        # Check that the template contains the field data
        self.assertContains(response, 'window.allFields')
        self.assertContains(response, 'test_field_1')
        self.assertContains(response, 'test_field_2')
    
    def test_fields_data_structure(self):
        """Test that fields_data is structured correctly for JavaScript"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        # Extract the fields data from the response
        content = response.content.decode()
        
        # Find the JSON script tag
        import re
        json_match = re.search(r'<script[^>]*id="allFields"[^>]*>(.*?)</script>', content, re.DOTALL)
        self.assertIsNotNone(json_match, "allFields script tag not found")
        
        fields_json = json_match.group(1).strip()
        fields_data = json.loads(fields_json)
        
        # Verify the structure
        self.assertIsInstance(fields_data, list)
        self.assertGreaterEqual(len(fields_data), 2)
        
        # Check first field
        field1_data = next(f for f in fields_data if f['field_name'] == 'test_field_1')
        self.assertEqual(field1_data['field_name'], 'test_field_1')
        self.assertEqual(field1_data['label'], 'Test Field 1')
        self.assertEqual(field1_data['field_type'], 'text')
        self.assertTrue(field1_data['enabled'])
        self.assertTrue(field1_data['required'])
        self.assertEqual(field1_data['order'], 1)
        
        # Check second field
        field2_data = next(f for f in fields_data if f['field_name'] == 'test_field_2')
        self.assertEqual(field2_data['field_name'], 'test_field_2')
        self.assertEqual(field2_data['label'], 'Test Field 2')
        self.assertEqual(field2_data['field_type'], 'choice')
        self.assertTrue(field2_data['enabled'])
        self.assertFalse(field2_data['required'])
        self.assertEqual(field2_data['order'], 2)
        self.assertEqual(field2_data['choices'], 'Option A,Option B,Option C')

    def test_textarea_field_in_fields_data(self):
        """Test that textarea (Large Text) fields are included in fields_data for JavaScript"""
        textarea_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='notes_field',
            label='Notes',
            field_type='textarea',
            enabled=True,
            required=False,
            order=3
        )

        client = Client()
        client.force_login(self.user)

        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode()
        json_match = re.search(r'<script[^>]*id="allFields"[^>]*>(.*?)</script>', content, re.DOTALL)
        self.assertIsNotNone(json_match, "allFields script tag not found")

        fields_json = json_match.group(1).strip()
        fields_data = json.loads(fields_json)

        textarea_data = next(f for f in fields_data if f['field_name'] == 'notes_field')
        self.assertEqual(textarea_data['field_name'], 'notes_field')
        self.assertEqual(textarea_data['label'], 'Notes')
        self.assertEqual(textarea_data['field_type'], 'textarea')
        self.assertTrue(textarea_data['enabled'])
        self.assertFalse(textarea_data['required'])
        self.assertEqual(textarea_data['order'], 3)

    def test_javascript_handles_textarea_field_type(self):
        """Test that JavaScript createFormFieldInput, createCustomFieldInput, createEditableFieldInput handle textarea"""
        import os
        from django.conf import settings

        js_file_path = os.path.join(settings.STATIC_ROOT, 'js', 'data-input.js')
        if not os.path.exists(js_file_path):
            js_file_path = os.path.join(settings.STATICFILES_DIRS[0], 'js', 'data-input.js')

        self.assertTrue(os.path.exists(js_file_path), f"JavaScript file not found at {js_file_path}")

        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()

        self.assertIn("case 'textarea':", js_content,
                      "createFormFieldInput should handle textarea field type")
        self.assertIn('<textarea', js_content,
                      "JavaScript should render textarea element for Large Text fields")
    
    def test_geometry_details_api_returns_correct_data(self):
        """Test that the geometry details API returns the correct structure"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('geometry_details', kwargs={'geometry_id': self.geometry.id}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('geometry', data)
        
        geometry_data = data['geometry']
        self.assertEqual(geometry_data['id'], self.geometry.id)
        self.assertEqual(geometry_data['id_kurz'], 'TEST001')
        self.assertEqual(geometry_data['created_by_user_id'], self.user.id)
        self.assertIn('entries', geometry_data)
        
        # Check entries structure
        entries = geometry_data['entries']
        self.assertEqual(len(entries), 1)
        
        entry = entries[0]
        self.assertEqual(entry['id'], self.entry.id)
        self.assertEqual(entry['name'], 'Test Entry')
        self.assertEqual(entry['year'], 2023)
        
        # Check that field values are included
        self.assertIn('test_field_1', entry)
        self.assertEqual(entry['test_field_1'], 'Test Value 1')
        self.assertIn('test_field_2', entry)
        self.assertEqual(entry['test_field_2'], 'Option A')
    
    def test_geometry_details_api_with_no_entries(self):
        """Test geometry details API when there are no entries"""
        # Create a geometry without entries
        from django.contrib.gis.geos import Point
        empty_geometry = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='EMPTY001',
            address='Empty Address',
            geometry=Point(16.0, 49.0),
            user=self.user
        )
        
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('geometry_details', kwargs={'geometry_id': empty_geometry.id}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertTrue(data['success'])
        
        geometry_data = data['geometry']
        self.assertEqual(geometry_data['id'], empty_geometry.id)
        self.assertEqual(geometry_data['id_kurz'], 'EMPTY001')
        self.assertEqual(len(geometry_data['entries']), 0)
    
    def test_geometry_details_api_with_disabled_fields(self):
        """Test that disabled fields are not included in the API response"""
        # Disable one field
        self.field2.enabled = False
        self.field2.save()
        
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('geometry_details', kwargs={'geometry_id': self.geometry.id}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        geometry_data = data['geometry']
        entries = geometry_data['entries']
        
        # Check that only enabled fields are included
        entry = entries[0]
        self.assertIn('test_field_1', entry)  # Enabled field
        self.assertNotIn('test_field_2', entry)  # Disabled field
    
    def test_map_data_api_returns_lightweight_data(self):
        """Test that the map data API returns lightweight data without field details"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_map_data', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('map_data', data)
        
        map_data = data['map_data']
        self.assertEqual(len(map_data), 1)
        
        point = map_data[0]
        self.assertEqual(point['id'], self.geometry.id)
        self.assertEqual(point['id_kurz'], 'TEST001')
        self.assertEqual(point['address'], 'Test Address')
        self.assertIn('lat', point)
        self.assertIn('lng', point)
        self.assertIn('user', point)
        self.assertEqual(point['created_by_user_id'], self.user.id)
        
        # Should not contain entries or field data
        self.assertNotIn('entries', point)
    
    def test_javascript_template_variables(self):
        """Test that JavaScript template variables are set correctly"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode()
        
        # Check that allowMultipleEntries is set
        self.assertIn('window.allowMultipleEntries', content)
        
        # Check that translations are set
        self.assertIn('window.translations', content)
        
        # Check that the initializeDataInput function is called
        self.assertIn('initializeDataInput', content)
    
    def test_no_fields_configured_scenario(self):
        """Test the scenario when no fields are configured"""
        # Remove all fields
        DatasetField.objects.filter(dataset=self.dataset).delete()
        
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode()
        
        # Check that allFields is empty
        json_match = re.search(r'<script[^>]*id="allFields"[^>]*>(.*?)</script>', content, re.DOTALL)
        self.assertIsNotNone(json_match)
        
        fields_json = json_match.group(1).strip()
        fields_data = json.loads(fields_json)
        # No fields should exist if none are configured (no automatic creation)
        self.assertEqual(len(fields_data), 0)
    
    def test_javascript_file_loading(self):
        """Test that the external JavaScript file is loaded correctly"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        content = response.content.decode()
        
        # Check that the external JavaScript file is referenced
        self.assertIn('/static/js/data-input.js', content, "External JavaScript file not referenced")
        
        # Read the JavaScript file directly from the filesystem
        import os
        from django.conf import settings
        
        js_file_path = os.path.join(settings.STATIC_ROOT, 'js', 'data-input.js')
        if not os.path.exists(js_file_path):
            js_file_path = os.path.join(settings.STATICFILES_DIRS[0], 'js', 'data-input.js')
        
        self.assertTrue(os.path.exists(js_file_path), f"JavaScript file not found at {js_file_path}")
        
        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        # Check that key JavaScript functions are defined in the external file
        required_functions = [
            'function generateEntriesTable',
            'function showGeometryDetails',
            'function selectPoint',
            'function loadGeometryDetails',
            'function createFormFieldInput',
            'function initializeDataInput'
        ]
        
        for func in required_functions:
            self.assertIn(func, js_content, f"Function {func} not found in external JavaScript file")
    
    def test_javascript_debug_logging_present(self):
        """Test that debug logging is present in the external JavaScript file"""
        # Read the JavaScript file directly from the filesystem
        import os
        from django.conf import settings
        
        js_file_path = os.path.join(settings.STATIC_ROOT, 'js', 'data-input.js')
        if not os.path.exists(js_file_path):
            js_file_path = os.path.join(settings.STATICFILES_DIRS[0], 'js', 'data-input.js')
        
        self.assertTrue(os.path.exists(js_file_path), f"JavaScript file not found at {js_file_path}")
        
        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        # Check that debug logging is present in the external file
        debug_statements = [
            'console.log(\'generateEntriesTable called with point:\'',
            'console.log(\'window.allFields:\'',
            'console.log(\'New entry form - Checking window.allFields:\'',
            'console.log(\'New entry form - Has enabled fields:\'',
            'console.log(\'New entry form - Rendering field:\''
        ]
        
        for debug_stmt in debug_statements:
            self.assertIn(debug_stmt, js_content, f"Debug statement {debug_stmt} not found in external JavaScript file")
    
    def test_geometry_details_api_structure_matches_js_expectations(self):
        """Test that the API response structure matches what JavaScript expects"""
        client = Client()
        client.force_login(self.user)
        
        # Test the geometry details API
        response = client.get(reverse('geometry_details', kwargs={'geometry_id': self.geometry.id}))
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Verify the structure that JavaScript expects
        self.assertIn('success', data)
        self.assertTrue(data['success'])
        self.assertIn('geometry', data)
        
        geometry = data['geometry']
        required_fields = ['id', 'id_kurz', 'address', 'lat', 'lng', 'user', 'created_by_user_id', 'entries']
        for field in required_fields:
            self.assertIn(field, geometry, f"Required field {field} missing from geometry data")
        
        # Check entries structure
        entries = geometry['entries']
        self.assertIsInstance(entries, list)
        
        if entries:
            entry = entries[0]
            entry_required_fields = ['id', 'name', 'year', 'user']
            for field in entry_required_fields:
                self.assertIn(field, entry, f"Required field {field} missing from entry data")
    
    def test_template_renders_with_correct_context(self):
        """Test that the template receives the correct context variables"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        # Check that the template context contains the expected variables
        self.assertIn('dataset', response.context)
        self.assertIn('fields_data', response.context)
        self.assertIn('allow_multiple_entries', response.context)
        
        # Verify the context values
        self.assertEqual(response.context['dataset'], self.dataset)
        self.assertIsInstance(response.context['fields_data'], list)
        self.assertGreaterEqual(len(response.context['fields_data']), 2)
        context_field_names = {field['field_name'] for field in response.context['fields_data']}
        self.assertIn('test_field_1', context_field_names)
        self.assertIn('test_field_2', context_field_names)
        self.assertIsInstance(response.context['allow_multiple_entries'], bool)
    
    def test_javascript_handles_non_editable_fields(self):
        """Test that JavaScript code properly handles non_editable fields by checking readonly/disabled attributes"""
        # Read the JavaScript file directly from the filesystem
        import os
        from django.conf import settings
        
        js_file_path = os.path.join(settings.STATIC_ROOT, 'js', 'data-input.js')
        if not os.path.exists(js_file_path):
            js_file_path = os.path.join(settings.STATICFILES_DIRS[0], 'js', 'data-input.js')
        
        self.assertTrue(os.path.exists(js_file_path), f"JavaScript file not found at {js_file_path}")
        
        with open(js_file_path, 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        # Check that createFormFieldInput function handles non_editable for text fields
        self.assertIn('if (field.non_editable) inputHtml += \' readonly\';', js_content,
                     "createFormFieldInput should add readonly for non_editable text fields")
        
        # Check that createFormFieldInput function handles non_editable for select/choice fields
        self.assertIn('if (field.non_editable) inputHtml += \' disabled\';', js_content,
                     "createFormFieldInput should add disabled for non_editable select fields")
        
        # Check that createFormFieldInput function adds hidden input for disabled selects
        self.assertIn('if (field.non_editable) {', js_content,
                     "createFormFieldInput should check for non_editable")
        self.assertIn('<input type="hidden" name="', js_content,
                     "createFormFieldInput should add hidden input for disabled selects")
        
        # Check that createEditableFieldInput function handles non_editable
        # This function is used for editing existing entries
        editable_function_start = js_content.find('function createEditableFieldInput')
        self.assertNotEqual(editable_function_start, -1, "createEditableFieldInput function not found")
        
        # Extract the createEditableFieldInput function
        editable_function_end = js_content.find('function createEntry', editable_function_start)
        if editable_function_end == -1:
            editable_function_end = len(js_content)
        
        editable_function = js_content[editable_function_start:editable_function_end]
        
        # Check that it handles non_editable for text fields
        self.assertIn('if (field.non_editable) inputHtml += \' readonly\';', editable_function,
                     "createEditableFieldInput should add readonly for non_editable text fields")
        
        # Check that it handles non_editable for select fields
        self.assertIn('if (field.non_editable) inputHtml += \' disabled\';', editable_function,
                     "createEditableFieldInput should add disabled for non_editable select fields")
        
        # Check that createCustomFieldInput function handles non_editable
        custom_function_start = js_content.find('function createCustomFieldInput')
        self.assertNotEqual(custom_function_start, -1, "createCustomFieldInput function not found")
        
        custom_function_end = js_content.find('function createEditableFieldInput', custom_function_start)
        if custom_function_end == -1:
            custom_function_end = len(js_content)
        
        custom_function = js_content[custom_function_start:custom_function_end]
        
        # Check that it handles non_editable
        self.assertIn('if (field.non_editable)', custom_function,
                     "createCustomFieldInput should check for non_editable")
    
    def test_javascript_non_editable_fields_in_json_data(self):
        """Test that non_editable fields are properly included in JSON data for JavaScript"""
        # Create a non-editable field
        non_editable_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='non_editable_field',
            label='Non-Editable Field',
            field_type='text',
            enabled=True,
            non_editable=True,
            order=3
        )
        
        # Create an editable field for comparison
        editable_field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name='editable_field',
            label='Editable Field',
            field_type='text',
            enabled=True,
            non_editable=False,
            order=4
        )
        
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('dataset_data_input', kwargs={'dataset_id': self.dataset.id}))
        self.assertEqual(response.status_code, 200)
        
        # Extract the JSON data from the response
        content = response.content.decode()
        json_match = re.search(r'<script[^>]*id="allFields"[^>]*>(.*?)</script>', content, re.DOTALL)
        self.assertIsNotNone(json_match, "allFields script tag not found")
        
        fields_json = json_match.group(1).strip()
        fields_data = json.loads(fields_json)
        
        # Find the non-editable field
        non_editable_data = next(
            (f for f in fields_data if f['field_name'] == 'non_editable_field'),
            None
        )
        self.assertIsNotNone(non_editable_data, "Non-editable field not found in JSON")
        self.assertTrue(non_editable_data['non_editable'], "non_editable should be True")
        
        # Find the editable field
        editable_data = next(
            (f for f in fields_data if f['field_name'] == 'editable_field'),
            None
        )
        self.assertIsNotNone(editable_data, "Editable field not found in JSON")
        self.assertFalse(editable_data.get('non_editable', False), "non_editable should be False for editable field")
        
        # Verify that JavaScript can access the non_editable property
        # This ensures the property name matches what JavaScript expects
        self.assertIn('non_editable', non_editable_data, "non_editable property should be in JSON")
        self.assertEqual(non_editable_data['non_editable'], True, "non_editable should be True in JSON")

    def test_owner_can_delete_geometry_via_post(self):
        """Dataset owner can delete a geometry; it is removed from the database."""
        client = Client()
        client.force_login(self.user)
        gid = self.geometry.id
        url = reverse('geometry_delete', kwargs={'geometry_id': gid})
        response = client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))
        self.assertFalse(DataGeometry.objects.filter(pk=gid).exists())

    def test_shared_user_cannot_delete_others_geometry(self):
        """Collaborators cannot delete geometries created by another user."""
        other = User.objects.create_user(username='collab', email='c@example.com', password='pass')
        self.dataset.shared_with.add(other)
        client = Client()
        client.force_login(other)
        gid = self.geometry.id
        url = reverse('geometry_delete', kwargs={'geometry_id': gid})
        response = client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(DataGeometry.objects.filter(pk=gid).exists())

    def test_creator_can_delete_own_geometry(self):
        """A logged-in user can delete a geometry they created."""
        from django.contrib.gis.geos import Point

        collab = User.objects.create_user(username='collab2', email='c2@example.com', password='pass')
        self.dataset.shared_with.add(collab)
        own = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='OWN001',
            address='Own point',
            geometry=Point(16.0, 48.1),
            user=collab,
        )
        client = Client()
        client.force_login(collab)
        url = reverse('geometry_delete', kwargs={'geometry_id': own.id})
        response = client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get('success'))
        self.assertFalse(DataGeometry.objects.filter(pk=own.id).exists())
