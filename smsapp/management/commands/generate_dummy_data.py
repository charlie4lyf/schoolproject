"""
Management command to generate dummy data for the School Management System.

Usage:
    python manage.py generate_dummy_data [--clean]

Options:
    --clean     Delete existing data before generating new data
"""

import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from smsapp.models import (
    User, AcademicYear, Term, Subject, GradeSubjectConfig,
    SchoolClass, Student, Teacher, Parent, StudentEnrollment,
    ClassSubjectTeacher, Attendance, Assessment, Grade,
    Assignment, AssignmentSubmission, GradingScale, ParentStudent
)


class Command(BaseCommand):
    help = 'Generate dummy data for the School Management System'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Delete existing data before generating new data',
        )
        parser.add_argument(
            '--students',
            type=int,
            default=100,
            help='Number of students to create (default: 100)',
        )
        parser.add_argument(
            '--teachers',
            type=int,
            default=15,
            help='Number of teachers to create (default: 15)',
        )
        parser.add_argument(
            '--parents',
            type=int,
            default=80,
            help='Number of parents to create (default: 80)',
        )

    def handle(self, *args, **options):
        self.clean = options['clean']
        self.num_students = options['students']
        self.num_teachers = options['teachers']
        self.num_parents = options['parents']

        if self.clean:
            self.stdout.write(self.style.WARNING('Deleting existing data...'))
            self.delete_existing_data()

        self.stdout.write(self.style.SUCCESS('Generating dummy data...'))

        with transaction.atomic():
            self.create_grading_scale()
            self.create_academic_years_and_terms()
            self.create_subjects()
            self.create_grade_subject_configs()
            self.create_admin_user()
            self.create_teachers()
            self.create_classes()
            self.create_students()
            self.create_parents()
            self.create_teacher_assignments()
            self.create_student_enrollments()
            self.create_attendance_records()
            self.create_assessments_and_grades()
            self.create_assignments_and_submissions()

        self.stdout.write(self.style.SUCCESS('Dummy data generated successfully!'))
        self.print_summary()

    def delete_existing_data(self):
        """Delete all existing data in reverse order of dependencies."""
        models_to_delete = [
            AssignmentSubmission, Assignment, Grade, Assessment,
            Attendance, ClassSubjectTeacher,
            StudentEnrollment, ParentStudent, Parent, Student, Teacher,
            SchoolClass, GradeSubjectConfig, Subject, Term, AcademicYear,
            GradingScale,
        ]
        for model in models_to_delete:
            count = model.objects.all().count()
            model.objects.all().delete()
            self.stdout.write(f'  Deleted {count} {model.__name__} records')
        
        # Delete non-superuser users
        users_deleted = User.objects.filter(is_superuser=False).delete()
        self.stdout.write(f'  Deleted {users_deleted[0]} non-superuser records')

    def create_grading_scale(self):
        """Create standard grading scale."""
        self.stdout.write('Creating grading scale...')
        scales = [
            ('A', 80, 100, 'Excellent'),
            ('B', 70, 79, 'Very Good'),
            ('C', 60, 69, 'Good'),
            ('D', 50, 59, 'Pass'),
            ('E', 40, 49, 'Weak Pass'),
            ('U', 0, 39, 'Fail'),
        ]
        for grade, min_score, max_score, comment in scales:
            GradingScale.objects.get_or_create(
                grade=grade,
                defaults={'min_score': min_score, 'max_score': max_score, 'comment': comment}
            )

    def create_academic_years_and_terms(self):
        """Create academic years and terms."""
        self.stdout.write('Creating academic years and terms...')
        
        current_year = timezone.now().year
        
        # Create current and previous academic year
        for year_offset in [0, -1]:
            year = current_year + year_offset
            ay, _ = AcademicYear.objects.get_or_create(
                name=str(year),
                defaults={
                    'start_date': datetime(year, 1, 1).date(),
                    'end_date': datetime(year, 12, 31).date(),
                    'is_active': year_offset == 0,
                }
            )
            
            # Create 3 terms for each year
            terms = [
                ('Term 1', datetime(year, 1, 1).date(), datetime(year, 4, 30).date()),
                ('Term 2', datetime(year, 5, 1).date(), datetime(year, 8, 31).date()),
                ('Term 3', datetime(year, 9, 1).date(), datetime(year, 12, 15).date()),
            ]
            
            for i, (name, start, end) in enumerate(terms, 1):
                Term.objects.get_or_create(
                    academic_year=ay,
                    name=name,
                    defaults={
                        'start_date': start,
                        'end_date': end,
                        'is_active': year_offset == 0 and i == 1,  # First term of current year is active
                    }
                )
        
        self.academic_year = AcademicYear.objects.get(is_active=True)
        self.current_term = Term.objects.get(is_active=True)

    def create_subjects(self):
        """Create standard school subjects."""
        self.stdout.write('Creating subjects...')
        subjects_data = [
            ('Mathematics', 'MATH'),
            ('English Language', 'ENG'),
            ('Science', 'SCI'),
            ('Social Studies', 'SOC'),
            ('History', 'HIST'),
            ('Geography', 'GEO'),
            ('Biology', 'BIO'),
            ('Chemistry', 'CHEM'),
            ('Physics', 'PHY'),
            ('Computer Studies', 'COMP'),
            ('Physical Education', 'PE'),
            ('Art and Design', 'ART'),
            ('Music', 'MUS'),
            ('Religious Studies', 'RS'),
            ('Shona', 'SHO'),
            ('Agriculture', 'AGR'),
            ('Commerce', 'COMM'),
            ('Accounts', 'ACC'),
            ('Business Studies', 'BUS'),
            ('Food and Nutrition', 'FAN'),
        ]
        
        self.subjects = []
        for name, code in subjects_data:
            subject, _ = Subject.objects.get_or_create(
                code=code,
                defaults={'name': name, 'description': f'{name} subject'}
            )
            self.subjects.append(subject)

    def create_grade_subject_configs(self):
        """Configure subjects for each grade level."""
        self.stdout.write('Creating grade-subject configurations...')
        
        grade_levels = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6']
        
        # Core subjects for all grades
        core_subjects = ['MATH', 'ENG', 'SCI', 'SOC', 'RS', 'PE']
        
        # Additional subjects by grade level
        primary_additional = ['HIST', 'GEO', 'ART', 'MUS', 'SHO']
        secondary_forms = ['HIST', 'GEO', 'BIO', 'CHEM', 'PHY', 'COMP']
        form4_plus = ['COMM', 'ACC', 'BUS', 'AGR']
        
        for grade in grade_levels:
            # Core subjects (compulsory)
            for code in core_subjects:
                subject = Subject.objects.get(code=code)
                GradeSubjectConfig.objects.get_or_create(
                    grade_level=grade,
                    subject=subject,
                    defaults={'is_compulsory': True, 'is_elective': False}
                )
            
            # Additional subjects based on grade
            if grade.startswith('G'):
                additional = primary_additional
            elif grade in ['F1', 'F2', 'F3']:
                additional = secondary_forms
            else:
                additional = secondary_forms + form4_plus
            
            for code in additional:
                subject = Subject.objects.get(code=code)
                is_elective = grade in ['F4', 'F5', 'F6'] and code in form4_plus
                GradeSubjectConfig.objects.get_or_create(
                    grade_level=grade,
                    subject=subject,
                    defaults={
                        'is_compulsory': not is_elective,
                        'is_elective': is_elective
                    }
                )

    def create_admin_user(self):
        """Create admin user."""
        self.stdout.write('Creating admin user...')
        self.admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'System',
                'last_name': 'Administrator',
                'email': 'admin@school.edu',
                'role': 'admin',
                'is_staff': True,
                'is_superuser': True,
            }
        )
        self.admin_user.set_password('admin123')
        self.admin_user.save()

    def create_teachers(self):
        """Create teacher users and profiles."""
        self.stdout.write(f'Creating {self.num_teachers} teachers...')
        
        first_names = ['John', 'Mary', 'James', 'Patricia', 'Robert', 'Jennifer', 'Michael', 'Linda',
                       'William', 'Elizabeth', 'David', 'Barbara', 'Richard', 'Susan', 'Joseph',
                       'Jessica', 'Thomas', 'Sarah', 'Charles', 'Karen', 'Christopher', 'Nancy']
        last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
                      'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
                      'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez']
        
        qualifications = ['B.Ed', 'M.Ed', 'BSc', 'MSc', 'BA', 'MA', 'Diploma in Education']
        specializations = ['Mathematics', 'Science', 'Languages', 'Humanities', 'Technical', 'Arts']
        
        self.teachers = []
        for i in range(self.num_teachers):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f"teacher{i+1:02d}"
            
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f"{username}@school.edu",
                    'role': 'teacher',
                    'phone': f"07{random.randint(10000000, 99999999)}",
                }
            )
            user.set_password('teacher123')
            user.save()
            
            # Create teacher profile
            dob = datetime(random.randint(1970, 1995), random.randint(1, 12), random.randint(1, 28)).date()
            teacher, _ = Teacher.objects.get_or_create(
                user=user,
                defaults={
                    'date_of_birth': dob,
                    'qualification': random.choice(qualifications),
                    'specialization': random.choice(specializations),
                    'date_joined': datetime(random.randint(2015, 2023), random.randint(1, 12), 1).date(),
                    'is_active': True,
                }
            )
            self.teachers.append(teacher)

    def create_classes(self):
        """Create school classes with auto-populated subjects from GradeSubjectConfig."""
        self.stdout.write('Creating classes...')

        grade_levels = ['G1', 'G2', 'G3', 'G4', 'G5', 'G6', 'G7', 'F1', 'F2', 'F3', 'F4', 'F5', 'F6']
        sections = ['A', 'B', 'C']

        self.classes = []
        for grade in grade_levels:
            for section in sections:
                class_name = f"{self._grade_to_name(grade)} {section}"
                class_teacher = random.choice(self.teachers) if random.random() > 0.3 else None

                school_class, created = SchoolClass.objects.get_or_create(
                    name=class_name,
                    academic_year=self.academic_year,
                    defaults={
                        'grade_level': grade,
                        'class_teacher': class_teacher,
                        'room_number': f"R{random.randint(1, 50):02d}",
                        'capacity': random.randint(30, 45),
                    }
                )
                self.classes.append(school_class)

                # Auto-populate ALL subjects from GradeSubjectConfig for this grade
                if created:
                    configs = GradeSubjectConfig.objects.filter(grade_level=grade)
                    for config in configs:
                        ClassSubjectTeacher.objects.get_or_create(
                            class_assigned=school_class,
                            subject=config.subject,
                            academic_year=self.academic_year,
                            defaults={'teacher': None}
                        )

    def _grade_to_name(self, grade):
        """Convert grade code to display name."""
        mapping = {
            'G1': 'Grade 1', 'G2': 'Grade 2', 'G3': 'Grade 3',
            'G4': 'Grade 4', 'G5': 'Grade 5', 'G6': 'Grade 6', 'G7': 'Grade 7',
            'F1': 'Form 1', 'F2': 'Form 2', 'F3': 'Form 3',
            'F4': 'Form 4', 'F5': 'Form 5', 'F6': 'Form 6',
        }
        return mapping.get(grade, grade)

    def create_students(self):
        """Create student users and profiles."""
        self.stdout.write(f'Creating {self.num_students} students...')
        
        first_names_male = ['Tendai', 'Kudakwashe', 'Tatenda', 'Farai', 'Simba', 'Tawanda', 'Blessing',
                           'Prince', 'Tinashe', 'Shingirai', 'Tanaka', 'Ngonidzashe', 'Tadiwa', 'Munashe']
        first_names_female = ['Rudo', 'Tariro', 'Ashley', 'Michelle', 'Tanatswa', 'Natasha', 'Beloved',
                             'Faith', 'Hope', 'Joy', 'Grace', 'Blessing', 'Patience', 'Memory']
        last_names = ['Moyo', 'Sibanda', 'Ndlovu', 'Dube', 'Ncube', 'Mpofu', 'Mhlanga', 'Shumba',
                      'Gumbo', 'Mupfumi', 'Chikomo', 'Mupfumi', 'Makoni', 'Katsande', 'Charamba']
        
        genders = ['M', 'F']
        relationships = ['Father', 'Mother', 'Uncle', 'Aunt', 'Grandmother', 'Grandfather']
        
        self.students = []
        for i in range(self.num_students):
            gender = random.choice(genders)
            first_name = random.choice(first_names_male if gender == 'M' else first_names_female)
            last_name = random.choice(last_names)
            
            user, _ = User.objects.get_or_create(
                username=f"student{i+1:03d}",
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f"student{i+1:03d}@school.edu",
                    'role': 'student',
                }
            )
            user.set_password('student123')
            user.save()
            
            # Create student profile
            year = random.randint(2005, 2018)
            dob = datetime(year, random.randint(1, 12), random.randint(1, 28)).date()
            
            student, _ = Student.objects.get_or_create(
                user=user,
                defaults={
                    'date_of_birth': dob,
                    'gender': gender,
                    'emergency_contact_name': f"{random.choice(last_names)} Family",
                    'emergency_contact_phone': f"07{random.randint(10000000, 99999999)}",
                    'emergency_contact_relationship': random.choice(relationships),
                    'blood_group': random.choice(['A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-']),
                    'admission_date': datetime(random.randint(2019, 2024), 1, 1).date(),
                    'is_active': True,
                }
            )
            self.students.append(student)

    def create_parents(self):
        """Create parent users and profiles."""
        self.stdout.write(f'Creating {self.num_parents} parents...')
        
        first_names_male = ['John', 'Peter', 'Paul', 'George', 'James', 'William', 'Thomas', 'Robert']
        first_names_female = ['Mary', 'Jane', 'Elizabeth', 'Margaret', 'Sarah', 'Patricia', 'Linda', 'Barbara']
        last_names = ['Moyo', 'Sibanda', 'Ndlovu', 'Dube', 'Ncube', 'Mpofu', 'Mhlanga', 'Shumba']
        occupations = ['Teacher', 'Doctor', 'Nurse', 'Farmer', 'Business Owner', 'Engineer', 'Accountant',
                      'Driver', 'Mechanic', 'Lecturer', 'Government Worker', 'Self-employed', 'Unemployed']
        
        self.parents = []
        for i in range(self.num_parents):
            gender = random.choice(['M', 'F'])
            first_name = random.choice(first_names_male if gender == 'M' else first_names_female)
            last_name = random.choice(last_names)
            
            user, _ = User.objects.get_or_create(
                username=f"parent{i+1:03d}",
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f"parent{i+1:03d}@email.com",
                    'role': 'parent',
                    'phone': f"07{random.randint(10000000, 99999999)}",
                }
            )
            user.set_password('parent123')
            user.save()
            
            parent, _ = Parent.objects.get_or_create(
                user=user,
                defaults={
                    'occupation': random.choice(occupations),
                    'address': f"{random.randint(1, 999)} {random.choice(['Main', 'Church', 'School', 'Market'])} Street, Harare",
                }
            )
            self.parents.append(parent)
        
        # Link parents to students
        self.stdout.write('Linking parents to students...')
        relationships = ['father', 'mother', 'guardian', 'other']
        
        for student in self.students:
            # Each student gets 1-2 parents
            num_parents = random.randint(1, 2)
            assigned_parents = random.sample(self.parents, min(num_parents, len(self.parents)))
            
            for i, parent in enumerate(assigned_parents):
                ParentStudent.objects.get_or_create(
                    parent=parent,
                    student=student,
                    defaults={
                        'relationship': relationships[i] if i < 2 else random.choice(relationships),
                        'is_primary_contact': i == 0,
                    }
                )

    def create_teacher_assignments(self):
        """Assign teachers to existing class-subject records (all subjects already exist)."""
        self.stdout.write('Assigning teachers to class subjects...')

        for school_class in self.classes:
            # Get all subjects for this class (already auto-populated)
            subject_assignments = ClassSubjectTeacher.objects.filter(
                class_assigned=school_class,
                academic_year=self.academic_year,
                teacher__isnull=True  # Only assign to unassigned subjects
            )

            # Assign teachers to 70% of subjects (realistic scenario)
            if subject_assignments.exists():
                assignments_list = list(subject_assignments)
                num_to_assign = int(len(assignments_list) * 0.7)
                selected = random.sample(assignments_list, min(num_to_assign, len(assignments_list)))

                for assignment in selected:
                    teacher = random.choice(self.teachers)
                    assignment.teacher = teacher
                    assignment.save()

    def create_student_enrollments(self):
        """Enroll students in classes."""
        self.stdout.write('Enrolling students in classes...')
        
        # Group classes by grade level
        classes_by_grade = {}
        for school_class in self.classes:
            if school_class.grade_level not in classes_by_grade:
                classes_by_grade[school_class.grade_level] = []
            classes_by_grade[school_class.grade_level].append(school_class)
        
        # Assign students to appropriate grade based on age
        for student in self.students:
            age = (timezone.now().date() - student.date_of_birth).days // 365
            
            # Determine grade level based on age
            if age < 7:
                grade = 'G1'
            elif age < 8:
                grade = 'G2'
            elif age < 9:
                grade = 'G3'
            elif age < 10:
                grade = 'G4'
            elif age < 11:
                grade = 'G5'
            elif age < 12:
                grade = 'G6'
            elif age < 13:
                grade = 'G7'
            elif age < 14:
                grade = 'F1'
            elif age < 15:
                grade = 'F2'
            elif age < 16:
                grade = 'F3'
            elif age < 17:
                grade = 'F4'
            elif age < 18:
                grade = 'F5'
            else:
                grade = 'F6'
            
            # Pick a random class in that grade
            if grade in classes_by_grade:
                school_class = random.choice(classes_by_grade[grade])
                StudentEnrollment.objects.get_or_create(
                    student=student,
                    academic_year=self.academic_year,
                    defaults={
                        'class_assigned': school_class,
                        'enrollment_date': datetime(self.academic_year.start_date.year, 1, random.randint(1, 28)).date(),
                        'is_active': True,
                    }
                )

    def create_attendance_records(self):
        """Create attendance records for the current term."""
        self.stdout.write('Creating attendance records...')
        
        # Get active enrollments
        enrollments = StudentEnrollment.objects.filter(is_active=True)
        
        # Create attendance for last 30 school days
        for day_offset in range(30):
            date = self.current_term.start_date + timedelta(days=day_offset)
            # Skip weekends
            if date.weekday() >= 5:
                continue
            
            for enrollment in enrollments[:50]:  # Limit to 50 students for performance
                # 85% attendance rate
                status = random.choices(
                    ['present', 'absent', 'late', 'excused'],
                    weights=[85, 8, 4, 3]
                )[0]
                
                Attendance.objects.get_or_create(
                    student=enrollment.student,
                    date=date,
                    defaults={
                        'class_assigned': enrollment.class_assigned,
                        'term': self.current_term,
                        'status': status,
                        'remarks': 'Auto-generated' if status != 'present' else '',
                        'marked_by': random.choice(self.teachers) if self.teachers else None,
                    }
                )

    def create_assessments_and_grades(self):
        """Create assessments and grades."""
        self.stdout.write('Creating assessments and grades...')

        # Get class-subject-teacher assignments WITH teachers only
        assignments = ClassSubjectTeacher.objects.filter(
            academic_year=self.academic_year,
            teacher__isnull=False
        ).select_related('teacher')
        
        assessment_types = ['Test 1', 'Test 2', 'Mid-term Exam', 'End of Term Exam', 'Assignment', 'Quiz']
        
        for assignment in assignments[:20]:  # Limit for performance
            # Create 2-4 assessments per subject
            for i in range(random.randint(2, 4)):
                assessment_name = f"{random.choice(assessment_types)} - {assignment.subject.name}"
                
                assessment, _ = Assessment.objects.get_or_create(
                    name=assessment_name,
                    term=self.current_term,
                    class_assigned=assignment.class_assigned,
                    subject=assignment.subject,
                    defaults={
                        'max_score': 100,
                        'assessment_date': self.current_term.start_date + timedelta(days=random.randint(7, 60)),
                        'description': f'Assessment for {assignment.subject.name}',
                    }
                )
                
                # Create grades for enrolled students
                enrollments = StudentEnrollment.objects.filter(
                    class_assigned=assignment.class_assigned,
                    is_active=True
                )
                
                for enrollment in enrollments:
                    # Generate realistic grade distribution
                    score = random.choices(
                        [random.randint(30, 49), random.randint(50, 59), random.randint(60, 69),
                         random.randint(70, 79), random.randint(80, 100)],
                        weights=[10, 15, 25, 30, 20]
                    )[0]
                    
                    Grade.objects.get_or_create(
                        assessment=assessment,
                        student=enrollment.student,
                        defaults={
                            'score': Decimal(str(score)),
                            'comment': 'Good work' if score >= 70 else 'Needs improvement' if score < 60 else 'Average',
                            'entered_by': assignment.teacher,
                        }
                    )

    def create_assignments_and_submissions(self):
        """Create assignments and submissions."""
        self.stdout.write('Creating assignments and submissions...')

        # Get class-subject assignments WITH teachers only
        class_subjects = ClassSubjectTeacher.objects.filter(
            academic_year=self.academic_year,
            teacher__isnull=False
        ).select_related('teacher')

        for cs in class_subjects[:15]:  # Limit for performance
            # Create 1-3 assignments per subject
            for i in range(random.randint(1, 3)):
                assignment_title = f"{cs.subject.name} Assignment {i+1}"

                assignment, _ = Assignment.objects.get_or_create(
                    title=assignment_title,
                    class_assigned=cs.class_assigned,
                    subject=cs.subject,
                    defaults={
                        'description': f'Complete the {cs.subject.name} assignment on the topic covered this term.',
                        'teacher': cs.teacher,
                        'due_date': timezone.now() + timedelta(days=random.randint(-7, 14)),
                        'max_score': random.choice([10, 20, 50, 100]),
                        'allow_late_submission': random.choice([True, False]),
                    }
                )
                
                # Create submissions from students
                enrollments = StudentEnrollment.objects.filter(
                    class_assigned=cs.class_assigned,
                    is_active=True
                )
                
                for enrollment in enrollments:
                    # 70% submission rate
                    if random.random() < 0.7:
                        is_late = timezone.now() > assignment.due_date and random.random() < 0.3
                        
                        submission, created = AssignmentSubmission.objects.get_or_create(
                            assignment=assignment,
                            student=enrollment.student,
                            defaults={
                                'submission_text': f'Submission by {enrollment.student.user.get_full_name()}',
                                'submitted_at': assignment.due_date - timedelta(days=random.randint(0, 3)) if not is_late 
                                               else assignment.due_date + timedelta(days=random.randint(1, 2)),
                                'status': random.choice(['pending', 'graded', 'returned']),
                            }
                        )
                        
                        # Grade some submissions
                        if created and submission.status == 'graded':
                            submission.score = Decimal(str(random.randint(40, 100)))
                            submission.teacher_feedback = random.choice([
                                'Excellent work!',
                                'Good effort, but could be improved.',
                                'Please review the material and resubmit.',
                                'Well done!',
                                'Satisfactory.',
                            ])
                            submission.graded_by = cs.teacher
                            submission.graded_at = timezone.now()
                            submission.save()

    def print_summary(self):
        """Print summary of created data."""
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('DUMMY DATA SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*50))
        
        models_count = [
            ('Users', User.objects.filter(is_superuser=False).count()),
            ('Teachers', Teacher.objects.count()),
            ('Students', Student.objects.count()),
            ('Parents', Parent.objects.count()),
            ('Academic Years', AcademicYear.objects.count()),
            ('Terms', Term.objects.count()),
            ('Subjects', Subject.objects.count()),
            ('Classes', SchoolClass.objects.count()),
            ('Student Enrollments', StudentEnrollment.objects.count()),
            ('Teacher Assignments', ClassSubjectTeacher.objects.count()),
            ('Attendance Records', Attendance.objects.count()),
            ('Assessments', Assessment.objects.count()),
            ('Grades', Grade.objects.count()),
            ('Assignments', Assignment.objects.count()),
            ('Assignment Submissions', AssignmentSubmission.objects.count()),
        ]
        
        for name, count in models_count:
            self.stdout.write(f'  {name:<25}: {count:>5}')
        
        self.stdout.write(self.style.SUCCESS('='*50))
        
        self.stdout.write(self.style.SUCCESS('\nLogin Credentials:'))
        self.stdout.write('  Admin:    username=admin,      password=admin123')
        self.stdout.write('  Teacher:  username=teacher01,  password=teacher123')
        self.stdout.write('  Student:  username=student001, password=student123')
        self.stdout.write('  Parent:   username=parent001,  password=parent123')
