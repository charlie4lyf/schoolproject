from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from ..models import AcademicYear, Term, Subject, GradingScale, GradeSubjectConfig, SchoolClass, ClassSubjectTeacher, GRADE_CHOICES
from ..forms import AcademicYearForm, TermForm, SubjectForm, GradingScaleForm, GradeSubjectConfigForm, ClassSubjectTeacherForm
from ..decorators import admin_required

@login_required
@admin_required
def settings_dashboard(request):
    return render(request, 'settings/dashboard.html')


@login_required
@admin_required
def academic_year_list(request):
    years = AcademicYear.objects.all().order_by('-start_date')
    return render(request, 'settings/academic_year_list.html', {'years': years})


@login_required
@admin_required
def academic_year_manage(request, pk=None):
    if pk:
        year = get_object_or_404(AcademicYear, pk=pk)
        title = 'Edit Academic Year'
    else:
        year = None
        title = 'Add Academic Year'

    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=year)
        if form.is_valid():
            if form.cleaned_data['is_active']:
                AcademicYear.objects.all().update(is_active=False)
            form.save()
            messages.success(request, 'Academic Year saved successfully.')
            return redirect('academic_year_list')
    else:
        form = AcademicYearForm(instance=year)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'academic_year_list'
    })


@login_required
@admin_required
def term_manage(request, pk=None):
    if pk:
        term = get_object_or_404(Term, pk=pk)
        title = 'Edit Term'
    else:
        term = None
        title = 'Add Term'

    if request.method == 'POST':
        form = TermForm(request.POST, instance=term)
        if form.is_valid():
            if form.cleaned_data['is_active']:
                Term.objects.all().update(is_active=False)
            form.save()
            messages.success(request, 'Term saved successfully.')
            return redirect('term_list')
    else:
        form = TermForm(instance=term)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'term_list'
    })


@login_required
@admin_required
def subject_manage(request, pk=None):
    if pk:
        subject = get_object_or_404(Subject, pk=pk)
        title = 'Edit Subject'
    else:
        subject = None
        title = 'Add Subject'

    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject saved successfully.')
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'subject_list'
    })


@login_required
@admin_required
def term_list(request):
    terms = Term.objects.all().order_by('-start_date')
    return render(request, 'settings/term_list.html', {'terms': terms})


@login_required
@admin_required
def subject_list(request):
    subjects = Subject.objects.annotate(
        class_count=Count('class_assignments')
    ).order_by('name')
    return render(request, 'settings/subject_list.html', {'subjects': subjects})


@login_required
@admin_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted.')
        return redirect('subject_list')
    return render(request, 'settings/confirm_delete.html', {'object': subject, 'type': 'Subject'})


@login_required
@admin_required
def grading_scale(request):
    scales = GradingScale.objects.all().order_by('-min_score')
    form   = GradingScaleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Grade scale added.')
        return redirect('grading_scale')
    return render(request, 'settings/grading_scale.html', {'scales': scales, 'form': form})


@login_required
@admin_required
def grading_scale_delete(request, pk):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('grading_scale')
    get_object_or_404(GradingScale, pk=pk).delete()
    messages.success(request, 'Grade scale removed.')
    return redirect('grading_scale')


@login_required
@admin_required
def grade_subject_config_list(request):
    configs = GradeSubjectConfig.objects.select_related('subject').order_by('grade_level', 'subject__name')
    grouped_configs = {grade[0]: [] for grade in GRADE_CHOICES}
    for config in configs:
        grouped_configs[config.grade_level].append(config)
    context = {
        'grouped_configs': grouped_configs,
        'grade_choices': GRADE_CHOICES,
    }
    return render(request, 'settings/grade_subject_config.html', context)


@login_required
@admin_required
def grade_subject_config_add(request, grade_level):
    if request.method == 'POST':
        form = GradeSubjectConfigForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.grade_level = grade_level
            config.save()
            messages.success(request, f'Subject added to {dict(GRADE_CHOICES).get(grade_level)}')
            return redirect('grade_subject_config_list')
    else:
        form = GradeSubjectConfigForm()
        existing_subjects = GradeSubjectConfig.objects.filter(grade_level=grade_level).values_list('subject_id', flat=True)
        form.fields['subject'].queryset = Subject.objects.exclude(id__in=existing_subjects)
    
    context = {
        'form': form,
        'grade_level': grade_level,
        'grade_name': dict(GRADE_CHOICES).get(grade_level),
        'title': f'Add Subject to {dict(GRADE_CHOICES).get(grade_level)}',
    }
    return render(request, 'settings/form_base.html', context)


@login_required
@admin_required
def grade_subject_config_edit(request, pk):
    config = get_object_or_404(GradeSubjectConfig, pk=pk)
    if request.method == 'POST':
        form = GradeSubjectConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuration updated successfully')
            return redirect('grade_subject_config_list')
    else:
        form = GradeSubjectConfigForm(instance=config)
    
    context = {
        'form': form,
        'title': f'Edit {config.subject.name} for {config.get_grade_level_display()}',
        'cancel_url': 'grade_subject_config_list',
    }
    return render(request, 'settings/form_base.html', context)


@login_required
@admin_required
def grade_subject_config_delete(request, pk):
    config = get_object_or_404(GradeSubjectConfig, pk=pk)
    if request.method == 'POST':
        config.delete()
        messages.success(request, 'Configuration removed successfully')
        return redirect('grade_subject_config_list')
    
    return render(request, 'settings/confirm_delete.html', {
        'object': config,
        'type': f'Subject {config.subject.name} from {config.get_grade_level_display()}'
    })


@login_required
@admin_required
def class_subject_assignment_list(request, class_id=None):
    if class_id:
        class_obj = get_object_or_404(SchoolClass, pk=class_id)
        assignments = ClassSubjectTeacher.objects.filter(
            class_assigned=class_obj
        ).select_related('subject', 'teacher__user', 'academic_year')
        context = {
            'class_obj': class_obj,
            'assignments': assignments,
        }
        return render(request, 'classes/class_subject_assignments.html', context)
    else:
        classes = SchoolClass.objects.select_related('academic_year', 'class_teacher__user').annotate(
            subject_count=Count('subject_assignments')
        ).order_by('academic_year', 'grade_level', 'name')
        context = {'classes': classes}
        return render(request, 'classes/class_subject_list.html', context)


@login_required
@admin_required
def class_subject_assign(request, class_id):
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    if request.method == 'POST':
        form = ClassSubjectTeacherForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.class_assigned = class_obj
            exists = ClassSubjectTeacher.objects.filter(
                class_assigned=class_obj,
                subject=assignment.subject,
                academic_year=assignment.academic_year
            ).exists()
            if exists:
                messages.error(
                    request, 
                    f'Subject "{assignment.subject.name}" is already assigned to {class_obj.name} for {assignment.academic_year.name}'
                )
            else:
                assignment.save()
                messages.success(
                    request, 
                    f'Subject "{assignment.subject.name}" assigned to {class_obj.name} successfully!'
                )
                return redirect('class_subject_assignment_list', class_id=class_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        active_year = AcademicYear.objects.filter(is_active=True).first()
        initial_data = {}
        if active_year:
            initial_data['academic_year'] = active_year.id
        form = ClassSubjectTeacherForm(initial=initial_data)
        configured_subject_ids = GradeSubjectConfig.objects.filter(
            grade_level=class_obj.grade_level
        ).values_list('subject_id', flat=True)

        if active_year:
            assigned_subjects = ClassSubjectTeacher.objects.filter(
                class_assigned=class_obj,
                academic_year=active_year
            ).values_list('subject_id', flat=True)
            form.fields['subject'].queryset = Subject.objects.filter(
                id__in=configured_subject_ids
            ).exclude(id__in=assigned_subjects).order_by('name')
        else:
            form.fields['subject'].queryset = Subject.objects.filter(
                id__in=configured_subject_ids
            ).order_by('name')

        if hasattr(form.fields['subject'], 'queryset') and form.fields['subject'].queryset.count() == 0:
            messages.info(
                request,
                f'All grade-configured subjects have been assigned to {class_obj.name} for this academic year.'
            )
    
    context = {
        'form': form,
        'class_obj': class_obj,
        'title': f'Assign Subject to {class_obj.name}',
        'cancel_url': 'class_subject_assignment_list',
        'cancel_args': [class_id],
    }
    return render(request, 'settings/form_base.html', context)


@login_required
@admin_required
def class_subject_remove(request, assignment_id):
    assignment = get_object_or_404(ClassSubjectTeacher, pk=assignment_id)
    class_id = assignment.class_assigned.id
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Subject assignment removed successfully')
        return redirect('class_subject_assignment_list', class_id=class_id)
    return render(request, 'settings/confirm_delete.html', {
        'object': assignment,
        'type': f'Subject {assignment.subject.name} from {assignment.class_assigned.name}',
    })
