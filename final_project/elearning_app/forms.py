from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from .models import *
from .tasks import *

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(label="Password", widget=forms.PasswordInput, strip=False)
    password_confirmation = forms.CharField(label="Confirm Password", widget=forms.PasswordInput, strip=False)
    role = forms.ChoiceField(label="Role", widget=forms.Select, choices=[choice for choice in User.UserRole.choices if choice[0] != 'Admin'])

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "role", "password", "password_confirmation", "profile_picture", "bio")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")

        # Passwords match
        if password and password_confirmation and password != password_confirmation:
            raise forms.ValidationError({
                "password_confirmation": ["Passwords do not match."]
            })

        # Password is strong enough
        if password and (len(password) < 8 or password.isdigit() or password.isalpha()):
            raise forms.ValidationError({
                "password": ["Password is too simple. It must be at least 8 characters and contain letters and numbers."]
            })
        
        return cleaned_data
    
    def save(self, commit = True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        profile_picture = self.cleaned_data.get("profile_picture")
        if commit:
            user.save()
            user.set_role(self.cleaned_data["role"])
            if profile_picture:
                resize_profile_picture.delay(user.pk)
        return user

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email")

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "profile_picture", "bio")
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4}),
        }

    def save(self, commit = True):
        user = super().save(commit=False)
        profile_picture = self.cleaned_data.get("profile_picture")
        if commit:
            user.save()
            if profile_picture:
                resize_profile_picture.delay(user.pk)
        return user

class CourseReviewForm(forms.ModelForm):
    class Meta:
        model = CourseReview
        fields = ("rating", "review")
        widgets = {
            "review": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_rating(self):
        rating = self.cleaned_data["rating"]
        if rating < 0 or rating > 5:
            raise ValidationError("Rating must be a number between 0 and 5")
        return rating
    
    def clean(self):
        cleaned_data = super().clean()
        student = self.instance.student
        course = self.instance.course

        if not student or student.role != User.UserRole.STUDENT:
            raise ValidationError("Only students can leave course reviews.")

        enrollment = Enrollment.objects.filter(student=student, course=course, status=Enrollment.EnrollmentStatus.COMPLETED).first()
        if not enrollment:
            raise ValidationError("Student has not completed the course before leaving a review.")

        already_reviewed = CourseReview.objects.filter(student=student, course=course).exists()
        if already_reviewed and not self.instance.pk:
            raise ValidationError("Student has already left a review for this course.")

        return cleaned_data

class StatusUpdateForm(forms.ModelForm):
    class Meta:
        model = StatusUpdate
        fields = ("course", "text", )
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }

class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("file_submission",)

class AssignmentGradingForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("grade", "feedback")
        widgets = {
            "feedback": forms.Textarea(attrs={"rows": 3}),
        }

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "description", "cover_image", "start_date", "end_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and end < start:
            raise ValidationError("End date cannot be before start date.")
        return cleaned_data

class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ["title", "description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "description", "lesson_file"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        description = cleaned_data.get("description")
        lesson_file = cleaned_data.get("lesson_file")

        if not (description or lesson_file):
            raise ValidationError("Lesson must have one of description or file")
    
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["title", "description", "deadline", "weight"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean_weight(self):
        weight = self.cleaned_data["weight"]
        if weight < 0 or weight > 100:
            raise ValidationError("Weight must be between 0 and 100.")
        return weight
