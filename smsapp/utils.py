def get_grade_letter(percentage):
    """Looks up GradingScale table; falls back to hardcoded defaults."""
    from .models import GradingScale
    try:
        scale = GradingScale.objects.filter(
            min_score__lte=percentage, max_score__gte=percentage
        ).first()
        if scale:
            return scale.grade
    except Exception:
        pass

    if percentage >= 90: return 'A+'
    if percentage >= 80: return 'A'
    if percentage >= 70: return 'B'
    if percentage >= 60: return 'C'
    if percentage >= 50: return 'D'
    return 'F'


def get_term_subject_mark(student, subject, term):
    from .models import Grade
    grades = Grade.objects.filter(
        student=student,
        assessment__subject=subject,
        assessment__term=term,
    ).select_related('assessment')

    total_scored = sum(g.score for g in grades)
    total_possible = sum(g.assessment.max_score for g in grades)

    if not grades.exists() or total_possible == 0:
        return None
    return round((float(total_scored) / float(total_possible)) * 100, 1)
