from django.test import Client, TestCase
from django.urls import reverse

from django.contrib.auth.models import User


class DocumentationViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='docuser', email='doc@example.com', password='pass')
        self.url = reverse('documentation')

    def test_authenticated_user_gets_200(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'datasets/documentation.html')

    def test_anonymous_user_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
