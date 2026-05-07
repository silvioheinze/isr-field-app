"""Tests for entry create behavior when DatasetFieldConfig hides entry name on data input."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.urls import reverse

from ..models import DataSet, DataGeometry, DataEntry, DatasetFieldConfig


class EntryCreateNameConfigTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='p')
        self.dataset = DataSet.objects.create(name='D', owner=self.user)
        self.geometry = DataGeometry.objects.create(
            dataset=self.dataset,
            geometry=Point(16.0, 48.0),
            id_kurz='G123',
            address='Somewhere',
            user=self.user,
        )
        self.cfg = DatasetFieldConfig.objects.get(dataset=self.dataset)

    def test_ajax_create_empty_name_uses_geometry_id_when_name_disabled(self):
        self.cfg.name_enabled = False
        self.cfg.save()
        self.client.login(username='u', password='p')
        response = self.client.post(
            f'/geometries/{self.geometry.id}/entries/create/',
            {'name': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        entry = DataEntry.objects.get(geometry=self.geometry)
        self.assertEqual(entry.name, 'G123')

    def test_ajax_create_whitespace_name_defaults_when_name_disabled(self):
        self.cfg.name_enabled = False
        self.cfg.save()
        self.client.login(username='u', password='p')
        response = self.client.post(
            f'/geometries/{self.geometry.id}/entries/create/',
            {'name': '   '},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        entry = DataEntry.objects.get(geometry=self.geometry)
        self.assertEqual(entry.name, 'G123')

    def test_ajax_create_empty_name_rejected_when_name_enabled(self):
        self.cfg.name_enabled = True
        self.cfg.save()
        self.client.login(username='u', password='p')
        response = self.client.post(
            f'/geometries/{self.geometry.id}/entries/create/',
            {'name': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])
        self.assertFalse(DataEntry.objects.filter(geometry=self.geometry).exists())

    def test_explicit_name_still_used_when_name_disabled(self):
        self.cfg.name_enabled = False
        self.cfg.save()
        self.client.login(username='u', password='p')
        response = self.client.post(
            f'/geometries/{self.geometry.id}/entries/create/',
            {'name': 'Custom title'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        entry = DataEntry.objects.get(geometry=self.geometry)
        self.assertEqual(entry.name, 'Custom title')

    def test_data_input_template_exposes_entry_name_config(self):
        self.cfg.name_enabled = False
        self.cfg.name_label = 'Titel'
        self.cfg.save()
        self.client.login(username='u', password='p')
        response = self.client.get(reverse('dataset_data_input', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('window.entryNameEnabled = false', content)
        self.assertIn('window.entryNameLabel = "Titel"', content)
