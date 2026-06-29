from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import (
    AcademicYear, Assignment, AssignmentSubmission,
    SchoolClass, ClassSubjectTeacher, GRADE_CHOICES, GradeSubjectConfig, GradingScale,
    Parent, ParentStudent, Student, Subject, Teacher, Term, User,
    YearEndPromotion,
)


# ─────────────────────────────────────────────
# USER / AUTH FORMS
# ─────────────────────────────────────────────

class UserProfileForm(forms.ModelForm):
    """
    Editable profile fields that actually exist on the custom User model.
    NOTE: profile_picture does NOT exist on User — removed.
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'phone':      forms.TextInput(attrs={'class': 'form-control'}),
        }


class UserAdminForm(forms.ModelForm):
    """Admin form to edit core user details and optionally reset password."""
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Leave blank to keep current password',
        }),
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'phone':      forms.TextInput(attrs={'class': 'form-control'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get('password'):
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class RoleChangeForm(forms.ModelForm):
    """Change a user's role."""
    class Meta:
        model = User
        fields = ['role']
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
        }


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


# ─────────────────────────────────────────────
# ACADEMIC YEAR & TERM
# ─────────────────────────────────────────────

class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2025'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date':   forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TermForm(forms.ModelForm):
    """
    NOTE: is_finalized was removed — it does not exist on the Term model.
    Fields present: name, academic_year, start_date, end_date, is_active,
    new_term_prompt_dismissed.
    """
    class Meta:
        model = Term
        fields = [
            'name', 'academic_year',
            'start_date', 'end_date',
            'is_active', 'new_term_prompt_dismissed',
        ]
        widgets = {
            'name':                      forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Term 1'}),
            'academic_year':             forms.Select(attrs={'class': 'form-select'}),
            'start_date':                forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date':                  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active':                 forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'new_term_prompt_dismissed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ─────────────────────────────────────────────
# SUBJECT
# ─────────────────────────────────────────────

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control'}),
            'code':        forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ─────────────────────────────────────────────
# GRADE-LEVEL SUBJECT CONFIGURATION
# ─────────────────────────────────────────────

class GradeSubjectConfigForm(forms.ModelForm):
    """
    Configures which subjects belong to which grade level,
    and whether they are compulsory or elective.
    """
    class Meta:
        model = GradeSubjectConfig
        fields = ['grade_level', 'subject', 'is_compulsory', 'is_elective']
        widgets = {
            'grade_level':   forms.Select(attrs={'class': 'form-select'}),
            'subject':       forms.Select(attrs={'class': 'form-select'}),
            'is_compulsory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_elective':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['subject'].disabled = True


# ─────────────────────────────────────────────
# CLASS
# ─────────────────────────────────────────────

class ClassForm(forms.ModelForm):
    """
    FIX: grade_level choices now match the model (G1–G7, F1–F6),
    not the old incorrect numeric choices (1–6).
    """
    class Meta:
        model = SchoolClass
        fields = ['name', 'grade_level', 'academic_year', 'class_teacher', 'room_number', 'capacity']
        widgets = {
            'name':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Form 1A'}),
            'grade_level':   forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'class_teacher': forms.Select(attrs={'class': 'form-select'}),
            'room_number':   forms.TextInput(attrs={'class': 'form-control'}),
            'capacity':      forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only active teachers in the dropdown
        self.fields['class_teacher'].queryset = Teacher.objects.filter(is_active=True)
        self.fields['class_teacher'].required = False


# ─────────────────────────────────────────────
# STUDENT
# ─────────────────────────────────────────────

class StudentForm(forms.Form):
    """
    Composite form: creates/updates both a User record and its linked
    Student profile in a single form submission.
    """
    # ── User fields ──────────────────────────
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name  = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email      = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))

    # ── Student fields ───────────────────────
    date_of_birth = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    gender = forms.ChoiceField(
        choices=[('M', 'Male'), ('F', 'Female')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    current_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    # ── Emergency contact ────────────────────
    emergency_contact_name         = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    emergency_contact_phone        = forms.CharField(max_length=20,  widget=forms.TextInput(attrs={'class': 'form-control'}))
    emergency_contact_relationship = forms.CharField(max_length=50,  widget=forms.TextInput(attrs={'class': 'form-control'}))

    # ── Medical ──────────────────────────────
    blood_group   = forms.CharField(max_length=5, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    allergies     = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))
    medical_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))

    is_active = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}))

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)

        if self.instance:
            u = self.instance.user
            self.initial.update({
                'first_name':                      u.first_name,
                'last_name':                       u.last_name,
                'email':                           u.email,
                'date_of_birth':                   self.instance.date_of_birth,
                'gender':                          self.instance.gender,
                'current_class':                   self.instance.current_class,
                'emergency_contact_name':          self.instance.emergency_contact_name,
                'emergency_contact_phone':         self.instance.emergency_contact_phone,
                'emergency_contact_relationship':  self.instance.emergency_contact_relationship,
                'blood_group':                     self.instance.blood_group,
                'allergies':                       self.instance.allergies,
                'medical_notes':                   self.instance.medical_notes,
                'is_active':                       self.instance.is_active,
            })

    def clean_email(self):
        email = self.cleaned_data['email']
        qs = User.objects.filter(email=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.user.pk)
        if qs.exists():
            raise forms.ValidationError('A user with this email already exists.')
        return email


class StudentProfileForm(forms.ModelForm):
    """Self-service profile editing for students (non-academic fields only)."""
    class Meta:
        model = Student
        fields = ['emergency_contact_name', 'emergency_contact_phone', 'medical_notes', 'allergies', 'blood_group']
        widgets = {
            'emergency_contact_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'medical_notes':           forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'allergies':               forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'blood_group':             forms.TextInput(attrs={'class': 'form-control'}),
        }


# ─────────────────────────────────────────────
# TEACHER
# ─────────────────────────────────────────────

class TeacherForm(forms.ModelForm):
    """
    Composite form: creates/updates User + Teacher profile together.
    Extra user fields are declared explicitly.
    """
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name  = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email      = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone      = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Teacher
        fields = ['date_of_birth', 'qualification', 'specialization', 'date_joined', 'is_active']
        widgets = {
            'date_of_birth':  forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'qualification':  forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
            'date_joined':    forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active':      forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class TeacherProfileForm(forms.ModelForm):
    """Self-service profile editing for teachers."""
    class Meta:
        model = Teacher
        fields = ['qualification', 'specialization']
        widgets = {
            'qualification':  forms.TextInput(attrs={'class': 'form-control'}),
            'specialization': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TeacherAssignmentForm(forms.ModelForm):
    """Assign a teacher to teach a subject in a class for a given academic year."""
    class Meta:
        model = ClassSubjectTeacher
        fields = ['class_assigned', 'subject', 'teacher', 'academic_year']
        widgets = {
            'class_assigned': forms.Select(attrs={'class': 'form-select'}),
            'subject':        forms.Select(attrs={'class': 'form-select'}),
            'teacher':        forms.Select(attrs={'class': 'form-select'}),
            'academic_year':  forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = Teacher.objects.filter(is_active=True)

    def clean_subject(self):
        """Validate that the subject is configured for the selected class's grade level."""
        class_assigned = self.cleaned_data.get('class_assigned')
        subject = self.cleaned_data.get('subject')
        if class_assigned and subject:
            from smsapp.models import GradeSubjectConfig
            is_configured = GradeSubjectConfig.objects.filter(
                grade_level=class_assigned.grade_level,
                subject=subject
            ).exists()
            if not is_configured:
                raise forms.ValidationError(
                    f'"{subject}" is not configured for {class_assigned.grade_level}. '
                    f'Add it in Grade-Subject Config first.'
                )
        return subject


# ─────────────────────────────────────────────
# PARENT
# ─────────────────────────────────────────────

class ParentForm(forms.ModelForm):
    """Composite form: creates/updates User + Parent profile together."""
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name  = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email      = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    phone      = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = Parent
        fields = ['occupation', 'address']
        widgets = {
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'address':    forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ParentProfileForm(forms.ModelForm):
    """Self-service profile editing for parents."""
    class Meta:
        model = Parent
        fields = ['occupation', 'address']
        widgets = {
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'address':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ParentStudentLinkForm(forms.ModelForm):
    """Link a parent to a child with a relationship type."""
    class Meta:
        model = ParentStudent
        fields = ['student', 'relationship', 'is_primary_contact']
        widgets = {
            'student':            forms.Select(attrs={'class': 'form-select'}),
            'relationship':       forms.Select(attrs={'class': 'form-select'}),
            'is_primary_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = (
            Student.objects.filter(is_active=True).select_related('user')
        )
        self.fields['student'].label_from_instance = (
            lambda obj: f"{obj.user.get_full_name()} ({obj.student_id_number})"
        )


# ─────────────────────────────────────────────
# ASSESSMENTS & GRADES
# ─────────────────────────────────────────────

class AssessmentCreationForm(forms.Form):
    """Composite form for creating/updating an Assessment (grade-management)."""
    name              = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    term              = forms.ModelChoiceField(queryset=Term.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    class_assigned    = forms.ModelChoiceField(queryset=SchoolClass.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    subject           = forms.ModelChoiceField(queryset=Subject.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    max_score         = forms.DecimalField(max_digits=5, decimal_places=2, min_value=1, initial=100, widget=forms.NumberInput(attrs={'class': 'form-control'}))
    assessment_date   = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    description       = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}))

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        if self.instance:
            self.initial.update({
                'name':              self.instance.name,
                'term':              self.instance.term,
                'class_assigned':    self.instance.class_assigned,
                'subject':           self.instance.subject,
                'max_score':         self.instance.max_score,
                'assessment_date':   self.instance.assessment_date,
                'description':       self.instance.description,
            })


class GradingScaleForm(forms.ModelForm):
    class Meta:
        model = GradingScale
        fields = ['grade', 'min_score', 'max_score', 'comment']
        widgets = {
            'grade':     forms.TextInput(attrs={'class': 'form-control'}),
            'min_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'comment':   forms.TextInput(attrs={'class': 'form-control'}),
        }


# ─────────────────────────────────────────────
# ASSIGNMENTS & SUBMISSIONS
# ─────────────────────────────────────────────

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'class_assigned', 'subject',
            'due_date', 'attachment', 'max_score', 'allow_late_submission',
        ]
        widgets = {
            'title':                forms.TextInput(attrs={'class': 'form-control'}),
            'description':          forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'class_assigned':       forms.Select(attrs={'class': 'form-select'}),
            'subject':              forms.Select(attrs={'class': 'form-select'}),
            'due_date':             forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'attachment':           forms.FileInput(attrs={'class': 'form-control'}),
            'max_score':            forms.NumberInput(attrs={'class': 'form-control'}),
            'allow_late_submission': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StudentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['submission_file', 'submission_text']
        widgets = {
            'submission_file': forms.FileInput(attrs={'class': 'form-control'}),
            'submission_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional comments…'}),
        }


class GradingForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['score', 'teacher_feedback', 'status']
        widgets = {
            'score':            forms.NumberInput(attrs={'class': 'form-control'}),
            'teacher_feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status':           forms.Select(attrs={'class': 'form-select'}),
        }


# ─────────────────────────────────────────────
# YEAR-END PROMOTION
# ─────────────────────────────────────────────

class YearEndPromotionForm(forms.ModelForm):
    """
    Used by the class teacher to set each student's end-of-year status
    and optionally pre-assign them to a class for the next academic year.
    """
    class Meta:
        model = YearEndPromotion
        fields = ['status', 'next_class', 'class_teacher_note']
        widgets = {
            'status':             forms.Select(attrs={'class': 'form-select'}),
            'next_class':         forms.Select(attrs={'class': 'form-select'}),
            'class_teacher_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['next_class'].required = False


class ClassSubjectTeacherForm(forms.ModelForm):
    class Meta:
        model = ClassSubjectTeacher
        fields = ['subject', 'teacher', 'academic_year']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter teachers to only active ones
        self.fields['teacher'].queryset = Teacher.objects.filter(is_active=True)
        # Order academic years by start date descending
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-start_date')
        # Add empty option for teacher (optional)
        self.fields['teacher'].empty_label = "Select Teacher (Optional)"


class GradeLevelTeacherAssignmentForm(forms.Form):
    """Bulk assign a teacher to ALL classes of a specific grade + subject."""
    grade_level = forms.ChoiceField(
        choices=GRADE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Grade Level'
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Subject'
    )
    teacher = forms.ModelChoiceField(
        queryset=Teacher.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Teacher',
        empty_label='Select Teacher'
    )
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all().order_by('-start_date'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Academic Year'
    )

    def clean(self):
        cleaned_data = super().clean()
        grade_level = cleaned_data.get('grade_level')
        subject = cleaned_data.get('subject')

        if grade_level and subject:
            # Validate that the subject is configured for this grade
            is_configured = GradeSubjectConfig.objects.filter(
                grade_level=grade_level,
                subject=subject
            ).exists()
            if not is_configured:
                raise forms.ValidationError(
                    f'"{subject}" is not configured for {grade_level}. '
                    f'Add it in Grade-Subject Config first.'
                )

        return cleaned_data