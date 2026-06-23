from django.test import TestCase
from django.urls import reverse

from .models import Student, NewUsers


def make_student(name, email, phone):
    """Helper: create a NewUsers + Student pair (mirrors the register view)."""
    user = NewUsers.objects.create(
        name=name, email=email, phone_number=phone, password="pw123"
    )
    return Student.objects.create(user=user)


class SearchStudentsViewTests(TestCase):
    def setUp(self):
        self.alice = make_student("Alice Smith", "alice@example.com", "1111111111")
        self.bob = make_student("Bob Jones", "bob@example.com", "2222222222")

    def test_search_matches_by_name(self):
        response = self.client.get(reverse("search_students"), {"q": "alice"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertNotContains(response, "Bob Jones")

    def test_search_is_case_insensitive(self):
        response = self.client.get(reverse("search_students"), {"q": "ALICE"})
        self.assertContains(response, "Alice Smith")

    def test_search_supports_partial_match(self):
        response = self.client.get(reverse("search_students"), {"q": "lic"})
        self.assertContains(response, "Alice Smith")
        self.assertNotContains(response, "Bob Jones")

    def test_search_empty_query_returns_all(self):
        response = self.client.get(reverse("search_students"), {"q": ""})
        self.assertContains(response, "Alice Smith")
        self.assertContains(response, "Bob Jones")

    def test_search_no_matches_shows_empty_message(self):
        response = self.client.get(reverse("search_students"), {"q": "zzz"})
        self.assertContains(response, "No students found")
        self.assertNotContains(response, "Alice Smith")

    def test_display_students_filters_by_q(self):
        response = self.client.get(reverse("display_students"), {"q": "alice"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Smith")
        self.assertNotContains(response, "Bob Jones")
