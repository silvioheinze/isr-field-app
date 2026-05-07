"""Dataset settings: entry name visibility on data input."""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from ..models import DataSet
from ..views.dataset_views import ensure_dataset_field_config


class DatasetSettingsEntryNameTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='u', password='p')
        self.dataset = DataSet.objects.create(name='Settings Test DS', owner=self.user)

    def _post_settings(self, **extra):
        self.dataset.refresh_from_db()
        d = self.dataset
        extra = dict(extra)
        omit_street_view_checkbox = extra.pop('_omit_street_view_checkbox', False)
        data = {
            'name': d.name,
            'description': d.description or '',
        }
        if d.is_public:
            data['is_public'] = 'on'
        if d.allow_multiple_entries:
            data['allow_multiple_entries'] = 'on'
        if d.enable_mapping_areas:
            data['enable_mapping_areas'] = 'on'
        if d.allow_anonymous_data_input:
            data['allow_anonymous_data_input'] = 'on'
        if d.anonymous_show_all_points:
            data['anonymous_show_all_points'] = 'on'
        if d.anonymous_disable_new_points:
            data['anonymous_disable_new_points'] = 'on'
        if getattr(d, 'data_input_show_street_view', True) and not omit_street_view_checkbox:
            data['data_input_show_street_view'] = 'on'
        if d.map_default_lat is not None:
            data['map_default_lat'] = str(d.map_default_lat)
        if d.map_default_lng is not None:
            data['map_default_lng'] = str(d.map_default_lng)
        if d.map_default_zoom is not None:
            data['map_default_zoom'] = str(d.map_default_zoom)
        data.update(extra)
        return self.client.post(
            reverse('dataset_settings', args=[d.id]),
            data,
        )

    def test_settings_page_includes_entry_name_toggle(self):
        ensure_dataset_field_config(self.dataset)
        self.client.login(username='u', password='p')
        response = self.client.get(reverse('dataset_settings', args=[self.dataset.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'show_entry_name_on_data_input')
        self.assertContains(response, 'Show entry name on data input')

    def test_uncheck_clears_name_enabled(self):
        cfg = ensure_dataset_field_config(self.dataset)
        cfg.name_enabled = True
        cfg.save()
        self.client.login(username='u', password='p')
        response = self._post_settings()
        self.assertEqual(response.status_code, 302)
        cfg.refresh_from_db()
        self.assertFalse(cfg.name_enabled)

    def test_check_sets_name_enabled(self):
        cfg = ensure_dataset_field_config(self.dataset)
        cfg.name_enabled = False
        cfg.save()
        self.client.login(username='u', password='p')
        response = self._post_settings(show_entry_name_on_data_input='on')
        self.assertEqual(response.status_code, 302)
        cfg.refresh_from_db()
        self.assertTrue(cfg.name_enabled)

    def test_uncheck_disables_data_input_street_view(self):
        self.dataset.data_input_show_street_view = True
        self.dataset.save(update_fields=['data_input_show_street_view'])
        self.client.login(username='u', password='p')
        r = self._post_settings(_omit_street_view_checkbox=True)
        self.assertEqual(r.status_code, 302)
        self.dataset.refresh_from_db()
        self.assertFalse(self.dataset.data_input_show_street_view)

    def test_post_enables_data_input_street_view(self):
        self.dataset.data_input_show_street_view = False
        self.dataset.save(update_fields=['data_input_show_street_view'])
        self.client.login(username='u', password='p')
        r = self._post_settings(data_input_show_street_view='on')
        self.assertEqual(r.status_code, 302)
        self.dataset.refresh_from_db()
        self.assertTrue(self.dataset.data_input_show_street_view)

    def test_settings_form_includes_street_view_toggle(self):
        ensure_dataset_field_config(self.dataset)
        self.client.login(username='u', password='p')
        r = self.client.get(reverse('dataset_settings', args=[self.dataset.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data_input_show_street_view')
