import factory
from django.contrib.auth.models import Group
from .models import *

class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    bio = factory.Faker("sentence")
    password = factory.PostGenerationMethodCall('set_password', 'StrongPass123')

    @factory.post_generation
    def role(self, create, extracted, **kwargs):
        # extracted should be "Student", "Teacher", or "Admin"
        if not create or not extracted:
            return
        group, _ = Group.objects.get_or_create(name=extracted)
        self.groups.add(group)

class CourseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Course

    title = factory.Faker("sentence", nb_words=4)
    description = factory.Faker("paragraph")
    start_date = "2025-01-01"
    end_date = "2025-02-01"
    is_published = True
    taught_by = factory.SubFactory(UserFactory, role="Teacher")

class UserBlockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = UserBlock

    blocked_user = factory.SubFactory(UserFactory, role="Student")
    blocked_by = factory.SubFactory(UserFactory, role="Teacher")

class NotificationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Notification

    user = factory.SubFactory(UserFactory, role="Student")
    related_course = factory.SubFactory(CourseFactory)
    content = factory.Faker("sentence")

class ModuleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Module

    course = factory.SubFactory(CourseFactory)
    title = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("paragraph")

class AssignmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Assignment

    module = factory.SubFactory(ModuleFactory)
    title = factory.Faker("sentence", nb_words=2)
    description = factory.Faker("paragraph")
    weight = 10

class EnrollmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Enrollment

    student = factory.SubFactory(UserFactory, role="Student")
    course = factory.SubFactory(CourseFactory)
    status = Enrollment.EnrollmentStatus.COMPLETED