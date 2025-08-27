import io
from celery import shared_task
from PIL import Image
from django.core.files.base import ContentFile
from datetime import timedelta
from .models import *

@shared_task
def resize_profile_picture(user_id):
    """Crops and resizes a profile picture to a centered 200x200 square."""
    try:
        user = User.objects.get(pk=user_id)
        if not user.profile_picture:
            return

        # Open the existing image
        img = Image.open(user.profile_picture)
        img = img.convert("RGB")  # Ensure consistent format

        # Crop to square (centered)
        width, height = img.size
        min_dim = min(width, height)
        left = (width - min_dim) // 2
        top = (height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        img = img.crop((left, top, right, bottom))

        # Resize to 200x200
        img = img.resize((200, 200), Image.Resampling.LANCZOS)

        # Save the resized image to memory
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=90)
        buffer.seek(0)

        # Create a new file name
        file_name = f"profile_{user_id}.jpg"

        # Save back to the field (overwrite old one)
        user.profile_picture.save(file_name, ContentFile(buffer.read()), save=True)

    except User.DoesNotExist:
        return
    
@shared_task
def notify_upcoming_assignment_deadlines():
    """Creates notifications for users when an assignment is a week away and hasn't been submitted"""
    now = timezone.now()
    week_from_now = now + timedelta(days=7)
    assignments = Assignment.objects.filter(
        deadline__date=week_from_now.date()
    )
    for assignment in assignments:
        course = assignment.module.course
        # Get all active enrollments for the course
        enrolled_users = course.enrollments.filter(
            status=Enrollment.EnrollmentStatus.ACTIVE
        ).select_related("student")

        # Get users who already submitted the assignment
        users_who_submitted_ids = set(
            assignment.assignment_submissions.values_list("student_id", flat=True)
        )

        # Send notification to users who have not submitted yet
        for enrollment in enrolled_users:
            if enrollment.student not in users_who_submitted_ids:
                Notification.objects.create(
                    related_course=course,
                    user=enrollment.student,
                    content=f'Assignment "{assignment.title}" is due in one week for course {course.title}.',
                )