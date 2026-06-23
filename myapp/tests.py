from django.test import TestCase
from myapp.models import Student, NewUsers, Class_name


def make_student(name, klass, email, phone):
    """Helper: create a NewUsers + Student with the given name and class."""
    user = NewUsers.objects.create(
        name=name,
        email=email,
        phone_number=phone,
        password="pw123",
    )
    return Student.objects.create(user=user, class_name=klass)


class DisplayStudentsSearchFilterTests(TestCase):
    def setUp(self):
        self.class1 = Class_name.objects.create(name="Class 1")
        self.class2 = Class_name.objects.create(name="Class 2")

        # class1: 9 students (8 "Alpha"/"Alice"/"Bob" so filters yield >6 -> page 2)
        make_student("Alice A", self.class1, "alicea@test", "1000000001")
        make_student("Alpha B", self.class1, "alphab@test", "1000000002")
        make_student("Alpha C", self.class1, "alphac@test", "1000000003")
        make_student("Alpha D", self.class1, "alphad@test", "1000000004")
        make_student("Alpha E", self.class1, "alphae@test", "1000000005")
        make_student("Alpha F", self.class1, "alphaf@test", "1000000006")
        make_student("Alpha G", self.class1, "alphag@test", "1000000007")
        make_student("Alpha H", self.class1, "alphah@test", "1000000008")
        make_student("Bob Z", self.class1, "bobz@test", "1000000009")
        # class2: 2 students
        make_student("Alice Wonder", self.class2, "alicew@test", "1000000010")
        make_student("Charlie Delta", self.class2, "charlied@test", "1000000011")

        self.url = "/display_students/"

    def test_no_filter_shows_all(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # First page is ordered by id; Alice A is created first.
        self.assertIn("Alice A", html)
        # The class dropdown is present.
        self.assertIn("Class 1", html)
        self.assertIn("Class 2", html)

    def test_search_by_name(self):
        resp = self.client.get(self.url, {"q": "alice"})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Case-insensitive partial match across both classes.
        self.assertIn("Alice A", html)
        self.assertIn("Alice Wonder", html)
        self.assertNotIn("Bob Z", html)
        self.assertNotIn("Alpha B", html)

    def test_filter_by_class(self):
        resp = self.client.get(self.url, {"class": str(self.class1.id)})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # class1 student present, class2 student absent.
        self.assertIn("Alice A", html)
        self.assertNotIn("Alice Wonder", html)
        self.assertNotIn("Charlie Delta", html)

    def test_combined_name_and_class(self):
        resp = self.client.get(
            self.url, {"q": "alpha", "class": str(self.class1.id)}
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("Alpha B", html)
        # "Alice A" is in class1 but its name does not contain "alpha".
        self.assertNotIn("Alice A", html)
        # "Alice Wonder" is in class2.
        self.assertNotIn("Alice Wonder", html)

    def test_invalid_class_ignored(self):
        resp = self.client.get(self.url, {"class": "abc"})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # Treated as "All classes" — no crash, students still listed.
        self.assertIn("Alice A", html)

    def test_pagination_preserves_filters(self):
        # 7 "alpha" matches in class1 -> page 1 of 6, with a Next link.
        resp = self.client.get(
            self.url, {"q": "alpha", "class": str(self.class1.id)}
        )
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        # The Next link must carry the active filters forward.
        self.assertIn("q=alpha", html)
        self.assertIn("class=%d" % self.class1.id, html)
        self.assertIn("page=2", html)

    def test_empty_results_message(self):
        resp = self.client.get(self.url, {"q": "zzznomatch"})
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn("No students found.", html)
        self.assertNotIn("Alice A", html)
