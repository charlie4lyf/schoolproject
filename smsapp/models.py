import random
import uuid
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


# ─────────────────────────────────────────────
# USER
# ─────────────────────────────────────────────

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin',   'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
        ('parent',  'Parent'),
    ]

    role  = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(unique=True, blank=True, null=True)

    REQUIRED_FIELDS = ['first_name', 'last_name', 'role']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def save(self, *args, **kwargs):
        if not self.pk and self.role != 'admin' and not self.username:
            self.username = User.generate_username(self.role)
        super().save(*args, **kwargs)

    @staticmethod  # FIX: was missing @staticmethod — calling self.generate_username() passed `self` as `role`
    def generate_username(role):
        role_suffix = {
            'student': 'S',
            'teacher': 'T',
            'parent':  'P',
            'admin':   'A',
        }
        year_short = str(timezone.now().year)[2:]
        digits     = f"{random.randint(0, 999999):06d}"
        suffix     = role_suffix.get(role, 'U')
        return f"C{year_short}{digits}{suffix}"


# ─────────────────────────────────────────────
# ACADEMIC YEAR & TERM
# ─────────────────────────────────────────────

class AcademicYear(models.Model):
    name       = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date   = models.DateField()
    is_active  = models.BooleanField(default=True)

    class Meta:
        db_table = 'academic_years'
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class Term(models.Model):
    academic_year             = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='terms')
    name                      = models.CharField(max_length=50)
    start_date                = models.DateField()
    end_date                  = models.DateField()
    is_active                 = models.BooleanField(default=False)
    new_term_prompt_dismissed = models.BooleanField(default=False)

    class Meta:
        db_table      = 'terms'
        ordering      = ['academic_year', 'start_date']
        unique_together = ['academic_year', 'name']

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    @property
    def has_ended(self):
        return timezone.now().date() > self.end_date


# ─────────────────────────────────────────────
# SHARED GRADE CHOICES
# FIX: was duplicated verbatim in GradeSubjectConfig and Class
# ─────────────────────────────────────────────

GRADE_CHOICES = [
    ('G1', 'Grade 1'), ('G2', 'Grade 2'), ('G3', 'Grade 3'),
    ('G4', 'Grade 4'), ('G5', 'Grade 5'), ('G6', 'Grade 6'),
    ('G7', 'Grade 7'),
    ('F1', 'Form 1'),  ('F2', 'Form 2'),  ('F3', 'Form 3'),
    ('F4', 'Form 4'),  ('F5', 'Form 5'),  ('F6', 'Form 6'),
]


# ─────────────────────────────────────────────
# SUBJECT
# ─────────────────────────────────────────────

class Subject(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    code        = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'subjects'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


# ─────────────────────────────────────────────
# GRADE-LEVEL SUBJECT CONFIGURATION
# ─────────────────────────────────────────────

class GradeSubjectConfig(models.Model):
    grade_level   = models.CharField(max_length=3, choices=GRADE_CHOICES)  # FIX: uses shared constant
    subject       = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grade_configs')
    is_compulsory = models.BooleanField(default=True)
    is_elective   = models.BooleanField(default=False)

    class Meta:
        db_table        = 'grade_subject_configs'
        unique_together = ['grade_level', 'subject']
        ordering        = ['grade_level', 'subject']

    def __str__(self):
        tag = "Elective" if self.is_elective else "Compulsory"
        return f"{self.grade_level} — {self.subject.name} [{tag}]"


# ─────────────────────────────────────────────
# CLASS
# ─────────────────────────────────────────────

class SchoolClass(models.Model):
    """
    A class instance for a specific academic year, e.g. Form 1A (2025).
    Renamed from Class (reserved word) to SchoolClass for clarity.
    """
    name          = models.CharField(max_length=50)
    grade_level   = models.CharField(max_length=3, choices=GRADE_CHOICES)  # FIX: uses shared constant
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='classes')
    class_teacher = models.ForeignKey(
        'Teacher', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='main_class'
    )
    room_number = models.CharField(max_length=20, blank=True, null=True)
    capacity    = models.IntegerField(default=40)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'classes'
        verbose_name    = 'Class'
        verbose_name_plural = 'Classes'
        ordering        = ['grade_level', 'name']
        unique_together = ['name', 'academic_year']

    def __str__(self):
        return f"{self.name} ({self.academic_year})"

    @property
    def student_count(self):
        # FIX: removed circular `from .models import StudentEnrollment` self-import
        return StudentEnrollment.objects.filter(class_assigned=self, is_active=True).count()

    @property
    def active_students(self):
        # FIX: removed circular self-import; also removed duplicate Student FK lookup —
        # query directly through the enrollment reverse relation
        return Student.objects.filter(
            enrollments__class_assigned=self,
            enrollments__is_active=True,
            is_active=True,
        )


# ─────────────────────────────────────────────
# STUDENT ENROLLMENT
# ─────────────────────────────────────────────

class StudentEnrollment(models.Model):
    student       = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='enrollments')
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='enrollments')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(default=timezone.now)
    is_active     = models.BooleanField(default=True)

    class Meta:
        db_table        = 'student_enrollments'
        unique_together = ['student', 'academic_year']
        ordering        = ['-academic_year', 'student']

    def __str__(self):
        return f"{self.student} → {self.class_assigned} ({self.academic_year})"


# ─────────────────────────────────────────────
# TEACHER
# ─────────────────────────────────────────────

class Teacher(models.Model):
    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id    = models.CharField(max_length=20, unique=True, editable=False, blank=True)
    date_of_birth  = models.DateField(null=True, blank=True)
    qualification  = models.CharField(max_length=200, blank=True, null=True)
    specialization = models.CharField(max_length=200, blank=True, null=True)
    date_joined    = models.DateField(default=timezone.now)
    is_active      = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'teachers'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

    def save(self, *args, **kwargs):
        if not self.employee_id:
            year = timezone.now().year
            uid  = str(uuid.uuid4()).replace('-', '').upper()[:5]
            self.employee_id = f"TCH-{year}-{uid}"
        super().save(*args, **kwargs)

    @property
    def assigned_class(self):
        """Returns the class where this teacher is the class teacher."""
        return SchoolClass.objects.filter(class_teacher=self).first()


# ─────────────────────────────────────────────
# STUDENT
# ─────────────────────────────────────────────

class Student(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female')]

    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id_number = models.CharField(max_length=20, unique=True, blank=True)
    date_of_birth     = models.DateField()
    gender            = models.CharField(max_length=1, choices=GENDER_CHOICES)

    # FIX: removed the redundant `current_class` FK.
    # It duplicated StudentEnrollment and would go stale. Use `current_enrollment` property instead.

    emergency_contact_name         = models.CharField(max_length=100)
    emergency_contact_phone        = models.CharField(max_length=20)
    emergency_contact_relationship = models.CharField(max_length=50)

    medical_notes   = models.TextField(blank=True, null=True)
    blood_group     = models.CharField(max_length=5, blank=True, null=True)
    allergies       = models.TextField(blank=True, null=True)

    admission_date  = models.DateField(default=timezone.now)
    is_active       = models.BooleanField(default=True)
    graduation_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'students'
        ordering = ['user__last_name']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id_number})"

    def save(self, *args, **kwargs):
        if not self.student_id_number:
            year = timezone.now().year
            uid  = str(uuid.uuid4()).replace('-', '').upper()[:6]
            self.student_id_number = f"STU-{year}-{uid}"
        super().save(*args, **kwargs)

    @property
    def current_enrollment(self):
        """Returns the active StudentEnrollment for the current academic year."""
        return self.enrollments.filter(is_active=True).select_related('class_assigned').first()

    @property
    def current_class(self):
        """Returns the student's current SchoolClass, or None."""
        enrollment = self.current_enrollment
        return enrollment.class_assigned if enrollment else None


# ─────────────────────────────────────────────
# YEAR-END PROMOTION
# ─────────────────────────────────────────────

class YearEndPromotion(models.Model):
    STATUS_CHOICES = [
        ('returning', 'Returning'),
        ('repeating', 'Repeating Same Grade'),
        ('leaving',   'Leaving School'),
        ('graduated', 'Graduated'),
    ]

    student       = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='promotions')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='promotions')
    current_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='promotion_records')
    status        = models.CharField(max_length=20, choices=STATUS_CHOICES, default='returning')
    next_class    = models.ForeignKey(
        SchoolClass, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='incoming_students'
    )
    class_teacher_note = models.TextField(blank=True, null=True)
    recorded_by        = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True)
    recorded_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'year_end_promotions'
        unique_together = ['student', 'academic_year']
        ordering        = ['-academic_year', 'current_class']

    def __str__(self):
        return f"{self.student} — {self.academic_year} — {self.status}"


# ─────────────────────────────────────────────
# PARENT
# ─────────────────────────────────────────────

class Parent(models.Model):
    user       = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parent_profile')
    occupation = models.CharField(max_length=100, blank=True, null=True)
    address    = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'parents'
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return self.user.get_full_name()


class ParentStudent(models.Model):
    RELATIONSHIP_CHOICES = [
        ('father',   'Father'),
        ('mother',   'Mother'),
        ('guardian', 'Guardian'),
        ('other',    'Other'),
    ]

    parent              = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='student_relationships')
    student             = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parent_relationships')
    relationship        = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES)
    is_primary_contact  = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'parent_student'
        unique_together = ['parent', 'student']

    def __str__(self):
        return f"{self.parent} → {self.student} ({self.relationship})"


# ─────────────────────────────────────────────
# CLASS-SUBJECT-TEACHER ASSIGNMENT
# ─────────────────────────────────────────────

class ClassSubjectTeacher(models.Model):
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='subject_assignments')
    subject        = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='class_assignments')
    teacher        = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='teaching_assignments')
    academic_year  = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='teaching_assignments')
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'class_subject_teacher'
        unique_together = ['class_assigned', 'subject', 'academic_year']
        ordering        = ['class_assigned', 'subject']

    def __str__(self):
        teacher_name = self.teacher.user.get_full_name() if self.teacher else 'Unassigned'
        return f"{teacher_name} — {self.subject} — {self.class_assigned}"


# ─────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent',  'Absent'),
        ('late',    'Late'),
        ('excused', 'Excused'),
    ]

    student        = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='attendance_records')
    term           = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='attendance_records')
    date           = models.DateField()
    status         = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    remarks        = models.TextField(blank=True, null=True)
    marked_by      = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='marked_attendance')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'attendance'
        unique_together = ['student', 'date']
        ordering        = ['-date', 'student']
        indexes = [
            models.Index(fields=['date', 'class_assigned']),
            models.Index(fields=['student', 'date']),
        ]

    def __str__(self):
        return f"{self.student} — {self.date} — {self.status}"


# ─────────────────────────────────────────────
# ASSESSMENTS & GRADES
# ─────────────────────────────────────────────

class Assessment(models.Model):
    name           = models.CharField(max_length=100)
    term           = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='assessments')
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='assessments')
    subject        = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assessments')
    max_score       = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    assessment_date = models.DateField()
    description     = models.TextField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'assessments'
        ordering = ['term', 'assessment_date', 'subject']

    def __str__(self):
        return f"{self.name} — {self.subject} — {self.class_assigned} ({self.term})"


class Grade(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='grades')
    student    = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades')
    score      = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    comment    = models.TextField(blank=True, null=True)
    entered_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='entered_grades')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table        = 'grades'
        unique_together = ['assessment', 'student']
        ordering        = ['assessment', 'student']

    def __str__(self):
        return f"{self.student} — {self.assessment.name} — {self.score}"


class ReportCard(models.Model):
    student               = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='report_cards')
    term                  = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='report_cards')
    overall_average       = models.DecimalField(max_digits=5, decimal_places=2)
    class_teacher_comment = models.TextField(blank=True, null=True)
    principal_comment     = models.TextField(blank=True, null=True)
    attendance_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    days_present          = models.IntegerField()
    days_absent           = models.IntegerField()
    generated_date        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'report_cards'
        unique_together = ['student', 'term']
        ordering        = ['-term', 'student']

    def __str__(self):
        return f"{self.student} — {self.term} — Report Card"


# ─────────────────────────────────────────────
# ASSIGNMENTS
# ─────────────────────────────────────────────

class Assignment(models.Model):
    title          = models.CharField(max_length=200)
    description    = models.TextField()
    class_assigned = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name='assignments')
    subject        = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    teacher        = models.ForeignKey(Teacher, on_delete=models.CASCADE, related_name='created_assignments')
    attachment     = models.FileField(upload_to='assignments/', null=True, blank=True)
    assigned_date  = models.DateTimeField(auto_now_add=True)
    due_date       = models.DateTimeField()
    max_score      = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    allow_late_submission = models.BooleanField(default=False)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'assignments'
        ordering = ['-due_date']

    def __str__(self):
        return f"{self.title} — {self.class_assigned.name}"

    @property
    def is_overdue(self):
        return timezone.now() > self.due_date


class AssignmentSubmission(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('graded',  'Graded'),
        ('returned', 'Returned for Revision'),
    ]

    assignment      = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student         = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_file = models.FileField(upload_to='submissions/')
    submission_text = models.TextField(blank=True, null=True)
    submitted_at    = models.DateTimeField(auto_now_add=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    score           = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    teacher_feedback = models.TextField(blank=True, null=True)
    graded_at       = models.DateTimeField(null=True, blank=True)
    graded_by       = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='graded_submissions')

    class Meta:
        db_table        = 'assignment_submissions'
        unique_together = ['assignment', 'student']
        ordering        = ['-submitted_at']

    def __str__(self):
        return f"{self.student} — {self.assignment.title}"

    @property
    def is_late(self):
        return self.submitted_at > self.assignment.due_date


class GradingScale(models.Model):
    min_score = models.DecimalField(max_digits=5, decimal_places=2)
    max_score = models.DecimalField(max_digits=5, decimal_places=2)
    grade     = models.CharField(max_length=5)
    comment   = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-min_score']

    def __str__(self):
        return f"{self.grade} ({self.min_score}–{self.max_score})"


# ─────────────────────────────────────────────
# ACTIVITY LOG
# ─────────────────────────────────────────────

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'), ('update', 'Update'), ('delete', 'Delete'),
        ('login',  'Login'),  ('logout', 'Logout'),
    ]

    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='activity_logs')
    action     = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id  = models.IntegerField(null=True, blank=True)
    description = models.TextField()
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'activity_logs'
        ordering = ['-timestamp']
        indexes  = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.user} — {self.action} — {self.model_name} — {self.timestamp}"