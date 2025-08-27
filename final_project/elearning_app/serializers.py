from rest_framework import serializers
from .models import *

class EnrollmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Enrollment
        fields = [
            "student",
            "course",
            "status",
            "activated_on",
            "completed_on",
            "canceled_on",
            "final_grade"
        ]
        extra_kwargs = {
            "completed_on": {"required": False, "allow_null": True},
            "canceled_on": {"required": False, "allow_null": True},
            "final_grade": {"required": False, "allow_null": True}
        }

class CourseReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseReview
        fields = [
            "student",
            "course",
            "rating",
            "review",
            "created_at",
        ]
        read_only_fields = ("course", "student", )
        extra_kwargs = {
            "review": {"required": False, "allow_null": True},
        }

    def validate_rating(self, value):
        if value < 0 or value > 5:
            raise serializers.ValidationError("Rating must be a number between 0 and 5")
        return value

    def validate(self, data):
        student = data.get("student")
        course = data.get("course")
        if not student or student.role != User.UserRole.STUDENT:
            raise serializers.ValidationError("Only students can leave course reviews.")

        enrollment = Enrollment.objects.filter(student=student, course=course, status=Enrollment.EnrollmentStatus.COMPLETED).first()
        if not enrollment:
            raise serializers.ValidationError("Student has not completed the course before leaving a review.")

        already_reviewed = CourseReview.objects.filter(student=student, course=course).exists()
        if already_reviewed and not self.instance:
            raise serializers.ValidationError("Student has already left a review for this course.")

        return data

class StatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StatusUpdate
        fields = ["course", "text"]

class UserSerializer(serializers.ModelSerializer):
    enrollments = EnrollmentSerializer(many=True, read_only=True)
    course_reviews = CourseReviewSerializer(many=True, read_only=True)
    status_updates = StatusUpdateSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "role",
            "profile_picture",
            "enrollments",
            "course_reviews",
            "status_updates",
        ]
        read_only_fields = ("id", "enrollments", "course_reviews", "status_updates", )

    def get_courses(self, obj):
        if obj.role != User.UserRole.TEACHER:
            serializers.ValidationError("Non-teacher users cannot own courses")
        else:
            return obj.courses
        
class LessonProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonProgress
        fields = [
            "student",
            "lesson",
            "completed"
        ]
        
class LessonSerializer(serializers.ModelSerializer):
    user_progress = LessonProgressSerializer(many=True, read_only=True)
    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "description",
            "lesson_file",
            "user_progress",
        ]
        read_only_fields = ("module", "user_progress", )

    def validate(self, data):
        description = data.get("description")
        lesson_file = data.get("lesson_file")
        if not (description or lesson_file):
            raise serializers.ValidationError("Lesson must have one of description or file")
        return data

class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentSubmission
        fields = [
            "assignment",
            "student",
            "file_submission",
            "submitted_on",
            "grade",
        ]
        read_only_fields = ("assignment", "student", )
        extra_kwargs = {
            "grade": {"required": False, "allow_null": True}
        }

class AssignmentSerializer(serializers.ModelSerializer):
    assignment_submissions = AssignmentSubmissionSerializer(many=True, read_only=True)

    class Meta:
        model = Assignment
        fields = [
            "title",
            "description",
            "deadline",
            "weight",
            "module",
            "assignment_submissions",
        ]
        read_only_fields = ("module", )
    
    def validate_weight(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("Weight must be between 0 and 100.")
        return value

class ModuleSerializer(serializers.ModelSerializer):
    lessons = LessonSerializer(many=True, read_only=True)
    assignments = AssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = [
            "id",
            "title",
            "description",
            "course",
            "lessons",
            "assignments",
        ]
        read_only_fields = ("course", "lessons", "assignments")

class CourseSerializer(serializers.ModelSerializer):
    modules = ModuleSerializer(many=True, read_only=True)
    course_reviews = CourseReviewSerializer(many=True, read_only=True)
    enrollments = EnrollmentSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "cover_image",
            "start_date",
            "end_date",
            "taught_by",
            "modules",
            "course_reviews",
            "enrollments",
            "is_published",
        ]
        read_only_fields = ("modules", "course_reviews", "enrollments", "id", "taught_by", "cover_image" )

    def validate_taught_by(self, teacher):
        if teacher.role != User.UserRole.TEACHER:
            raise serializers.ValidationError("Course must be taught by a teacher")
        return teacher
    
    def validate(self, data):
        start = data.get("start_date")
        end = data.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError("End date cannot be before start date.")
        return data
    
class ChatParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatParticipant
        fields = "__all__"

class ChatMessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessageAttachments
        fields = ["id", "attachment"]

class ChatMessageSerializer(serializers.ModelSerializer):
    attachments = ChatMessageAttachmentSerializer(many=True, required=False, read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "chat", "sender", "sent_at", "text", "attachments"]

class ChatSerializer(serializers.ModelSerializer):
    participants = ChatParticipantSerializer(many=True, read_only=True)
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = Chat
        fields = [
            "pk",
            "title",
            "picture",
            "participants",
            "messages",
        ]
        read_only_fields = ("participants", "messages", )

class UserBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserBlock
        fields = []
        read_only_fields = ("blocked_user", "blocked_by")

class MessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=False)
    error = serializers.CharField(required=False)