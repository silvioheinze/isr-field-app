import json

from unittest import mock

from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db.utils import ProgrammingError
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import DataSet, MappingArea


class MappingAreaViewsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.other_user = User.objects.create_user(username='other', password='pass')
        self.dataset = DataSet.objects.create(name='Test Dataset', owner=self.owner)

        self.list_url = reverse('mapping_area_list', args=[self.dataset.id])
        self.create_url = reverse('mapping_area_create', args=[self.dataset.id])

        self.owner_client = Client()
        self.owner_client.force_login(self.owner)
        self.other_client = Client()
        self.other_client.force_login(self.other_user)

    def _geos_polygon(self):
        coords = [
            (10.0, 10.0),
            (10.0, 10.1),
            (10.1, 10.1),
            (10.1, 10.0),
            (10.0, 10.0),
        ]
        return Polygon(coords, srid=4326)

    def _geos_multipolygon(self):
        return MultiPolygon(self._geos_polygon(), srid=4326)

    def _geojson_polygon(self):
        coords = [
            [10.0, 10.0],
            [10.0, 10.1],
            [10.1, 10.1],
            [10.1, 10.0],
            [10.0, 10.0],
        ]
        return {
            'type': 'Polygon',
            'coordinates': [coords],
        }

    def test_login_required_for_list(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_non_owner_cannot_list_mapping_areas(self):
        with self.assertLogs('django.request', level='WARNING'):
            response = self.other_client.get(self.list_url)
        self.assertEqual(response.status_code, 403)
        payload = response.json()
        self.assertFalse(payload['success'])
        self.assertEqual(payload['error'], 'Access denied')

    def test_owner_can_list_mapping_areas(self):
        area = MappingArea.objects.create(
            dataset=self.dataset,
            name='Area 1',
            geometry=self._geos_multipolygon(),
            created_by=self.owner,
        )
        area.allocated_users.add(self.other_user)

        response = self.owner_client.get(self.list_url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['mapping_areas']), 1)

        area_data = data['mapping_areas'][0]
        self.assertEqual(area_data['id'], area.id)
        self.assertEqual(area_data['name'], 'Area 1')
        self.assertEqual(set(area_data['allocated_users']), {self.other_user.id})
        self.assertEqual(area_data['geometry']['type'], 'MultiPolygon')

    def test_list_handles_database_error(self):
        with self.assertLogs('datasets.views.mapping_area_views', level='WARNING') as cap_logs:
            with mock.patch('datasets.views.mapping_area_views.MappingArea.objects.filter') as mocked_filter:
                mocked_filter.side_effect = ProgrammingError('relation does not exist')
                response = self.owner_client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['mapping_areas'], [])
        self.assertIn('warning', data)
        self.assertIn('temporarily unavailable', data['warning'])
        self.assertTrue(any('Database error while loading mapping areas' in entry for entry in cap_logs.output))

    def test_owner_can_create_mapping_area(self):
        payload = {
            'name': 'New Area',
            'geometry': self._geojson_polygon(),
            'allocated_users': [self.other_user.id],
        }

        response = self.owner_client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(MappingArea.objects.count(), 1)

        mapping_area = MappingArea.objects.get()
        self.assertEqual(mapping_area.name, 'New Area')
        self.assertEqual(mapping_area.allocated_users.count(), 1)
        self.assertEqual(mapping_area.allocated_users.first(), self.other_user)

    def test_create_rejects_invalid_geometry(self):
        payload = {
            'name': 'Invalid Area',
            'geometry': {'type': 'Point', 'coordinates': [10.0, 10.0]},
        }

        with self.assertLogs('django.request', level='WARNING'):
            response = self.owner_client.post(
                self.create_url,
                data=json.dumps(payload),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'Invalid geometry')
        self.assertEqual(MappingArea.objects.count(), 0)

    def test_create_response_returns_persisted_mapping_area(self):
        """Ensure mapping area save flow persists data and returns expected payload."""
        payload = {
            'name': 'Persisted Area',
            'geometry': self._geojson_polygon(),
            'allocated_users': [self.other_user.id],
        }
        response = self.owner_client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('mapping_area', data)
        mapping_area_payload = data['mapping_area']
        self.assertEqual(mapping_area_payload['name'], 'Persisted Area')
        self.assertIn(self.other_user.id, mapping_area_payload['allocated_users'])

        self.assertEqual(MappingArea.objects.count(), 1)
        mapping_area = MappingArea.objects.get()
        self.assertEqual(mapping_area.name, 'Persisted Area')
        expected_mp = MultiPolygon(
            Polygon(self._geojson_polygon()['coordinates'][0], srid=4326),
            srid=4326,
        )
        self.assertAlmostEqual(mapping_area.geometry.area, expected_mp.area, places=6)
        self.assertEqual(list(mapping_area.allocated_users.values_list('id', flat=True)), [self.other_user.id])

    def test_non_owner_cannot_create_mapping_area(self):
        payload = {
            'name': 'Blocked Area',
            'geometry': self._geojson_polygon(),
        }
        with self.assertLogs('django.request', level='WARNING'):
            response = self.other_client.post(
                self.create_url,
                data=json.dumps(payload),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MappingArea.objects.count(), 0)

    def test_owner_can_update_mapping_area(self):
        area = MappingArea.objects.create(
            dataset=self.dataset,
            name='Original Area',
            geometry=self._geos_multipolygon(),
            created_by=self.owner,
        )
        area.allocated_users.add(self.other_user)

        update_url = reverse('mapping_area_update', args=[self.dataset.id, area.id])
        new_geometry = {
            'type': 'Polygon',
            'coordinates': [[
                [10.2, 10.2],
                [10.2, 10.3],
                [10.3, 10.3],
                [10.3, 10.2],
                [10.2, 10.2],
            ]],
        }

        payload = {
            'name': 'Updated Area',
            'geometry': new_geometry,
            'allocated_users': [],
        }

        response = self.owner_client.post(
            update_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        area.refresh_from_db()
        self.assertEqual(area.name, 'Updated Area')
        self.assertEqual(area.allocated_users.count(), 0)
        self.assertAlmostEqual(area.geometry.centroid.x, 10.25, places=4)
        self.assertAlmostEqual(area.geometry.centroid.y, 10.25, places=4)

    def test_non_owner_cannot_update_mapping_area(self):
        area = MappingArea.objects.create(
            dataset=self.dataset,
            name='Original Area',
            geometry=self._geos_multipolygon(),
            created_by=self.owner,
        )

        update_url = reverse('mapping_area_update', args=[self.dataset.id, area.id])

        payload = {
            'name': 'Blocked Update',
            'geometry': self._geojson_polygon(),
        }

        with self.assertLogs('django.request', level='WARNING'):
            response = self.other_client.post(
                update_url,
                data=json.dumps(payload),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 403)

        area.refresh_from_db()
        self.assertEqual(area.name, 'Original Area')

    def test_owner_can_delete_mapping_area(self):
        area = MappingArea.objects.create(
            dataset=self.dataset,
            name='To Delete',
            geometry=self._geos_multipolygon(),
            created_by=self.owner,
        )

        delete_url = reverse('mapping_area_delete', args=[self.dataset.id, area.id])
        response = self.owner_client.post(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(MappingArea.objects.count(), 0)

    def test_non_owner_cannot_delete_mapping_area(self):
        area = MappingArea.objects.create(
            dataset=self.dataset,
            name='Protected',
            geometry=self._geos_multipolygon(),
            created_by=self.owner,
        )

        delete_url = reverse('mapping_area_delete', args=[self.dataset.id, area.id])
        with self.assertLogs('django.request', level='WARNING'):
            response = self.other_client.post(delete_url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MappingArea.objects.count(), 1)

    def test_owner_can_create_mapping_area_multipolygon_geojson(self):
        payload = {
            'name': 'Two parts',
            'geometry': {
                'type': 'MultiPolygon',
                'coordinates': [
                    [
                        [[0.0, 0.0], [0.0, 1.0], [1.0, 1.0], [1.0, 0.0], [0.0, 0.0]],
                    ],
                    [
                        [[2.0, 2.0], [2.0, 3.0], [3.0, 3.0], [3.0, 2.0], [2.0, 2.0]],
                    ],
                ],
            },
        }
        response = self.owner_client.post(
            self.create_url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        mapping_area = MappingArea.objects.get()
        self.assertEqual(mapping_area.geometry.geom_type, 'MultiPolygon')
        self.assertEqual(len(mapping_area.geometry), 2)

