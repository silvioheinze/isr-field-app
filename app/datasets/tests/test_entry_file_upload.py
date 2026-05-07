from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.gis.geos import Point

from ..models import DataSet, DataGeometry, DataEntry, DataEntryFile


@override_settings(STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage")
class EntryFileUploadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u1", password="pw")
        self.dataset = DataSet.objects.create(name="DS", owner=self.user)
        self.geometry = DataGeometry.objects.create(
            dataset=self.dataset,
            id_kurz="G1",
            address="A",
            geometry=Point(15.0, 48.0),
            user=self.user,
        )
        self.entry = DataEntry.objects.create(
            geometry=self.geometry,
            name="E1",
            year=2024,
            user=self.user,
        )

    def test_upload_requires_entry_id(self):
        self.client.force_login(self.user)
        img = SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg")
        r = self.client.post(
            reverse("upload_files"),
            {"geometry_id": str(self.geometry.id)},
            files={"files": img},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json().get("success"))

    def test_upload_attaches_to_existing_entry(self):
        self.client.force_login(self.user)
        img = SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg")
        r = self.client.post(
            reverse("upload_files"),
            {
                "geometry_id": str(self.geometry.id),
                "entry_id": str(self.entry.id),
            },
            files={"files": img},
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json().get("success"))
        self.assertEqual(DataEntryFile.objects.filter(entry=self.entry).count(), 1)

    def test_none_mode_rejects_upload(self):
        self.dataset.data_input_attachments_mode = DataSet.DATA_INPUT_ATTACHMENTS_NONE
        self.dataset.save()
        self.client.force_login(self.user)
        img = SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg")
        r = self.client.post(
            reverse("upload_files"),
            {
                "geometry_id": str(self.geometry.id),
                "entry_id": str(self.entry.id),
            },
            files={"files": img},
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json().get("success"))

    def test_geometry_files_filtered_by_entry(self):
        other = DataEntry.objects.create(
            geometry=self.geometry,
            name="E2",
            year=2024,
            user=self.user,
        )
        DataEntryFile.objects.create(
            entry=self.entry,
            file=SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg"),
            filename="a.jpg",
            file_type="image/jpeg",
            file_size=1,
            upload_user=self.user,
        )
        DataEntryFile.objects.create(
            entry=other,
            file=SimpleUploadedFile("b.jpg", b"y", content_type="image/jpeg"),
            filename="b.jpg",
            file_type="image/jpeg",
            file_size=1,
            upload_user=self.user,
        )
        self.client.force_login(self.user)
        url = reverse("geometry_files", kwargs={"geometry_id": self.geometry.id})
        r = self.client.get(url, {"entry_id": str(self.entry.id)})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(data["files"][0]["original_name"], "a.jpg")

    def test_ajax_create_entry_accepts_image_attachment(self):
        self.client.force_login(self.user)
        img = SimpleUploadedFile("new.jpg", b"x", content_type="image/jpeg")
        r = self.client.post(
            reverse("entry_create", kwargs={"geometry_id": self.geometry.id}),
            {"name": "With file"},
            files={"files": img},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 200)
        payload = r.json()
        self.assertTrue(payload.get("success"))
        entry = DataEntry.objects.get(pk=payload["entry_id"])
        self.assertEqual(entry.name, "With file")
        self.assertEqual(DataEntryFile.objects.filter(entry=entry).count(), 1)
        f = DataEntryFile.objects.get(entry=entry)
        self.assertEqual(f.filename, "new.jpg")

    def test_ajax_create_entry_rejects_disallowed_audio_when_images_only(self):
        self.dataset.data_input_attachments_mode = DataSet.DATA_INPUT_ATTACHMENTS_IMAGES
        self.dataset.save(update_fields=["data_input_attachments_mode"])
        self.client.force_login(self.user)
        audio = SimpleUploadedFile("note.mp3", b"x", content_type="audio/mpeg")
        r = self.client.post(
            reverse("entry_create", kwargs={"geometry_id": self.geometry.id}),
            {"name": "Bad mime"},
            files={"files": audio},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json().get("success"))
        self.assertFalse(
            DataEntry.objects.filter(geometry=self.geometry, name="Bad mime").exists()
        )

    def test_ajax_create_entry_rejects_files_when_attachment_mode_none(self):
        self.dataset.data_input_attachments_mode = DataSet.DATA_INPUT_ATTACHMENTS_NONE
        self.dataset.save(update_fields=["data_input_attachments_mode"])
        self.client.force_login(self.user)
        img = SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg")
        r = self.client.post(
            reverse("entry_create", kwargs={"geometry_id": self.geometry.id}),
            {"name": "No files please"},
            files={"files": img},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(r.status_code, 400)
        self.assertFalse(DataEntry.objects.filter(name="No files please").exists())
