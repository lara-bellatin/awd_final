from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Count, Q, Avg, Max
from django.db.models.functions import Coalesce
from django.views.generic import ListView, DetailView
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from django_htmx.http import HttpResponseClientRefresh as HTMXRefresh, HttpResponseClientRedirect as HTMXRedirect
from collections import defaultdict
from .models import *
from .forms import *

# --- User Authentication ---
def user_registration(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            refresh = RefreshToken.for_user(user)
            response = redirect("/")
            response.set_cookie("refresh_token", str(refresh), httponly=True)
            response.set_cookie("access_token", str(refresh.access_token), httponly=True)
            return response
    else:
        form = UserRegistrationForm()
    return render(request, "register.html", {"registration_form": form})

def user_login(request):
    if request.method == "POST":
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                refresh = RefreshToken.for_user(user)
                response = redirect("/")
                response.set_cookie("refresh_token", str(refresh), httponly=True)
                response.set_cookie("access_token", str(refresh.access_token), httponly=True)
                return response
    else:
        form = UserLoginForm()
    return render(request, "login.html", {"login_form": form})

# --- Home Page ---
class HomePageView(ListView):
    model = Course
    context_object_name = "courses"
    template_name = "index.html"

    def get_queryset(self):
        user = self.request.user
        blocked_by = []
        if user.is_authenticated:
            blocked_by = user.get_blocked_by()
        queryset = Course.objects.prefetch_related(
            "modules", "modules__lessons", "modules__assignments",
            "enrollments__student", "status_updates"
        ).exclude(
            taught_by__in=blocked_by
        ).select_related("taught_by")

        user = self.request.user
        if user.is_authenticated:
            if user.role == User.UserRole.STUDENT:
                queryset = queryset.filter(enrollments__student=user)
            elif user.role == User.UserRole.TEACHER:
                queryset = queryset.filter(taught_by=user)
        else:
            queryset = queryset.filter(is_published=True)

        queryset = queryset.annotate(
            students_enrolled_count=Count(
                "enrollments__student", 
                filter=Q(enrollments__status=Enrollment.EnrollmentStatus.ACTIVE),
                distinct=True
            ),
            average_rating=Coalesce(Avg("course_reviews__rating"), 0.0),
            review_count=Count("course_reviews", distinct=True)
        )
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        courses = context["courses"]

        if user.is_authenticated:
            blocked_users = user.get_blocked_users()
            context["chats"] = Chat.objects.filter(
                participants__user=user, is_active=True
            ).exclude(
                participants__user__in=blocked_users
            ).annotate(
                last_message_time=Max("messages__sent_at")
            ).order_by("-last_message_time", "-created_at")[:3]
            context["more_chats"] = (
                Chat.objects.filter(participants__user=user, is_active=True).count() > 3
            )
            context["status_updates"] = StatusUpdate.objects.filter(
                course__in=courses
            ).exclude(
                student__in=blocked_users
            ).select_related("student", "course").order_by("-created_at")
            context["notifications"] = Notification.objects.filter(
                related_course__in=courses,
                user=user,
                read=False
            ).order_by("-created_at")
            if user.role == User.UserRole.STUDENT:
                for course in courses:
                    course.user_progress = round(course.get_user_progress(user), 1)
        else:
            teacher_group = Group.objects.get_or_create(name=User.UserRole.TEACHER)
            context["teachers"] = teacher_group.user_set.all()

        return context

# --- User Profile ---
class UserDetailView(DetailView):
    model = User
    context_object_name = "profile_user"
    template_name = "user_profile.html"

    def dispatch(self, request, *args, **kwargs):
        profile_user = get_object_or_404(User, pk=kwargs.get("pk"))
        blocked_users = profile_user.get_blocked_users()

        if request.user in blocked_users:
            return redirect("/")

        if profile_user.role == User.UserRole.TEACHER:
            return super().dispatch(request, *args, **kwargs)
        if profile_user.role == User.UserRole.STUDENT and not request.user.is_authenticated:
            login_url = reverse("login")
            return redirect(f"{login_url}?next={request.path}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile_user = context["profile_user"]

        if profile_user.role == User.UserRole.TEACHER:
            context["courses"] = Course.objects.filter(
                taught_by=profile_user
            ).annotate(
                students_enrolled_count=Count(
                    "enrollments__student", 
                    filter=Q(enrollments__status=Enrollment.EnrollmentStatus.ACTIVE),
                    distinct=True
                ),
                average_rating=Coalesce(Avg("course_reviews__rating"), 0.0),
                review_count=Count("course_reviews", distinct=True)
            )
        elif profile_user.role == User.UserRole.STUDENT:
            context["profile_user"].is_blocked = UserBlock.objects.filter(
                blocked_user=profile_user,
                blocked_by=self.request.user
            ).exists()
            context["status_updates"] = StatusUpdate.objects.filter(
                student=profile_user
            ).select_related("course").order_by("-created_at")
            context["courses"] = Course.objects.filter(
                enrollments__student=profile_user
            )
            for course in context["courses"]:
                course.user_progress = round(course.get_user_progress(profile_user), 1)

        if profile_user != self.request.user:
            context["courses"] = context["courses"].filter(is_published=True)
        return context
    
class UserListView(ListView):
    model = User
    context_object_name = "users"
    template_name = "users.html"

    def get_queryset(self):
        query = self.request.GET.get("query")
        queryset = User.objects.exclude(is_staff=True)
        if query:
            queryset = queryset.filter(
                title__icontains=query
            )

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        users = context["users"]
        current_user = self.request.user
        blocked_ids = set([user.pk for user in current_user.get_blocked_users()])
        for user in users:
            user.is_blocked = user.pk in blocked_ids
        return context

def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        if request.user != user:
            raise PermissionDenied("Users can only modify their own profiles")
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = UserProfileForm(instance=user)
    return render(request, "components/forms/user_form.html", {"user_form": form, "user": user})

# --- Status Updates ---
def status_update_create(request):
    course_id = request.GET.get("course")
    initial = {}
    if course_id:
        initial["course"] = course_id

    if request.method == "POST":
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            status_update = form.save(commit=False)
            status_update.student = request.user
            status_update.course_progress = status_update.course.get_user_progress(request.user)
            status_update.save()
            return HTMXRefresh()
    else:
        form = StatusUpdateForm(initial=initial)

    return render(request, "components/forms/status_update_form.html", {"status_update_form": form, "mode": "create"})

def status_update_edit(request, pk):
    status_update = get_object_or_404(StatusUpdate, pk=pk)
    if request.method == "POST":
        if request.user != status_update.student:
            raise PermissionDenied("Only the poster can modify this status update")
        form = StatusUpdateForm(request.POST, instance=status_update)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = StatusUpdateForm(instance=status_update)
    return render(request, "components/forms/status_update_form.html", {"status_update_form": form, "mode": "edit", "status_update": status_update})

def status_update_delete(request, pk):
    status_update = get_object_or_404(StatusUpdate, pk=pk)
    if request.method == "POST":
        if request.user != status_update.student:
            raise PermissionDenied("Only the poster can delete this status update")
        status_update.delete()
        return HTMXRefresh()
    return render(request, "components/forms/status_update_delete.html", {"status_update": status_update})

# --- Courses ---
class CourseListView(ListView):
    model = Course
    context_object_name = "courses"
    template_name = "courses.html"

    def get_queryset(self):
        query = self.request.GET.get("query")
        today = timezone.now().date()
        user = self.request.user
        blocked_by = None
        if user.is_authenticated:
            blocked_by = user.get_blocked_by()
        
        queryset = Course.objects.prefetch_related(
            "modules", "modules__lessons", "modules__assignments",
            "enrollments__student", "status_updates"
        ).filter(
            is_published=True,
            end_date__gte=today
        ).select_related("taught_by")

        if blocked_by:
            queryset = queryset.exclude(
                taught_by__in=blocked_by
            )
        if query:
            queryset = queryset.filter(
                title__icontains=query
            )

        queryset = queryset.annotate(
            students_enrolled_count=Count(
                "enrollments__student", 
                filter=Q(enrollments__status=Enrollment.EnrollmentStatus.ACTIVE),
                distinct=True
            ),
            average_rating=Coalesce(Avg("course_reviews__rating"), 0.0),
            review_count=Count("course_reviews", distinct=True)
        ).distinct()

        return queryset

class CourseDetailView(DetailView):
    model = Course
    context_object_name = "course"
    template_name = "course.html"

    def dispatch(self, request, *args, **kwargs):
        course = get_object_or_404(Course, pk=kwargs.get("pk"))
        blocked_users = course.taught_by.get_blocked_users()

        if request.user in blocked_users:
            return redirect("/")
        
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Course.objects.prefetch_related(
            "modules", "modules__lessons", "modules__assignments",
            "enrollments", "enrollments__student", "status_updates", "course_reviews"
        ).select_related("taught_by")
        queryset = queryset.annotate(
            students_enrolled_count=Count(
                "enrollments__student", 
                filter=Q(enrollments__status=Enrollment.EnrollmentStatus.ACTIVE),
                distinct=True
            ),
            average_rating=Coalesce(Avg("course_reviews__rating"), 0.0),
            review_count=Count("course_reviews", distinct=True)
        )
        return queryset.distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = context["course"]
        user = self.request.user
        if user.is_authenticated:
            if user.role == User.UserRole.STUDENT:
                course.user_progress = round(course.get_user_progress(user), 1)
                context["user_enrollment"] = user.get_enrollment(course)
                context["completed_lessons"] = list(user.get_lessons_completed(course).values_list("pk", flat=True))
                context["submitted_assignments"] = {s.assignment.pk: s for s in user.get_assignments_submitted(course)}
                context["user_reviewed"] = course.course_reviews.filter(student=user).exists()
                context["status_updates"] = StatusUpdate.objects.filter(
                    course=course
                ).select_related("student").order_by("-created_at")
            elif user.role == User.UserRole.TEACHER:
                blocked_users = user.get_blocked_users()
                context["assignment_submissions"] = AssignmentSubmission.objects.filter(
                    assignment__module__course=course,
                ).exclude(
                    student__in=blocked_users
                ).select_related("assignment", "student").order_by("submitted_on")
                enrollments = course.enrollments.all()
                status_groups = defaultdict(list)
                for enrollment in enrollments:
                    student = enrollment.student
                    student.enrollment = enrollment
                    student.course_progress = round(course.get_user_progress(student), 1)
                    status_groups[enrollment.status].append(student)
                context["enrolled_students"] = [
                    ("Active", status_groups.get(Enrollment.EnrollmentStatus.ACTIVE, [])),
                    ("Completed", status_groups.get(Enrollment.EnrollmentStatus.COMPLETED, [])),
                    ("Canceled", status_groups.get(Enrollment.EnrollmentStatus.CANCELED, [])),
                    ("Removed", status_groups.get(Enrollment.EnrollmentStatus.REMOVED, [])),
                ]
                context["status_updates"] = StatusUpdate.objects.filter(
                    course=course
                ).exclude(
                    student__in=blocked_users
                ).select_related("student").order_by("-created_at")
            context["notifications"] = Notification.objects.filter(related_course=course, user=user, read=False).order_by("-created_at")

        return context
    
class LessonDetailView(DetailView):
    model = Lesson
    content_object_name = "lesson"
    template_name = "course_element.html"

    def dispatch(self, request, *args, **kwargs):
        lesson = get_object_or_404(Lesson, pk=kwargs.get("pk"))
        user = request.user
        course = Course.objects.get (pk=lesson.module.course.pk)
        blocked_users = course.taught_by.get_blocked_users()

        if not user.is_authenticated:
            login_url = reverse("login")
            return redirect(f"{login_url}?next={request.path}")
        
        if user in blocked_users:
            return redirect("/")
        
        if (user.role == User.UserRole.STUDENT and user.get_enrollment(course) is None) or (user.role == User.UserRole.TEACHER and user != course.taught_by):
            if not user.get_enrollment(course):
                # No access if student is not enrolled or teacher is not course creator
                return redirect("course", pk=course.pk)
            
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        lesson = context["lesson"]
        course = Course.objects.prefetch_related(
            "modules", "modules__lessons", "modules__assignments"
        ).get(pk=lesson.module.course.pk)
        context["course"] = course
        if user.role == User.UserRole.STUDENT:
            context["completed_lessons"] = list(user.get_lessons_completed(course).values_list("pk", flat=True))
            context["submitted_assignments"] = {s.assignment.pk: s for s in user.get_assignments_submitted(course)}

        return context

class AssignmentDetailView(DetailView):
    model = Assignment
    content_object_name = "assignment"
    template_name = "course_element.html"

    def dispatch(self, request, *args, **kwargs):
        assignment = get_object_or_404(Assignment, pk=kwargs.get("pk"))
        blocked_users = assignment.module.course.taught_by.get_blocked_users()

        if request.user in blocked_users:
            return redirect("/")

        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = Assignment.objects.prefetch_related(
            "assignment_submissions"
        )
        return queryset.distinct()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        assignment = context["assignment"]
        course = assignment.module.course
        context["course"] = course
        if user.role == User.UserRole.STUDENT:
            context["completed_lessons"] = list(user.get_lessons_completed(course).values_list("pk", flat=True))
            submitted_assignments = {s.assignment.pk: s for s in user.get_assignments_submitted(course)}
            context["submitted_assignments"] = submitted_assignments
            if assignment.pk in submitted_assignments:
                context["submission"] = AssignmentSubmission.objects.get(student=user, assignment=assignment)

        return context

    
def course_create(request):
    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(commit=False)
            course.taught_by = request.user
            course.save()
            return HTMXRedirect(f"courses/{course.pk}")
    else:
        form = CourseForm()
    return render(request, "components/forms/course_form.html", {"course_form": form})

def course_edit(request, pk):
    course = get_object_or_404(Course, pk=pk, taught_by=request.user)
    if request.method == "POST":
        form = CourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = CourseForm(instance=course)
    return render(request, "components/forms/course_form.html", {"course_form": form, "course": course})

def course_review(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == "POST":
        form = CourseReviewForm(request.POST)
        form.instance.course = course
        form.instance.student = request.user
        if form.is_valid():
            review = form.save(commit=False)
            review.save()
            return HTMXRefresh()
    else:
        form = CourseReviewForm()
    return render(request, "components/forms/course_review_form.html", {"course_review_form": form, "course": course})

def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.POST:
        if course.taught_by != request.user:
            raise PermissionDenied("Only the course's teacher can delete it")
        course.delete()
        return HTMXRefresh()
    
    return render(request, "components/forms/course_delete.html", {"course": course})

def module_create(request, course_pk):
    course = get_object_or_404(Course, pk=course_pk, taught_by=request.user)
    if course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can add modules to this course")
    if request.method == "POST":
        form = ModuleForm(request.POST)
        form.instance.course = course
        if form.is_valid():
            module = form.save(commit=False)
            module.save()
            return HTMXRefresh()
    else:
        form = ModuleForm()
    return render(request, "components/forms/module_form.html", {"module_form": form, "mode": "create", "course": course})

def module_edit(request, pk):
    module = get_object_or_404(Module, pk=pk, course__taught_by=request.user)
    if module.course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can edit its modules")
    if request.method == "POST":
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = ModuleForm(instance=module)
    return render(request, "components/forms/module_form.html", {"module_form": form, "mode": "edit", "module": module})

def module_delete(request, pk):
    module = get_object_or_404(Module, pk=pk)
    if request.POST:
        if module.course.taught_by != request.user:
            raise PermissionDenied("Only the course's teacher can delete a module")
        module.delete()
        return HTMXRefresh()
    
    return render(request, "components/forms/module_delete.html", {"module": module})

def lesson_create(request, module_pk):
    module = get_object_or_404(Module, pk=module_pk)
    course = module.course
    if course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can add lessons to this course")
    if request.method == "POST":
        form = LessonForm(request.POST, request.FILES)
        form.instance.module = module
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.save()
            return HTMXRefresh()
    else:
        form = LessonForm()
    return render(request, "components/forms/lesson_form.html", {"lesson_form": form, "mode": "create", "module": module})

def lesson_edit(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    if lesson.module.course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can edit its lessons")
    if request.method == "POST":
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = LessonForm(instance=lesson)
    return render(request, "components/forms/lesson_form.html", {"lesson_form": form, "mode": "edit", "lesson": lesson})

def lesson_delete(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    if request.POST:
        if lesson.module.course.taught_by != request.user:
            raise PermissionDenied("Only the course's teacher can delete this lesson")
        lesson.delete()
        return HTMXRefresh()
    
    return render(request, "components/forms/lesson_delete.html", {"lesson": lesson})

def assignment_create(request, module_pk):
    module = get_object_or_404(Module, pk=module_pk, course__taught_by=request.user)
    course = module.course
    if course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can add assignments to this course")
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        form.instance.module = module
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.save()
            return HTMXRefresh()
    else:
        form = AssignmentForm()
    return render(request, "components/forms/assignment_form.html", {"assignment_form": form, "mode": "create", "module": module})

def assignment_edit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk, module__course__taught_by=request.user)
    if assignment.module.course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can edit its assignments")
    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment)
        if form.is_valid():
            form.save()
            return HTMXRefresh()
    else:
        form = AssignmentForm(instance=assignment)
    return render(request, "components/forms/assignment_form.html", {"assignment_form": form, "mode": "edit", "assignment": assignment})

def assignment_delete(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    if request.POST:
        if assignment.module.course.taught_by != request.user:
            raise PermissionDenied("Only the course's teacher can delete this assignment")
        assignment.delete()
        return HTMXRefresh()
    
    return render(request, "components/forms/assignment_delete.html", {"assignment": assignment})

def assignment_submit(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    user = request.user
    if request.method == "POST":
        enrollment = user.get_enrollment(assignment.module.course)
        if not enrollment:
            raise PermissionDenied("User cannot submit assignment for course they're not enrolled in")
        form = AssignmentSubmissionForm(request.POST, request.FILES)
        form.instance.assignment = assignment
        form.instance.student = user
        if form.is_valid():
            submission = form.save(commit=False)
            submission.save()
            return HTMXRefresh()
    else:
        form = AssignmentSubmissionForm()
    return render(request, "components/forms/submit_assignment_form.html", {"submission_form": form, "mode": "create", "assignment": assignment})

def assignment_submit_edit(request, pk):
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    user = request.user
    if request.method == "POST":
        if user != submission.student:
            raise PermissionDenied("Cannot edit someone else's assignment submission")
        form = AssignmentSubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.save()
            return HTMXRefresh()
    else:
        form = AssignmentSubmissionForm(instance=submission)
    return render(request, "components/forms/submit_assignment_form.html", {"submission_form": form, "mode": "edit", "submission": submission})

def assignment_grade(request, pk):
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    if submission.assignment.module.course.taught_by != request.user:
        raise PermissionDenied("Only the course's teacher can grade assignments")
    if request.method == "POST":
        form = AssignmentGradingForm(request.POST, instance=submission)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.save()
            return HTMXRefresh()
    else:
        form = AssignmentGradingForm(instance=submission)
    return render(request, "components/forms/grade_assignment_form.html", {"grading_form": form, "submission": submission})

# --- Chats ---
class ChatRoomView(DetailView):
    model = Chat
    context_object_name = "chat"
    template_name = "chat_room.html"

    def dispatch(self, request, *args, **kwargs):
        chat = get_object_or_404(Chat, pk=kwargs.get("pk"))
        participants = chat.participants.all()
        if request.user not in [p.user for p in participants]:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        blocked_users = self.request.user.get_blocked_users()
        context["messages"] = ChatMessage.objects.filter(chat=context["chat"])
        context["chats"] = Chat.objects.filter(
            participants__user=self.request.user, is_active=True
        ).exclude(
            participants__user__in=blocked_users
        )
        return context


