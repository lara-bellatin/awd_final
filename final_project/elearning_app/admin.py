from django.contrib import admin
from .models import *

# Tabular Inlines
class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0

class AssignmentSubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0

class StatusUpdateInline(admin.TabularInline):
    model = StatusUpdate
    extra = 0

class CourseReviewInline(admin.TabularInline):
    model = CourseReview
    extra = 0

class CourseInline(admin.TabularInline):
    model = Course
    extra = 0

class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 2

class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 1

class ChatInline(admin.TabularInline):
    model = Chat
    extra = 0

class ChatParticipantInline(admin.TabularInline):
    model = ChatParticipant
    extra = 2

class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0

class ChatMessageAttachmentInline(admin.TabularInline):
    model = ChatMessageAttachments
    extra = 0

class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0

# Admin classes
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "first_name", "last_name", "role", "profile_picture", "is_active", "is_staff")
    fields = ("email", "first_name", "last_name", "profile_picture", "bio")
    search_fields = ("id", "email", "first_name", "last_name", "profile_picture")

    def get_inlines(self, request, obj=None):
        """Return different inlines depending on the user's role"""
        if obj is None:
            return []
        
        if obj.role == User.UserRole.TEACHER:
            return [
                CourseInline,
                ChatInline
            ]
        elif obj.role == User.UserRole.STUDENT:
            return [
                EnrollmentInline,
                AssignmentSubmissionInline,
                StatusUpdateInline,
                CourseReviewInline
            ]
        else:
            return []

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "taught_by", "is_published", "start_date", "end_date")
    list_filter = ("is_published", "taught_by")
    search_fields = ("title", "taught_by__email")
    inlines = [EnrollmentInline, ModuleInline, CourseReviewInline]

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "course")
    search_fields = ("title", "course__title")
    list_filter = ("course",)
    inlines = [LessonInline, AssignmentInline]

@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "created_by", "is_active", "created_at")
    search_fields = ("title", "created_by__email")
    inlines = [ChatParticipantInline, ChatMessageInline]

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "sender", "sent_at")
    search_fields = ("chat__title", "sender__email", "text")
    inlines = [ChatMessageAttachmentInline]

@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "module")
    search_fields = ("title", "module__title")
    list_filter = ("module",)
    inlines = [LessonProgressInline]

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "module", "weight")
    search_fields = ("title", "module__title")
    list_filter = ("module",)
    inlines = [AssignmentSubmissionInline]

@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "course", "status", "activated_on")
    list_filter = ("status", "course")
    search_fields = ("student__email", "course__title")

@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "course", "rating", "created_at")
    search_fields = ("student__email", "course__title")
    list_filter = ("course",)

@admin.register(StatusUpdate)
class StatusUpdateAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "course", "course_progress", "created_at")
    search_fields = ("student__email", "course__title")
    list_filter = ("course",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "content", "user", "related_course")
    search_fields = ("content", "user", "related_course")
    list_filter = ("user", )

@admin.register(UserBlock)
class UserBlockAdmin(admin.ModelAdmin):
    list_display = ("id", "blocked_user", "blocked_by", "created_at")
    search_fields = ("blocked_user__email", "blocked_by__email")
    list_filter = ("blocked_by", "blocked_user")