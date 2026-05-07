"""Anonymous welcome modal fields and dataset field config flags."""

import json
import uuid

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from datasets.models import DataSet, DatasetField, VirtualContributor
from datasets.views.dataset_views import normalize_welcome_field_submission


class NormalizeWelcomeSubmissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", password="p")
        self.dataset = DataSet.objects.create(name="D", owner=self.owner)
        self.field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name="note",
            label="Note",
            field_type="text",
            enabled=True,
            anonymous_welcome=True,
        )

    def test_accepts_whitelisted_key(self):
        out = normalize_welcome_field_submission(self.dataset, {"note": "hello"})
        self.assertEqual(out, {"note": "hello"})

    def test_drops_unknown_keys(self):
        out = normalize_welcome_field_submission(self.dataset, {"note": "x", "other": "y"})
        self.assertEqual(out, {"note": "x"})

    def test_required_missing_raises(self):
        self.field.required = True
        self.field.save(update_fields=["required"])
        with self.assertRaises(ValueError):
            normalize_welcome_field_submission(self.dataset, {})


class RegisterVirtualUserWelcomeTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", password="p")
        self.dataset = DataSet.objects.create(
            name="D",
            owner=self.owner,
            allow_anonymous_data_input=True,
        )
        self.dataset.ensure_anonymous_access_token()
        self.dataset.refresh_from_db()
        DatasetField.objects.create(
            dataset=self.dataset,
            field_name="org",
            label="Org",
            field_type="text",
            enabled=True,
            anonymous_welcome=True,
        )
        self.client = Client()

    def _session(self):
        s = self.client.session
        s[f"anonymous_token_{self.dataset.id}"] = self.dataset.anonymous_access_token
        s.save()

    def test_stores_welcome_values(self):
        self._session()
        u = str(uuid.uuid4())
        url = reverse("register_virtual_user", args=[self.dataset.id])
        r = self.client.post(
            url,
            data=json.dumps(
                {"uuid": u, "display_name": "Tester", "welcome_fields": {"org": "ACME"}}
            ),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("success"))
        vc = VirtualContributor.objects.get(dataset=self.dataset, uuid=u)
        self.assertEqual(vc.welcome_field_values.get("org"), "ACME")

    def test_rejects_value_for_non_welcome_field(self):
        DatasetField.objects.create(
            dataset=self.dataset,
            field_name="hidden",
            label="Hidden",
            field_type="text",
            enabled=True,
            anonymous_welcome=False,
        )
        self._session()
        u = str(uuid.uuid4())
        url = reverse("register_virtual_user", args=[self.dataset.id])
        r = self.client.post(
            url,
            data=json.dumps(
                {
                    "uuid": u,
                    "display_name": "",
                    "welcome_fields": {"org": "OK", "hidden": "nope"},
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        vc = VirtualContributor.objects.get(dataset=self.dataset, uuid=u)
        self.assertEqual(vc.welcome_field_values.get("org"), "OK")
        self.assertNotIn("hidden", vc.welcome_field_values)


class DatasetDetailAnonymousWelcomeColumnTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", password="p")
        self.dataset = DataSet.objects.create(
            name="D",
            owner=self.owner,
            allow_anonymous_data_input=True,
        )
        self.field = DatasetField.objects.create(
            dataset=self.dataset,
            field_name="x",
            label="X",
            field_type="text",
            enabled=True,
            order=0,
        )
        self.client = Client()
        self.client.force_login(self.owner)

    def test_update_fields_sets_anonymous_welcome(self):
        url = reverse("dataset_detail", args=[self.dataset.id])
        r = self.client.post(
            url,
            {
                "action": "update_fields",
                f"field_{self.field.id}_order": "0",
                f"field_{self.field.id}_enabled": "on",
                f"field_{self.field.id}_anonymous_welcome": "on",
            },
        )
        self.assertEqual(r.status_code, 302)
        self.field.refresh_from_db()
        self.assertTrue(self.field.anonymous_welcome)

    def test_disables_anonymous_welcome_when_anon_input_off(self):
        self.dataset.allow_anonymous_data_input = False
        self.dataset.save(update_fields=["allow_anonymous_data_input"])
        self.field.anonymous_welcome = True
        self.field.save(update_fields=["anonymous_welcome"])
        url = reverse("dataset_detail", args=[self.dataset.id])
        self.client.post(
            url,
            {
                "action": "update_fields",
                f"field_{self.field.id}_order": "0",
                f"field_{self.field.id}_enabled": "on",
            },
        )
        self.field.refresh_from_db()
        self.assertFalse(self.field.anonymous_welcome)


class ResetAnonymousVirtualUserTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="o", password="p")
        self.dataset = DataSet.objects.create(
            name="Reset",
            owner=self.owner,
            allow_anonymous_data_input=True,
        )
        self.dataset.ensure_anonymous_access_token()
        self.dataset.refresh_from_db()
        self.client = Client()

    def _session(self):
        s = self.client.session
        s[f"anonymous_token_{self.dataset.id}"] = self.dataset.anonymous_access_token
        s.save()

    def test_post_clears_session_and_redirects_with_flag(self):
        self._session()
        u = str(uuid.uuid4())
        reg = reverse("register_virtual_user", args=[self.dataset.id])
        r = self.client.post(
            reg,
            data=json.dumps({"uuid": u, "display_name": "Someone"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)

        sess = self.client.session
        self.assertEqual(sess.get(f"virtual_contributor_uuid_{self.dataset.id}"), u)

        rst = reverse("reset_anonymous_virtual_user", args=[self.dataset.id])
        r2 = self.client.post(rst)
        self.assertEqual(r2.status_code, 302)
        self.assertIn("anonymous_session_reset=1", r2["Location"])

        sess = self.client.session
        self.assertIsNone(sess.get(f"virtual_contributor_uuid_{self.dataset.id}"))

    def test_forbidden_when_not_in_anonymous_session(self):
        rst = reverse("reset_anonymous_virtual_user", args=[self.dataset.id])
        self.assertEqual(self.client.post(rst).status_code, 403)

    def test_get_not_allowed(self):
        self._session()
        rst = reverse("reset_anonymous_virtual_user", args=[self.dataset.id])
        self.assertEqual(self.client.get(rst).status_code, 405)
