from django.contrib.auth.models import Group, User
from django.contrib.gis.geos import MultiPolygon, Point, Polygon
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import (
    DataGeometry,
    DataSet,
    DatasetGroupMappingArea,
    DatasetUserMappingArea,
    MappingArea,
)


class DatasetMappingAreaAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.user = User.objects.create_user(username='member', password='pass')
        self.group = Group.objects.create(name='Collaborators')
        self.group.user_set.add(self.user)

        self.dataset = DataSet.objects.create(
            name='Shared Dataset',
            owner=self.owner,
            enable_mapping_areas=True,
        )
        self.dataset.shared_with.add(self.user)
        self.dataset.shared_with_groups.add(self.group)

        polygon = Polygon((
            (-0.1, -0.1),
            (-0.1, 0.1),
            (0.1, 0.1),
            (0.1, -0.1),
            (-0.1, -0.1),
        ), srid=4326)

        self.mapping_area = MappingArea.objects.create(
            dataset=self.dataset,
            name='Central Area',
            geometry=MultiPolygon(polygon, srid=4326),
            created_by=self.owner,
        )

        self.geometry_inside = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='IN',
            address='Inside',
            geometry=Point(0, 0, srid=4326),
            user=self.owner,
        )
        self.geometry_outside = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='OUT',
            address='Outside',
            geometry=Point(1, 1, srid=4326),
            user=self.owner,
        )

        self.owner_client = Client()
        self.owner_client.force_login(self.owner)

        self.user_client = Client()
        self.user_client.force_login(self.user)

    def test_owner_assigns_mapping_area_limits(self):
        url = reverse('dataset_access', args=[self.dataset.id])
        response = self.owner_client.post(url, {
            'shared_users': [str(self.user.id)],
            'shared_groups': [str(self.group.id)],
            f'user_mapping_areas_{self.user.id}': [str(self.mapping_area.id)],
            f'group_mapping_areas_{self.group.id}': [str(self.mapping_area.id)],
        })
        self.assertRedirects(response, url)

        self.assertTrue(
            DatasetUserMappingArea.objects.filter(
                dataset=self.dataset,
                user=self.user,
                mapping_area=self.mapping_area,
            ).exists()
        )
        self.assertTrue(
            DatasetGroupMappingArea.objects.filter(
                dataset=self.dataset,
                group=self.group,
                mapping_area=self.mapping_area,
            ).exists()
        )

    def test_user_sees_only_geometries_within_assigned_mapping_areas(self):
        DatasetUserMappingArea.objects.create(
            dataset=self.dataset,
            user=self.user,
            mapping_area=self.mapping_area,
        )

        response = self.user_client.get(reverse('dataset_map_data', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        map_data = response.json().get('map_data', [])
        self.assertEqual(len(map_data), 1)
        self.assertEqual(map_data[0]['id'], self.geometry_inside.id)

        # Geometry outside the permitted area should return 403
        outside_url = reverse('geometry_details', args=[self.geometry_outside.id])
        outside_response = self.user_client.get(outside_url)
        self.assertEqual(outside_response.status_code, 403)

        # Geometry inside should be accessible
        inside_url = reverse('geometry_details', args=[self.geometry_inside.id])
        inside_response = self.user_client.get(inside_url)
        self.assertEqual(inside_response.status_code, 200)
        self.assertTrue(inside_response.json().get('success'))

    def test_group_mapping_area_limits_apply_when_user_has_group_access(self):
        # Remove direct user share so access is via group
        self.dataset.shared_with.remove(self.user)

        DatasetGroupMappingArea.objects.create(
            dataset=self.dataset,
            group=self.group,
            mapping_area=self.mapping_area,
        )

        response = self.user_client.get(reverse('dataset_map_data', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        map_data = response.json().get('map_data', [])
        self.assertEqual(len(map_data), 1)
        self.assertEqual(map_data[0]['id'], self.geometry_inside.id)

        outside_response = self.user_client.get(reverse('geometry_details', args=[self.geometry_outside.id]))
        self.assertEqual(outside_response.status_code, 403)

    def test_allocated_user_sees_all_points_in_mapping_area_without_dataset_access_rows(self):
        """
        Polygon "Allocated users" must grant the same area-based visibility as
        dataset access mapping limits: all geometries inside the area, none outside.
        """
        self.mapping_area.allocated_users.add(self.user)

        response = self.user_client.get(reverse('dataset_map_data', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        map_data = response.json().get('map_data', [])
        self.assertEqual(len(map_data), 1)
        self.assertEqual(map_data[0]['id'], self.geometry_inside.id)

        outside_response = self.user_client.get(
            reverse('geometry_details', args=[self.geometry_outside.id])
        )
        self.assertEqual(outside_response.status_code, 403)

    def test_allocated_user_sees_all_geometries_in_area_from_any_creator(self):
        """Collaborators see every point in their allocated area, not only their own."""
        other = User.objects.create_user(username='other_contributor', password='pass')
        self.dataset.shared_with.add(other)

        geometry_other_inside = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz='IN2',
            address='Inside by other',
            geometry=Point(0.02, 0.02, srid=4326),
            user=other,
        )

        self.mapping_area.allocated_users.add(self.user)

        response = self.user_client.get(reverse('dataset_map_data', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        ids = {row['id'] for row in response.json().get('map_data', [])}
        self.assertSetEqual(ids, {self.geometry_inside.id, geometry_other_inside.id})

    def test_collaborator_mapping_area_outlines_endpoint_returns_geometry(self):
        DatasetUserMappingArea.objects.create(
            dataset=self.dataset,
            user=self.user,
            mapping_area=self.mapping_area,
        )
        url = reverse('mapping_area_outlines', args=[self.dataset.id])
        response = self.user_client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['mapping_areas']), 1)
        self.assertEqual(data['mapping_areas'][0]['id'], self.mapping_area.id)
        self.assertEqual(data['mapping_areas'][0]['geometry']['type'], 'Polygon')

    def test_owner_mapping_area_outlines_endpoint_returns_empty(self):
        """Owners use the full mapping-areas list API; outlines stay empty."""
        url = reverse('mapping_area_outlines', args=[self.dataset.id])
        response = self.owner_client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mapping_areas'], [])

