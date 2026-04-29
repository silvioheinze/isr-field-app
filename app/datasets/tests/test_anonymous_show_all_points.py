"""Anonymous 'show all points' map visibility."""
import json
import uuid

from django.contrib.gis.geos import Point
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import DataEntry, DataGeometry, DataSet, VirtualContributor


class AnonymousShowAllPointsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.dataset = DataSet.objects.create(
            name='Anon Dataset',
            owner=self.owner,
            allow_anonymous_data_input=True,
            anonymous_show_all_points=False,
        )
        self.dataset.ensure_anonymous_access_token()
        self.dataset.refresh_from_db()

        self.vc_self = VirtualContributor.objects.create(
            dataset=self.dataset,
            uuid=uuid.uuid4(),
            display_name='Self',
        )
        self.vc_other = VirtualContributor.objects.create(
            dataset=self.dataset,
            uuid=uuid.uuid4(),
            display_name='Other',
        )

        self.geom_self = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='A',
            address='A',
            geometry=Point(16.37, 48.21, srid=4326),
            virtual_contributor=self.vc_self,
        )
        self.geom_other = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='B',
            address='B',
            geometry=Point(16.38, 48.22, srid=4326),
            virtual_contributor=self.vc_other,
        )
        self.entry_other = DataEntry.objects.create(
            geometry=self.geom_other,
            name='Other entry',
            year=2020,
            virtual_contributor=self.vc_other,
        )

        self.anon_client = Client()
        sid = self.dataset.id
        session = self.anon_client.session
        session[f'anonymous_token_{sid}'] = self.dataset.anonymous_access_token
        session[f'virtual_contributor_uuid_{sid}'] = str(self.vc_self.uuid)
        session.save()

    def _map_ids(self):
        url = reverse('dataset_map_data', kwargs={'dataset_id': self.dataset.id})
        r = self.anon_client.get(url)
        self.assertEqual(r.status_code, 200)
        return {row['id'] for row in r.json().get('map_data', [])}

    def test_map_data_only_own_points_when_flag_off(self):
        self.assertEqual(self._map_ids(), {self.geom_self.id})

    def test_map_data_all_points_when_flag_on(self):
        self.dataset.anonymous_show_all_points = True
        self.dataset.save(update_fields=['anonymous_show_all_points'])
        self.assertSetEqual(self._map_ids(), {self.geom_self.id, self.geom_other.id})

    def test_geometry_details_other_denied_when_flag_off(self):
        url = reverse('geometry_details', kwargs={'geometry_id': self.geom_other.id})
        r = self.anon_client.get(url)
        self.assertEqual(r.status_code, 403)

    def test_geometry_details_other_allowed_when_flag_on(self):
        self.dataset.anonymous_show_all_points = True
        self.dataset.save(update_fields=['anonymous_show_all_points'])
        url = reverse('geometry_details', kwargs={'geometry_id': self.geom_other.id})
        r = self.anon_client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get('success'))

    def test_save_entries_other_geometry_denied_when_flag_off(self):
        url = reverse('save_entries')
        r = self.anon_client.post(
            url,
            {
                'geometry_id': str(self.geom_other.id),
                'entries[0][id]': str(self.entry_other.id),
            },
        )
        self.assertEqual(r.status_code, 403)

    def test_save_entries_other_geometry_allowed_when_flag_on(self):
        self.dataset.anonymous_show_all_points = True
        self.dataset.save(update_fields=['anonymous_show_all_points'])
        url = reverse('save_entries')
        r = self.anon_client.post(
            url,
            {
                'geometry_id': str(self.geom_other.id),
                'entries[0][id]': str(self.entry_other.id),
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get('success'))

    def test_geometry_create_denied_when_anonymous_disable_new_points(self):
        self.dataset.anonymous_disable_new_points = True
        self.dataset.save(update_fields=['anonymous_disable_new_points'])
        url = reverse('geometry_create', kwargs={'dataset_id': self.dataset.id})
        payload = {
            'id_kurz': 'NEW_PT',
            'address': 'New',
            'geometry': {'type': 'Point', 'coordinates': [16.4, 48.25]},
        }
        r = self.anon_client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 403)
        body = r.json()
        self.assertFalse(body.get('success', True))
        self.assertIn('disabled', (body.get('error') or '').lower())

    def test_geometry_create_allowed_when_anonymous_disable_new_points_off(self):
        url = reverse('geometry_create', kwargs={'dataset_id': self.dataset.id})
        payload = {
            'id_kurz': 'NEW_PT2',
            'address': 'New',
            'geometry': {'type': 'Point', 'coordinates': [16.41, 48.26]},
        }
        r = self.anon_client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get('success'))
