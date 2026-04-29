"""Anonymous mapping area outlines API (read-only, session token)."""

from django.contrib.auth.models import User
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import DataSet, MappingArea


class MappingAreaAnonymousOutlinesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.dataset = DataSet.objects.create(
            name='Anon MA',
            owner=self.owner,
            allow_anonymous_data_input=True,
            enable_mapping_areas=True,
            anonymous_show_all_mapping_areas=False,
        )
        self.dataset.ensure_anonymous_access_token()
        self.dataset.refresh_from_db()

        polygon = Polygon(
            (
                (-0.1, -0.1),
                (-0.1, 0.1),
                (0.1, 0.1),
                (0.1, -0.1),
                (-0.1, -0.1),
            ),
            srid=4326,
        )
        self.area = MappingArea.objects.create(
            dataset=self.dataset,
            name='North',
            geometry=MultiPolygon(polygon, srid=4326),
            created_by=self.owner,
        )

        self.url = reverse('mapping_area_anonymous_outlines', args=[self.dataset.id])
        self.client = Client()

    def _set_session_token(self, token):
        session = self.client.session
        session[f'anonymous_token_{self.dataset.id}'] = token
        session.save()

    def test_invalid_token_returns_403(self):
        self._set_session_token('wrong-token')
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 403)
        self.assertFalse(r.json().get('success', True))

    def test_flag_off_returns_empty_list(self):
        self._set_session_token(self.dataset.anonymous_access_token)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['mapping_areas'], [])

    def test_flag_on_returns_all_areas(self):
        self.dataset.anonymous_show_all_mapping_areas = True
        self.dataset.save(update_fields=['anonymous_show_all_mapping_areas'])
        self._set_session_token(self.dataset.anonymous_access_token)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['mapping_areas']), MappingArea.objects.filter(dataset=self.dataset).count())
        first = next(a for a in data['mapping_areas'] if a['id'] == self.area.id)
        self.assertEqual(first['name'], 'North')
        self.assertEqual(first['geometry']['type'], 'MultiPolygon')
