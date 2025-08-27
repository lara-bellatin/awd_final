from django.urls import reverse
from django.contrib.auth.models import Group
from rest_framework import status
from hypothesis import given, strategies as st
from .models import *
from .serializers import *
from .model_factories import *
from hypothesis.extra.django import TestCase as HypothesisTestCase
from rest_framework.test import APIClient
import string

class BaseAPITestCase(HypothesisTestCase):
    password = "StrongPass123"
    student_role = "Student"
    teacher_role = "Teacher"
    admin_role = "Admin"

    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name=cls.student_role)
        Group.objects.get_or_create(name=cls.teacher_role)
        Group.objects.get_or_create(name=cls.admin_role)

    def setUp(self):
        self.client = APIClient()

    def create_student(self, **kwargs):
        return UserFactory(role=self.student_role, password=self.password, **kwargs)

    def create_teacher(self, **kwargs):
        return UserFactory(role=self.teacher_role, password=self.password, **kwargs)

    def create_course(self, **kwargs):
        defaults = {
            "taught_by": kwargs.get("taught_by", self.create_teacher()),
            "title": "Test Course",
            "description": "A course for testing.",
            "start_date": "2025-01-01",
            "end_date": "2025-02-01",
            "is_published": True,
        }
        defaults.update(kwargs)
        return CourseFactory(**defaults)

class UserLoginAPITests(BaseAPITestCase):
    url = None
    user = None

    def setUp(self):
        super().setUp()
        self.url = reverse("api_login")
        self.user = self.create_student()

    def test_login_success(self):
        data = {"email": self.user.email, "password": self.password}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data and "refresh" in response.data

    def test_login_failure(self):
        data = {"email": self.user.email, "password": "WrongPassword"}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

class CourseAPITests(BaseAPITestCase):
    url = None
    teacher = None
    student = None
    course_data = None

    def setUp(self):
        super().setUp()
        self.url = reverse("api_courses")
        self.teacher = self.create_teacher()
        self.student = self.create_student()
        self.client.force_authenticate(user=self.teacher)
        self.course_data = {
            "title": "Test Course",
            "description": "A course for testing.",
            "start_date": "2025-01-01",
            "end_date": "2025-02-01",
            "is_published": True,
        }

    def test_teacher_can_create_course(self):
        response = self.client.post(self.url, data=self.course_data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == self.course_data["title"]

    def test_student_cannot_create_course(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self.url, self.course_data)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_course_list(self):
        self.client.post(self.url, self.course_data)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert any(course["title"] == self.course_data["title"] for course in response.data)

class EnrollmentAPITests(BaseAPITestCase):
    url = None
    teacher = None
    student = None
    course = None

    def setUp(self):
        super().setUp()
        self.teacher = self.create_teacher()
        self.student = self.create_student()
        self.client.force_authenticate(user=self.teacher)
        self.course = self.create_course(taught_by=self.teacher)
        self.url = reverse("api_enrollments", kwargs={"pk": self.course.pk})

    def test_student_can_enroll(self):
        self.client.force_authenticate(user=self.student)
        data = {"user_id": self.student.pk}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["student"] == self.student.pk

    def test_teacher_cannot_enroll(self):
        data = {"user_id": self.teacher.pk}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_400_BAD_REQUEST

class UserBlockAPITests(BaseAPITestCase):
    url = None
    teacher = None
    student = None

    def setUp(self):
        super().setUp()
        self.url = reverse("api_user_block")
        self.teacher = self.create_teacher()
        self.student = self.create_student()
        self.client.force_authenticate(user=self.teacher)

    def test_block_user(self):
        data = {"blocked_user": self.student.pk, "blocked_by": self.teacher.pk}
        response = self.client.post(self.url, data)
        assert response.status_code == status.HTTP_201_CREATED
        assert UserBlock.objects.filter(blocked_user=self.student, blocked_by=self.teacher).exists()

    def test_unblock_user(self):
        UserBlockFactory(blocked_user=self.student, blocked_by=self.teacher)
        data = {"blocked_user": self.student.pk, "blocked_by": self.teacher.pk}
        response = self.client.delete(self.url, data)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not UserBlock.objects.filter(blocked_user=self.student, blocked_by=self.teacher).exists()

class StatusUpdateAPITests(BaseAPITestCase):
    url = None
    student = None
    course = None

    def setUp(self):
        super().setUp()
        self.student = self.create_student()
        self.course = self.create_course()
        self.client.force_authenticate(user=self.student)
        self.url = reverse("api_status_updates", kwargs={"pk": self.student.pk})

    @given(text=st.text(string.ascii_letters, min_size=1, max_size=100))
    def test_create_status_update(self, text):
        data = {"course": self.course.pk, "text": text}
        response = self.client.post(self.url, data)
        assert response.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK)

class NotificationAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_student()
        self.teacher = self.create_teacher()
        self.course = self.create_course(taught_by=self.teacher)
        self.notification = NotificationFactory(user=self.user, related_course=self.course)
        self.client.force_authenticate(user=self.user)
        self.url = reverse("api_notification_read", kwargs={"pk": self.notification.pk})

    def test_notification_read(self):
        response = self.client.post(self.url)
        assert response.status_code == status.HTTP_200_OK
        self.notification.refresh_from_db()
        assert self.notification.read is True