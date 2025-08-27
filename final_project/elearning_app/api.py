from datetime import datetime
from rest_framework import generics, status, views, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import ValidationError as DRFValidationError
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from .models import *
from .serializers import *
from .tasks import *

# Users
@extend_schema(
    tags=["Auth"],
    responses={200: MessageSerializer, 401: MessageSerializer}
)
class UserLoginView(views.APIView):
    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")

        user = authenticate(request, email=email, password=password)
        if user:
            if not user.is_active:
                user.is_active = True
                user.last_login = datetime.now()
                user.save(update_fields=["is_active", "last_login"])
            login(request, user)
            refresh = RefreshToken.for_user(user)
            return Response({"refresh": str(refresh), "access": str(refresh.access_token)}, status=status.HTTP_200_OK)
        return Response({"message": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

@extend_schema(
    tags=["Auth"],
    responses={200: MessageSerializer, 400: MessageSerializer}
)
class UserLogoutView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            logout(request)
            refresh_token = request.data.get("refresh")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Logged out successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=["Users"])
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.prefetch_related(
        "enrollments",
        "status_updates",
        "course_reviews"
    )
    serializer_class = UserSerializer

    def perform_update(self, serializer):
        user = serializer.save()
        if "profile_picture" in serializer.validated_data:
            resize_profile_picture.delay(user.pk)

@extend_schema(tags=["Users"])
class UserListView(generics.ListAPIView):
    queryset = User.objects.prefetch_related(
        "enrollments",
        "status_updates",
        "course_reviews"
    )
    serializer_class = UserSerializer

@extend_schema(tags=["Status Updates"])
class StatusUpdateDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StatusUpdate.objects.all()
    serializer_class = StatusUpdateSerializer

@extend_schema(tags=["Status Updates"])
class StatusUpdateListCreateView(generics.ListCreateAPIView):
    serializer_class = StatusUpdateSerializer

    def get_queryset(self):
        pk = self.kwargs.get("pk")
        course = self.request.data.get("course")
        if pk:
            student = get_object_or_404(User, pk=pk)
            return StatusUpdate.objects.filter(student=student, course=course)
        return StatusUpdate.objects.all()
    
    def perform_create(self, serializer):
        student = self.request.user
        course = get_object_or_404(Course, pk=self.request.data.get("course"))
        try:
            course_progress = course.get_user_progress(student)
            serializer.save(student=student, course=course, course_progress=course_progress)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

@extend_schema(tags=["Users"])
class UserBlockView(
    generics.CreateAPIView,
    generics.DestroyAPIView
):
    serializer_class = UserBlockSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        blocked_user_id = request.data.get("blocked_user")
        blocked_by_id = request.data.get("blocked_by")
        if not blocked_user_id or not blocked_by_id:
            return Response({"error": "Both blocked_user and blocked_by are required."}, status=status.HTTP_400_BAD_REQUEST)
        if blocked_user_id == blocked_by_id:
            return Response({"error": "You cannot block yourself."}, status=status.HTTP_400_BAD_REQUEST)

        blocked_user = get_object_or_404(User, pk=blocked_user_id)
        blocked_by = get_object_or_404(User, pk=blocked_by_id)

        obj, created = UserBlock.objects.get_or_create(blocked_user=blocked_user, blocked_by=blocked_by)
        if not created:
            return Response({"message": "User is already blocked."}, status=status.HTTP_200_OK)
        serializer = self.serializer_class(obj)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        blocked_user_id = request.data.get("blocked_user")
        blocked_by_id = request.data.get("blocked_by")
        if not blocked_user_id or not blocked_by_id:
            return Response({"error": "Both blocked_user and blocked_by are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            obj = UserBlock.objects.get(blocked_user_id=blocked_user_id, blocked_by_id=blocked_by_id)
            obj.delete()
            return Response({"message": "User unblocked successfully."}, status=status.HTTP_204_NO_CONTENT)
        except UserBlock.DoesNotExist:
            return Response({"error": "Block relationship does not exist."}, status=status.HTTP_404_NOT_FOUND)


# Courses
@extend_schema(tags=["Courses"])
class CourseListCreateView(generics.ListCreateAPIView):
    queryset = Course.objects.prefetch_related(
        "modules",
        "modules__lessons",
        "modules__assignments",
        "enrollments__student",
        "status_updates",
    )
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(taught_by=self.request.user)

    def create(self, request, *args, **kwargs):
        user = self.request.user
        if user.role != User.UserRole.TEACHER:
            return Response({"error": "Only teachers can create courses"}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

@extend_schema(tags=["Courses"])
class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.prefetch_related(
        "modules",
        "modules__lessons",
        "modules__assignments",
        "enrollments__student",
        "status_updates",
    )
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        user = self.request.user
        course = get_object_or_404(Course, pk=kwargs.get("pk"))
        if user != course.taught_by:
            return Response({"error": "Only the course's teacher can edit this course"}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

@extend_schema(tags=["Enrollments"])
class EnrollmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Enrollment.objects.all()
    serializer_class = EnrollmentSerializer

    def update(self, request, *args, **kwargs):
        user = self.request.user
        instance = self.get_object()
        if user != instance.student and user != instance.course.taught_by:
            return Response({"error": "Only student and teacher can modify an enrollment"}, status=status.HTTP_403_FORBIDDEN)
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

@extend_schema(tags=["Enrollments"])
class EnrollmentListCreateView(generics.ListCreateAPIView):
    serializer_class = EnrollmentSerializer

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs.get("pk"))
        student = self.request.user
        return Enrollment.objects.filter(student=student, course=course)
    
    def create(self, request, *args, **kwargs):
        course_id = kwargs.get("pk")
        user_id = request.data.get("user_id")

        if not user_id:
            return Response({"error": "No user_id was provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Check that both user and course exist
            user = get_object_or_404(User, pk=user_id)
            course = get_object_or_404(Course, pk=course_id)

            # Check that the user is a student and can be enrolled
            if user.role != User.UserRole.STUDENT:
                return Response({"error": "User is not a student and cannot be enrolled in a course"}, status=status.HTTP_400_BAD_REQUEST)

            # Update enrollmen if exists
            existing_enrollment = user.get_enrollment(course)
            if existing_enrollment:
                if existing_enrollment.status == Enrollment.EnrollmentStatus.CANCELED:
                    # Reactivate enrollment if canceled
                    existing_enrollment.status = Enrollment.EnrollmentStatus.ACTIVE
                    existing_enrollment.save(update_fields=["status"])
                if existing_enrollment.status == Enrollment.EnrollmentStatus.COMPLETED:
                    return Response({"error": "The user has already completed this course"}, status=status.HTTP_400_BAD_REQUEST)
                return Response(EnrollmentSerializer(existing_enrollment).data, status=status.HTTP_200_OK)
            
            # Create enrollment
            serializer = self.get_serializer(data={"course": course.pk, "student": user.pk})
            serializer.is_valid(raise_exception=True)
            enrollment = serializer.save()

            return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=["Course Reviews"])
class CourseReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CourseReview.objects.all()
    serializer_class = CourseReviewSerializer

@extend_schema(tags=["Course Reviews"])
class CourseReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = CourseReviewSerializer

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs.get("pk"))
        return CourseReview.objects.filter(course=course)
    
    def perform_create(self, serializer):
        course = get_object_or_404(Course, pk=self.kwargs.get("pk"))
        student = self.request.user
        try:
            progress = course.get_user_progress(student)
            if progress < 100:
                raise DRFValidationError("Only users who have completed the course can leave reviews.")
            serializer.save(course=course, student=student)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

# Modules
@extend_schema(tags=["Modules"])
class ModuleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Module.objects.prefetch_related(
        "lessons",
        "assignments"
    )
    serializer_class = ModuleSerializer
    
@extend_schema(tags=["Modules"])
class ModuleListCreateView(generics.ListCreateAPIView):
    serializer_class = ModuleSerializer

    def get_queryset(self):
        course = get_object_or_404(Course, pk=self.kwargs.get("pk"))
        return Module.objects.filter(course=course).prefetch_related(
            "lessons",
            "assignments"
        )
    
    def perform_create(self, serializer):
        course = get_object_or_404(Course, pk=self.kwargs.get("pk"))
        try:
            serializer.save(course=course)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

# Lessons
@extend_schema(tags=["Lessons"])
class LessonDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = LessonSerializer

    def get_queryset(self):
        user = self.request.user
        # If user is a student, return their progress in this lesson
        if user.role == User.UserRole.STUDENT:
            return Lesson.objects.filter(user_progress__student=user).prefetch_related(
                "user_progress",
            )
        # If user is a teacher or admin, return all student's progress in this lesson
        else:
            return Lesson.objects.prefetch_related(
                "user_progress",
            )

@extend_schema(tags=["Lessons"])
class LessonListCreateView(generics.ListCreateAPIView):
    serializer_class = LessonSerializer

    def get_queryset(self):
        module = get_object_or_404(Module, pk=self.kwargs.get("pk"))
        return Lesson.objects.filter(module=module).prefetch_related(
            "user_progress"
        )
    
    def perform_create(self, serializer):
        module = get_object_or_404(Module, pk=self.kwargs.get("pk"))
        try:
            instance = serializer.save(module=module)
            instance.full_clean()
            instance.save()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

@extend_schema(tags=["Lessons"])
class LessonProgressDetailView(
    generics.CreateAPIView,
    generics.UpdateAPIView,
    generics.RetrieveAPIView,
):
    serializer_class = LessonProgressSerializer

    def get_queryset(self):
        lesson = get_object_or_404(Lesson, pk=self.kwargs.get("pk"))
        student = self.request.user
        return LessonProgress.objects.filter(student=student, lesson=lesson)
    
    def put(self, request, *args, **kwargs):
        try:
            lesson = get_object_or_404(Lesson, pk=kwargs.get("pk"))
            student = self.request.user
        
            if student.role != User.UserRole.STUDENT:
                return Response({"message": "Only students can update their progress in a module"}, status=status.HTTP_403_FORBIDDEN)
            
            completed = request.data.get("completed")
            lesson_progress, created = LessonProgress.objects.update_or_create(
                student=student,
                lesson=lesson,
                defaults={"completed": completed}
            )
            return Response({"message": "User's lesson progress updated successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": f"Unexpected error updating user's lesson progress: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

# Assignments
@extend_schema(tags=["Assignments"])
class AssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Assignment.objects.prefetch_related(
        "assignment_submissions",
    )
    serializer_class = AssignmentSerializer

@extend_schema(tags=["Assignments"])
class AssignmentListCreateView(generics.ListCreateAPIView):
    serializer_class = AssignmentSerializer

    def get_queryset(self):
        module = get_object_or_404(Module, pk=self.kwargs.get("pk"))
        return Assignment.objects.filter(module=module).prefetch_related(
            "assignment_submissions"
        )
    
    def perform_create(self, serializer):
        module = get_object_or_404(Module, pk=self.kwargs.get("pk"))
        try:
            instance = serializer.save(module=module)
            instance.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

@extend_schema(tags=["Assignments"])
class AssignmentSubmissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = AssignmentSubmission.objects.all()
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def dispatch(self, request, *args, **kwargs):
        submission = get_object_or_404(AssignmentSubmission, pk=kwargs.get("pk"))
        user = self.request.user
        teacher = submission.assignment.module.course.taught_by

        # Only submitter and course teacher can view
        if request.method == "GET":
            if user != submission.student and user != teacher:
                return Response({"error": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        # Only submitter can modify or delete
        if request.method in ("PUT", "PATCH", "DELETE"):
            if user != submission.student:
                return Response({"error": "Only the submitter can modify or delete this submission."}, status=status.HTTP_403_FORBIDDEN)

        return super().dispatch(request, *args, **kwargs)

@extend_schema(
    tags=["Assignments"],
    responses={200: MessageSerializer, 400: MessageSerializer, 403: MessageSerializer}
)
class AssignmentSubmissionGradeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        submission = get_object_or_404(AssignmentSubmission, pk=pk)
        teacher = submission.assignment.module.course.taught_by
        user = request.user

        if user != teacher:
            return Response({"error": "Only the course teacher can grade this submission."}, status=status.HTTP_403_FORBIDDEN)

        grade = request.data.get("grade")
        feedback = request.data.get("feedback", "")

        if grade is None:
            return Response({"error": "Grade is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grade = float(grade)
            if not (0.0 <= grade <= 100.0):
                raise ValueError
        except ValueError:
            return Response({"detail": "Grade must be a number between 0 and 100."}, status=status.HTTP_400_BAD_REQUEST)

        submission.grade = grade
        submission.feedback = feedback
        submission.save(update_fields=["grade", "feedback"])
        return Response({"message": "Submission graded successfully."}, status=status.HTTP_200_OK)
        
@extend_schema(tags=["Assignments"])
class AssignmentSubmissionListCreateView(generics.ListCreateAPIView):
    serializer_class = AssignmentSubmissionSerializer

    def get_queryset(self):
        assignment = get_object_or_404(Assignment, pk=self.kwargs.get("pk"))
        user_role = self.request.user.role
        # If user is a student, return only their own submissions for assignment
        if user_role == User.UserRole.STUDENT:
            return AssignmentSubmission.objects.filter(assignment=assignment, student_id=self.request.user.pk)
        # If user is a teacher or admin, return all submissions for assignment
        else:
            return AssignmentSubmission.objects.filter(assignment=assignment)
        
    def perform_create(self, serializer):
        assignment = get_object_or_404(Assignment, pk=self.kwargs.get("pk"))
        # user = self.request.user
        user = get_object_or_404(User, pk=5)
        try:
            instance = serializer.save(assignment=assignment, student=user)
            instance.full_clean()
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

# Chats
@extend_schema(tags=["Chats"])
class ChatDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChatSerializer

    def get_queryset(self):
        return Chat.objects.filter(
            participants__user=self.request.user
        ).prefetch_related("chat_messages", "participants__user")

@extend_schema(tags=["Chats"])
class ChatListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatSerializer

    def get_queryset(self):
        return Chat.objects.filter(
            participants__user=self.request.user
        ).prefetch_related("chat_messages", "participants__user").distinct()
    
    def create(self, request, *args, **kwargs):
        user_ids = request.data.get("user_ids")
        user_ids = set(user_ids)

        if len(user_ids) < 2:
            return Response({"error": "At least 2 different users are required to start a chat"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            users = [get_object_or_404(User, pk=user_id) for user_id in user_ids]
            current_user = request.user
            
            # Check that current user is one of the participants
            if current_user not in users:
                return Response({"error": "You can only create chats that include yourself"}, status=status.HTTP_403_FORBIDDEN)
            
            # Check if a direct chat already exists with these users
            existing_chat = (
                Chat.objects
                .annotate(
                    num_participants=Count("participants"),
                    num_matching=Count("participants", filter=Q(participants__user__in=user_ids))
                )
                .filter(num_participants=len(users), num_matching=len(users))
                .first()
            )

            if existing_chat:
                return Response(ChatSerializer(existing_chat).data, status=status.HTTP_200_OK)
            
            # Create new direct chat
            with transaction.atomic():
                chat_data = {"title": f"{", ".join([str(user) for user in users])}"}
                
                serializer = self.get_serializer(data=chat_data)
                serializer.is_valid(raise_exception=True)
                chat = serializer.save(created_by=current_user)

                # Create chat participants
                chat_participants = [ChatParticipant(chat=chat, user=user) for user in users]
                ChatParticipant.objects.bulk_create(chat_participants)
                
                return Response(ChatSerializer(chat).data, status=status.HTTP_201_CREATED)
                
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(tags=["Chats"])
class ChatMessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ChatMessage.objects.all()
    serializer_class = ChatMessageSerializer

@extend_schema(tags=["Chats"])
class ChatMessageListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatMessageSerializer
        
    def get_queryset(self):
        chat = get_object_or_404(
            Chat.objects.filter(participants__user=self.request.user),
            pk=self.kwargs.get("pk")
        )
        return ChatMessage.objects.filter(chat=chat).select_related("sender")
    
    def perform_create(self, serializer):
        chat = get_object_or_404(
            Chat.objects.filter(participants__user=self.request.user),
            pk=self.kwargs.get("pk")
        )
        user = self.request.user
        try:
            message = serializer.save(chat=chat, sender=user)
            for file in self.request.FILES.getlist('attachments'):
                ChatMessageAttachments.objects.create(chat_message=message, attachment=file)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

@extend_schema(tags=["Chats"])
class ChatParticipantDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ChatParticipant.objects.all()
    serializer_class = ChatParticipantSerializer

@extend_schema(tags=["Chats"])
class ChatParticipantListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatParticipantSerializer

    def get_queryset(self):
        chat = get_object_or_404(Chat, pk=self.kwargs.get("pk"))
        return ChatParticipant.objects.filter(chat=chat)
    
    def perform_create(self, serializer):
        chat = get_object_or_404(Chat, pk=self.kwargs.get("pk"))
        try:
            serializer.save(chat=chat)
        except DjangoValidationError as e:
            raise DRFValidationError(e.message)

@extend_schema(
    tags=["Users"],
    responses={200: MessageSerializer, 400: MessageSerializer}
)
class NotificationReadView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            notification = get_object_or_404(Notification, pk=kwargs.get("pk"))
            notification.read = True
            notification.save(update_fields=["read"])
            return Response({"message": "Notification dismissed successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)