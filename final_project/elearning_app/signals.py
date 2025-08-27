from datetime import datetime
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import *

@receiver(post_save, sender=Module)
def module_create_notification(sender, instance: Module, created, **kwargs):
    """Create notifications for students if module was created after course was published"""
    if created:
        course = instance.course
        if course.is_published:
            enrolled_users = course.enrollments.exclude(status=Enrollment.EnrollmentStatus.CANCELED).select_related("student")
            for enrollment in enrolled_users:
                Notification.objects.create(
                    user=enrollment.student,
                    content=f'New module "{instance.title}" added to course {course.title}',
                    related_course=course
                )
            
@receiver(post_save, sender=Lesson)
def lesson_created_notification(sender, instance: Lesson, created, **kwargs):
    """Create notifications for students if lesson was created after course was published"""
    if created:
        course = instance.course
        if course.is_published:
            enrolled_users = course.enrollments.exclude(status=Enrollment.EnrollmentStatus.CANCELED).select_related("student")
            for enrollment in enrolled_users:
                Notification.objects.create(
                    user=enrollment.student,
                    content=f'New lesson "{instance.title}" added to course {course.title}',
                    related_course=course
                )

@receiver(post_save, sender=LessonProgress)
def mark_enrollment_completed_on_lessons_completed(sender, instance: LessonProgress, created, **kwargs):
    """Mark course enrollment as completed if user has completed all lessons"""
    if instance.completed:
        student = instance.student
        course = instance.course

        if course.get_user_progress(student) == 100.0:
            enrollment = student.enrollments.filter(course=course).first()
            enrollment.status = Enrollment.EnrollmentStatus.COMPLETED
            enrollment.completed_on = datetime.now()
            update_fields=["status", "completed_on"]
            final_grade = student.get_final_grade(course)
            if final_grade:
                enrollment.final_grade = student.get_final_grade(course)
                Notification.objects.create(
                    user=student,
                    content=f"Final grade for course {course.title} has been updated",
                    related_course=course
                )
                update_fields.append("final_grade")
            enrollment.save(update_fields=update_fields)

@receiver(post_save, sender=Enrollment)
def enrollment_notification(sender, instance: Enrollment, created, **kwargs):
    """Notify a teacher when a student enrolls in their course and update timestamps if status is updated"""
    if created:
        student = instance.student
        teacher = instance.teacher
        Notification.objects.create(
            user=teacher,
            content=f'{student} has enrolled in course {instance.course.title}',
            related_course=instance.course
        )
    else:
        if instance.status == Enrollment.EnrollmentStatus.COMPLETED and instance.completed_on is None:
            instance.completed_on = datetime.now()
            instance.save(update_fields=["completed_on"])
        elif instance.status == Enrollment.EnrollmentStatus.CANCELED and instance.canceled_on is None:
            instance.canceled_on = datetime.now()
            instance.save(update_fields=["canceled_on"])
        elif instance.status == Enrollment.EnrollmentStatus.REMOVED and instance.removed_on is None:
            instance.removed_on = datetime.now()
            instance.save(update_fields=["removed_on"])

@receiver(post_save, sender=AssignmentSubmission)
def assignment_submission_notifications(sender, instance: AssignmentSubmission, created, **kwargs):
    """Notify a teacher when a student submits an assignment and notify a student when a teacher grades their assignment. Also, mark enrollment complete if course complete"""
    student = instance.student
    teacher = instance.teacher
    course = instance.assignment.module.course
    if created:
        Notification.objects.create(
            user=teacher,
            content=f'{student} has submitted assignment {instance.assignment.title}',
            related_course=instance.assignment.module.course
        )
    elif instance.grade:
        Notification.objects.create(
            user=student,
            content=f'Assignment submission for {instance.assignment.title} has been graded',
            related_course=instance.assignment.module.course
        )
        if course.get_user_progress(student) == 100.0:
            enrollment = student.enrollments.filter(course=course).first()
            enrollment.status = Enrollment.EnrollmentStatus.COMPLETED
            enrollment.completed_on = datetime.now()
            update_fields=["status", "completed_on"]
            final_grade = student.get_final_grade(course)
            if final_grade:
                enrollment.final_grade = student.get_final_grade(course)
                Notification.objects.create(
                    user=student,
                    content=f"Final grade for course {course.title} has been updated",
                    related_course=course
                )
                update_fields.append("final_grade")
                enrollment.save(update_fields=update_fields)

@receiver(post_save, sender=UserBlock)
def remove_enrollments_on_block(sender, instance: UserBlock, created, **kwargs):
    """Remove the user's enrollment (if exists) from all of the teacher's courses"""
    if created:
        teacher = instance.blocked_by
        student = instance.blocked_user
        for course in teacher.get_courses():
            Enrollment.objects.filter(course=course, student=student).update(status=Enrollment.EnrollmentStatus.REMOVED, completed_on=datetime.now())
