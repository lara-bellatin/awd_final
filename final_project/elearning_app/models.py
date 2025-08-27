from typing import Optional
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

class UserManager(BaseUserManager):
    def create_user(self, email: str, password: Optional[str] = None, **extra_fields):
        if not email:
            raise ValueError("An email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email: str, password: Optional[str] = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        # Add user to Admin group automatically
        user = self.create_user(email, password, **extra_fields)
        admin_group, _ = Group.objects.get_or_create(name=User.UserRole.ADMIN)
        user.groups.add(admin_group)
        return user

class User(AbstractUser):
    class UserRole(models.TextChoices):
        STUDENT = 'Student'
        TEACHER = 'Teacher'
        ADMIN = 'Admin'

    username = None
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    profile_picture = models.ImageField(null=True, blank=True)
    bio = models.CharField(max_length=500, null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def role(self) -> Optional[str]:
        """Returns the user's primary role based on their groups"""
        group = self.groups.first()
        return group.name if group else None
    
    @property
    def full_name(self) -> str:
        """Returns the user f's full name"""
        return self.first_name + " " + self.last_name
    
    def get_blocked_users(self):
        """Returns a list of users this user has blocked"""
        return list(User.objects.filter(blocked_users__blocked_by=self))
    
    def get_blocked_by(self):
        """Returns a list of users who have blocked this user"""
        return list(User.objects.filter(blocked_by__blocked_user=self))
    
    def get_courses(self):
        """Returns the user's actively enrolled courses if they're a student or taught courses if they're a teacher"""
        if self.role == User.UserRole.STUDENT:
            return Course.objects.filter(
                enrollments__student=self,
                enrollments__is_active=True
            )
        elif self.role == User.UserRole.TEACHER:
            return Course.objects.filter(
                taught_by=self
            )
        else:
            return None
    
    def get_enrollment(self, course):
        """Returns the status of the user's enrollment in the specified course or None if not enrolled"""
        return Enrollment.objects.filter(
            student=self,
            course=course,
        ).first()
    
    def get_lessons_completed(self, course):
        """Returns all lessons completed by the user in this course"""
        return Lesson.objects.filter(module__course=course, user_progress__student=self, user_progress__completed=True)
    
    def get_assignments_submitted(self, course):
        """Returns all assignment submissions made by the user in this course"""
        return AssignmentSubmission.objects.filter(assignment__module__course=course, student=self)
    
    def get_final_grade(self, course):
        submissions = self.get_assignments_submitted(course)
        assignments = course.get_all_assignments()
        if assignments.count() != submissions.count() or submissions.filter(grade__isnull=True).exists():
            return None
        final_grade = 0
        for a in submissions:
            final_grade += (a.assignment.weight/100) * a.grade
        return final_grade

    def set_role(self, role: str):
        """Assign the user to the given role group"""
        if role not in User.UserRole.values:
            raise ValueError(f"Invalid role: {role}")
        
        self.groups.clear()
        group, _ = Group.objects.get_or_create(name=role)
        self.groups.add(group)

    def delete(self, *args, **kwargs):
        """Soft delete a user by setting is_active to False instead of deleting record"""
        self.is_active = False
        self.save()

class Course(models.Model):
    title = models.CharField(max_length=256)
    description = models.CharField(max_length=1000, null=True, blank=True)
    taught_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="courses")
    cover_image = models.ImageField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited_at = models.DateTimeField(auto_now=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_published = models.BooleanField(default=False)  # course starts out as "unpublished"

    def __str__(self):
        return self.title
    
    @property
    def status(self):
        """Returns the course's current status (unpublished, upcoming, ongoing, ended)"""
        if self.is_published:
            today = timezone.now().date()
            if self.start_date > today:
                return "upcoming"
            elif self.start_date <= today <= self.end_date:
                return "ongoing"
            else:
                return "ended"
        return "unpublished"
    
    @property
    def duration_weeks(self) -> int:
        """Returns the course's duration in weeks based on start and end date. Rounds up for partial weeks"""
        if self.start_date and self.end_date:
            days = (self.end_date - self.start_date).days
            return max(1, (days + 6) // 7)
        return 0
    
    @property
    def module_count(self) -> int:
        return Module.objects.filter(course=self).count()
    
    @property
    def lesson_count(self) -> int:
        return Lesson.objects.filter(module__course=self).count()
    
    @property
    def assignment_count(self) -> int:
        return Assignment.objects.filter(module__course=self).count()
    
    def get_all_lessons(self):
        return Lesson.objects.filter(module__course=self)
    
    def get_all_assignments(self):
        return Assignment.objects.filter(module__course=self)
    
    def get_user_progress(self, user: User) -> float:
        """
        Returns the user's progress on the course by calculating from assignments submitted and lessons completed
        """
        # Lessons
        all_lessons_count = Lesson.objects.filter(module__course=self).count()
        lessons_completed = user.get_lessons_completed(self)
        completed_lessons_count = len(lessons_completed) if lessons_completed is not None else 0

        # Assignments
        all_assignments_count = Assignment.objects.filter(module__course=self).count()
        assignments_submitted = user.get_assignments_submitted(self)
        submitted_assignments_count = len(assignments_submitted) if assignments_submitted is not None else 0

        total_items = all_lessons_count + all_assignments_count
        completed_items = completed_lessons_count + submitted_assignments_count

        if total_items == 0:
            return 0.0

        return round((completed_items / total_items) * 100, 2)

class Module(models.Model):
    course = models.ForeignKey(to=Course, on_delete=models.CASCADE, related_name="modules")
    title = models.CharField(max_length=256)
    description = models.CharField(max_length=1000, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited_at = models.DateTimeField(auto_now=True)

    @property
    def teacher(self) -> User:
        return self.course.taught_by

class Lesson(models.Model):
    module = models.ForeignKey(to=Module, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=256)
    description = models.CharField(max_length=1000, null=True, blank=True)
    lesson_file = models.FileField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited_at = models.DateTimeField(auto_now=True)

    @property
    def teacher(self) -> User:
        return self.module.teacher
    
    @property
    def course(self) -> Course:
        return self.module.course

    def clean(self):
        """Check if the lesson order assigned to this lesson is higher than the total amount of lessons in the module"""
        if not self.module_id:
            return

    # custom save function with special validation
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class LessonProgress(models.Model):
    student = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(to=Lesson, on_delete=models.CASCADE, related_name="user_progress")
    completed = models.BooleanField()

    @property
    def course(self) -> Course:
        return self.lesson.module.course

class Assignment(models.Model):
    module = models.ForeignKey(to=Module, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=256)
    description = models.CharField(max_length=1000)
    deadline = models.DateTimeField(null=True, blank=True)
    weight = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)], default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited_at = models.DateTimeField(auto_now=True)

    @property
    def teacher(self) -> User:
        return self.module.teacher

    def clean(self):
        """Check if the weight assigned to this course assignment makes the sum of all course assignment weights for the course excede 100"""
        course = self.module.course
        existing_assignments = Assignment.objects.filter(
            module__course=course
        ).exclude(pk=self.pk)

        current_lesson_weight = sum(a.weight for a in existing_assignments)
        if current_lesson_weight + self.weight > 100.0:
            raise ValidationError({"weight": f"Total assignment weight for course '{course.title}' exceeds 100%. Max weight for this assignment is {(100 - current_lesson_weight):.2f}%."})

    # custom save function with special validation
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(to=Assignment, on_delete=models.CASCADE, related_name="assignment_submissions")
    student = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assignment_submissions")
    submitted_on = models.DateTimeField(auto_now_add=True)
    file_submission = models.FileField()
    grade = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)], null=True, blank=True)
    feedback = models.CharField(max_length=500, null=True, blank=True)

    @property
    def teacher(self) -> User:
        return self.assignment.module.teacher

class Enrollment(models.Model):
    class EnrollmentStatus(models.TextChoices):
        ACTIVE = 'Active'
        COMPLETED = 'Completed'
        CANCELED = 'Canceled'
        REMOVED = 'Removed'

    student = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(to=Course, on_delete=models.CASCADE, related_name="enrollments")
    status = models.CharField(max_length=9, choices=EnrollmentStatus, default=EnrollmentStatus.ACTIVE)
    activated_on = models.DateTimeField(auto_now_add=True)
    completed_on = models.DateTimeField(null=True, blank=True)
    canceled_on = models.DateTimeField(null=True, blank=True)
    removed_on = models.DateTimeField(null=True, blank=True)
    final_grade = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)], null=True, blank=True)

    @property
    def teacher(self) -> User:
        return self.course.taught_by

class CourseReview(models.Model):
    student = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="course_reviews")
    course = models.ForeignKey(to=Course, on_delete=models.CASCADE, related_name="course_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(0.0), MaxValueValidator(5.0)])
    review = models.CharField(max_length=500, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class StatusUpdate(models.Model):
    student = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="status_updates")
    course = models.ForeignKey(to=Course, on_delete=models.CASCADE, related_name="status_updates")
    course_progress = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(100.0)])  # progress in course at the point of posting
    text = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

class Chat(models.Model):
    title = models.CharField(max_length=256)
    picture = models.ImageField(null=True, blank=True)
    created_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    last_edited_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    @property
    def last_message(self):
        """Get the last message sent on the channel"""
        return self.messages.order_by('-sent_at').first()

class ChatParticipant(models.Model):
    chat = models.ForeignKey(to=Chat, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_participations")

class ChatMessage(models.Model):
    chat = models.ForeignKey(to=Chat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(auto_now_add=True)
    text = models.CharField(max_length=256)

    def __str__(self):
        return self.text

class ChatMessageAttachments(models.Model):
    chat_message = models.ForeignKey(to=ChatMessage, on_delete=models.CASCADE, related_name="attachments")
    attachment = models.FileField()

    @property
    def sender(self) -> User:
        return self.chat_message.sender
    
    @property
    def chat(self) -> Chat:
        return self.chat_message.chat

class Notification(models.Model):
    user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    related_course = models.ForeignKey(to=Course, on_delete=models.CASCADE, related_name="notifications")
    content = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

class UserBlock(models.Model):
    blocked_user = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_users")
    blocked_by = models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocked_by")
    created_at = models.DateTimeField(auto_now_add=True)