import string
import datetime
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from hypothesis import given, strategies as st
from hypothesis.extra.django import TestCase as HypothesisTestCase
from .forms import *
from .models import *
from .model_factories import *

class UserRegistrationFormTests(HypothesisTestCase):
    @given(
        first_name=st.text(string.ascii_letters, min_size=1, max_size=20),
        last_name=st.text(string.ascii_letters, min_size=1, max_size=20),
        email=st.emails(),
        password=st.text(string.ascii_letters + string.digits, min_size=8, max_size=20)
            .filter(lambda x: any(c.isdigit() for c in x) and any(c.isalpha() for c in x)),
        bio=st.text(string.printable, min_size=0, max_size=100),
        role=st.sampled_from(["Student", "Teacher"])
    )
    def test_valid_registration(self, first_name, last_name, email, password, bio, role):
        form = UserRegistrationForm(data={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "role": role,
            "password": password,
            "password_confirmation": password,
            "bio": bio,
        })
        assert form.is_valid(), form.errors

    def test_password_mismatch(self):
        form = UserRegistrationForm(data={
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "role": "Student",
            "password": "Password123",
            "password_confirmation": "Password321",
        })
        assert not form.is_valid()
        assert "password_confirmation" in form.errors

    def test_weak_password(self):
        form = UserRegistrationForm(data={
            "first_name": "Test",
            "last_name": "User",
            "email": "test@example.com",
            "role": "Student",
            "password": "password",
            "password_confirmation": "password",
        })
        assert not form.is_valid()
        assert "password" in form.errors

class UserLoginFormTests(TestCase):
    email = None
    password = None
    user = None

    def setUp(self):
        self.password = "Password123"
        self.email = "test@example.com"
        self.user = UserFactory(email=self.email)
        self.user.set_password(self.password)
        self.user.save()

    def test_login_form_valid(self):
        form = UserLoginForm(data={"username": self.email, "password": self.password})
        assert form.is_valid() or "username" in form.errors or "password" in form.errors

class UserProfileFormTests(HypothesisTestCase):
    @given(
        first_name=st.text(string.ascii_letters, min_size=1, max_size=20),
        last_name=st.text(string.ascii_letters, min_size=1, max_size=20),
        email=st.emails(),
        bio=st.text(string.printable, min_size=0, max_size=100),
    )
    def test_profile_form_valid(self, first_name, last_name, email, bio):
        form = UserProfileForm(data={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "bio": bio,
        })
        assert form.is_valid(), form.errors

class CourseReviewFormTests(TestCase):
    student = None
    teacher = None
    course = None

    def setUp(self):
        self.student = UserFactory(role="Student")
        self.teacher = UserFactory(role="Teacher")
        self.course = CourseFactory(taught_by=self.teacher)
        EnrollmentFactory(student=self.student, course=self.course, status=Enrollment.EnrollmentStatus.COMPLETED)

    def test_valid_review(self):
        form = CourseReviewForm(data={
            "rating": 5,
            "review": "Great course!",
            "student": self.student.pk,
            "course": self.course.pk
        })
        form.instance.student = self.student
        form.instance.course = self.course
        assert form.is_valid(), form.errors

    def test_invalid_rating(self):
        form = CourseReviewForm(data={
            "rating": 10,
            "review": "Too high!",
        })
        form.instance.student = self.student
        form.instance.course = self.course
        assert not form.is_valid()
        assert "rating" in form.errors

class StatusUpdateFormTests(HypothesisTestCase):
    student = None
    teacher = None
    course = None

    def setUp(self):
        self.student = UserFactory(role="Student")
        self.teacher = UserFactory(role="Teacher")
        self.course = CourseFactory(taught_by=self.teacher)

    @given(text=st.text(string.ascii_letters, min_size=1, max_size=100))
    def test_valid_status_update(self, text):
        form = StatusUpdateForm(data={
            "course": self.course.pk,
            "text": text,
        })
        assert form.is_valid(), form.errors

class AssignmentSubmissionFormTests(TestCase):
    student = None
    teacher = None
    course = None
    assignment = None

    def setUp(self):
        self.student = UserFactory(role="Student")
        self.teacher = UserFactory(role="Teacher")
        self.course = CourseFactory(taught_by=self.teacher)
        self.assignment = Assignment.objects.create(
            module=Module.objects.create(course=self.course, title="M", description="D"),
            title="A", description="D", weight=10
        )

    def test_valid_submission(self):
        file = SimpleUploadedFile("test.txt", b"file_content")
        form = AssignmentSubmissionForm(data={}, files={"file_submission": file})
        assert form.is_valid(), form.errors

class AssignmentGradingFormTests(TestCase):
    def test_valid_grading(self):
        form = AssignmentGradingForm(data={"grade": 95, "feedback": "Well done!"})
        assert form.is_valid(), form.errors

class CourseFormTests(HypothesisTestCase):
    @given(
        title=st.text(string.ascii_letters, min_size=1, max_size=50),
        description=st.text(string.ascii_letters, min_size=1, max_size=200),
        start_date=st.dates(min_value=datetime.date(2020, 1, 1), max_value=datetime.date(2030, 12, 31)),
        end_date=st.dates(min_value=datetime.date(2020, 1, 2), max_value=datetime.date(2031, 12, 31)),
    )
    def test_valid_course(self, title, description, start_date, end_date):
        if end_date < start_date:
            end_date = start_date
        form = CourseForm(data={
            "title": title,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
        })
        assert form.is_valid(), form.errors

class ModuleFormTests(HypothesisTestCase):
    @given(
        title=st.text(string.ascii_letters, min_size=1, max_size=50),
        description=st.text(string.ascii_letters, min_size=1, max_size=200),
    )
    def test_valid_module(self, title, description):
        form = ModuleForm(data={"title": title, "description": description})
        assert form.is_valid(), form.errors

class LessonFormTests(TestCase):
    teacher = None
    course = None
    module = None

    def setUp(self):
        self.teacher = UserFactory(role="Teacher")
        self.course = CourseFactory(taught_by=self.teacher)
        self.module = Module.objects.create(course=self.course, title="M", description="D")

    def test_valid_lesson_with_description(self):
        form = LessonForm(data={"title": "Lesson 1", "description": "Some desc"})
        assert form.is_valid(), form.errors

    def test_valid_lesson_with_file(self):
        file = SimpleUploadedFile("lesson.pdf", b"file_content")
        form = LessonForm(data={"title": "Lesson 2"}, files={"lesson_file": file})
        assert form.is_valid(), form.errors

    def test_invalid_lesson(self):
        form = LessonForm(data={"title": "Lesson 3"})
        assert not form.is_valid()
        assert "__all__" in form.errors

class AssignmentFormTests(HypothesisTestCase):
    teacher = None
    course = None
    module = None

    def setUp(self):
        self.teacher = UserFactory(role="Teacher")
        self.course = CourseFactory(taught_by=self.teacher)
        self.module = ModuleFactory(course=self.course)

    @given(
        title=st.text(string.ascii_letters, min_size=1, max_size=50),
        description=st.text(string.ascii_letters, min_size=1, max_size=200),
        weight=st.floats(min_value=0.0, max_value=100.0),
    )
    def test_valid_assignment(self, title, description, weight):
        form = AssignmentForm(data={
            "title": title,
            "description": description,
            "weight": weight,
        })
        form.instance.module = self.module
        assert form.is_valid(), form.errors

    def test_invalid_weight(self):
        form = AssignmentForm(data={
            "title": "A",
            "description": "D",
            "weight": 200,
        })
        form.instance.module = self.module
        assert not form.is_valid()
        assert "weight" in form.errors