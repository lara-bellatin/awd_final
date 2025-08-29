from django.urls import path, re_path
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from . import views
from . import api

urlpatterns = [
    # VIEWS
	path("", views.HomePageView.as_view(), name="index"),

    # Users and status updates
    path("register/", views.user_registration, name="register"),
    path("login/", views.user_login, name="login"),
    path("users/", views.UserListView.as_view(), name="users"),
    path("users/<int:pk>", views.UserDetailView.as_view(), name="user"),
    path("users/status_updates/new", views.status_update_create, name="status-update-create"),
    path("users/status_updates/<int:pk>/edit", views.status_update_edit, name="status-update-edit"),
    path("users/status_updates/<int:pk>/delete", views.status_update_delete, name="status-update-delete"),
    path("users/<int:pk>/edit", views.user_edit, name="user-edit"),

    # Courses
    path("courses/", login_required(login_url="/login")(views.CourseListView.as_view()), name="courses"),
    path("courses/<int:pk>", views.CourseDetailView.as_view(), name="course"),
    path("courses/new/", login_required(login_url="/login")(views.course_create), name="course-create"),
    path("courses/<int:pk>/edit/", login_required(login_url="/login")(views.course_edit), name="course-edit"),
    path("courses/<int:pk>/review", login_required(login_url="/login")(views.course_review), name="course-review"),
    path("courses/<int:pk>/delete/", login_required(login_url="/login")(views.course_delete), name="course-delete"),
    
    # Modules
    path("courses/<int:course_pk>/modules/add/", login_required(login_url="/login")(views.module_create), name="module-create"),
    path("modules/<int:pk>/edit/", login_required(login_url="/login")(views.module_edit), name="module-edit"),
    path("modules/<int:pk>/delete/", login_required(login_url="/login")(views.module_delete), name="module-delete"),

    # Lessons
    path("modules/<int:module_pk>/lessons/add/", login_required(login_url="/login")(views.lesson_create), name="lesson-create"),
    path("lessons/<int:pk>/edit/", login_required(login_url="/login")(views.lesson_edit), name="lesson-edit"),
    path("lessons/<int:pk>/delete/", login_required(login_url="/login")(views.lesson_delete), name="lesson-delete"),
    path("lessons/<int:pk>", login_required(login_url="/login")(views.LessonDetailView.as_view()), name="lesson-detail"),

    # Assignments
    path("modules/<int:module_pk>/assignments/add/", login_required(login_url="/login")(views.assignment_create), name="assignment-create"),
    path("assignments/<int:pk>/edit/", login_required(login_url="/login")(views.assignment_edit), name="assignment-edit"),
    path("assignments/<int:pk>/delete/", login_required(login_url="/login")(views.assignment_delete), name="assignment-delete"),
    path("assignments/<int:pk>", login_required(login_url="/login")(views.AssignmentDetailView.as_view()), name="assignment-detail"),
    path("assignments/<int:pk>/submit/", login_required(login_url="/login")(views.assignment_submit), name="assignment-submit"),
    path("assignments/submissions/<int:pk>/edit/", login_required(login_url="/login")(views.assignment_submit_edit), name="assignment-submit-edit"),
    path("assignments/submissions/<int:pk>/grade/", login_required(login_url="/login")(views.assignment_grade), name="assignment-grade"),

    # Chats
    path("chats/<int:pk>", login_required(login_url="/login")(views.ChatRoomView.as_view()), name="chat"),

    # API
    # Tokens
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Users, auth, status updates and notifications
    path("api/login/", api.UserLoginView.as_view(), name="api_login"),
    path("api/logout/", api.UserLogoutView.as_view(), name="api_logout"),
    path("api/users/<int:pk>/", api.UserDetailView.as_view(), name="api_user"),
    path("api/users/", api.UserListView.as_view(), name="api_users"),
    re_path(r"^api/users(?:/(?P<pk>\d+))?/status_updates/$", api.StatusUpdateListCreateView.as_view(), name="api_status_updates"),
    path("api/users/status_updates/<int:pk>/", api.StatusUpdateDetailView.as_view(), name="api_status_update"),
    path("api/notifications/<int:pk>/dismiss/", api.NotificationReadView.as_view(), name="api_notification_read"),
    path("api/users/block/", api.UserBlockView.as_view(), name="api_user_block"),

    # Courses, Enrollments and Reviews
    path("api/courses/", api.CourseListCreateView.as_view(), name="api_courses"),
    path("api/courses/<int:pk>/", api.CourseDetailView.as_view(), name="api_course"),
    path("api/courses/<int:pk>/enrollments/", api.EnrollmentListCreateView.as_view(), name="api_enrollments"),
    path("api/courses/enrollments/<int:pk>/", api.EnrollmentDetailView.as_view(), name="api_enrollment"),
    path("api/courses/<int:pk>/reviews/", api.CourseReviewListCreateView.as_view(), name="api_course_reviews"),
    path("api/courses/reviews/<int:pk>/", api.CourseReviewDetailView.as_view(), name="api_course_review"),

    # Modules
    path("api/courses/<int:pk>/modules/", api.ModuleListCreateView.as_view(), name="api_modules"),
    path("api/modules/<int:pk>/", api.ModuleDetailView.as_view(), name="api_module"),

    # Lessons
    path("api/modules/<int:pk>/lessons/", api.LessonListCreateView.as_view(), name="api_lessons"),
    path("api/lessons/<int:pk>/", api.LessonDetailView.as_view(), name="api_lesson"),
    path("api/lessons/<int:pk>/progress/", api.LessonProgressDetailView.as_view(), name="api_lesson_progress"),

    # Assignments
    path("api/modules/<int:pk>/assignments/", api.AssignmentListCreateView.as_view(), name="api_assignments"),
    path("api/assignments/<int:pk>/", api.AssignmentDetailView.as_view(), name="api_assignment"),
    path("api/assignments/<int:pk>/submissions/", api.AssignmentSubmissionListCreateView.as_view(), name="api_submissions"),
    path("api/assignments/submissions/<int:pk>/", api.AssignmentSubmissionDetailView.as_view(), name="api_submission"),
    path("api/assignments/submissions/<int:pk>/grade/", api.AssignmentSubmissionGradeView.as_view(), name="api_submission_grade"),

    # Chats
    path("api/chats/", api.ChatListCreateView.as_view(), name="api_chats"),
    path("api/chats/<int:pk>/", api.ChatDetailView.as_view(), name="api_chat"),
    path("api/chats/<int:pk>/messages/", api.ChatMessageListCreateView.as_view(), name="api_chat_messages"),
    path("api/chats/messages/<int:pk>/", api.ChatMessageDetailView.as_view(), name="api_chat_message"),
    path("api/chats/<int:pk>/participants/", api.ChatParticipantListCreateView.as_view(), name="api_chat_participants"),
    path("api/chats/participants/<int:pk>/", api.ChatParticipantDetailView.as_view(), name="api_chat_participant"),
]