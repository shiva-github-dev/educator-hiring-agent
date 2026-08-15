from graph.matching import (
    build_contact_pipeline,
    exam_matches,
    matches,
    normalize_exam,
    normalize_subject,
    parse_experience,
    subject_overlap,
)

EDUCATORS = [
    {"name": "A", "email": "a@x.com", "phone": "1", "subjects": "Maths", "years_exp": 3, "exam": "JEE"},
    {"name": "B", "email": "b@x.com", "phone": "2", "subjects": "Physics, Chemistry", "years_exp": 5, "exam": "Both"},
    {"name": "C", "email": "c@x.com", "phone": "3", "subjects": "Biology", "years_exp": 8, "exam": "NEET"},
    {"name": "D", "email": "d@x.com", "phone": "4", "subjects": "Mathematics", "years_exp": 1, "exam": "JEE"},
]


def test_subject_normalization():
    assert normalize_subject("Maths") == "mathematics"
    assert normalize_subject("Chemistry") == "chemistry"
    assert normalize_subject(" Bio ") == "biology"


def test_exam_normalization():
    assert normalize_exam("JEE") == "jee"
    assert normalize_exam("NEET") == "neet"
    assert normalize_exam("JEE & NEET") == "both"


def test_experience_parsing():
    assert parse_experience("2") == 2.0
    assert parse_experience("2,000") == 2000.0
    assert parse_experience("n/a") == 0.0


def test_subject_overlap():
    assert subject_overlap("Maths, Physics", "Mathematics")
    assert not subject_overlap("Chemistry", "Mathematics")


def test_exam_matches():
    assert exam_matches("JEE", "JEE")
    assert exam_matches("Both", "JEE")
    assert not exam_matches("NEET", "JEE")
    assert exam_matches("Both", "both")
    assert not exam_matches("JEE", "both")


def test_matches_combined():
    req = {"subject": "Physics", "exam": "JEE", "min_experience": 2}
    assert matches(EDUCATORS[1], req)
    assert not matches(EDUCATORS[0], req)  # maths, not physics
    assert not matches(EDUCATORS[2], req)  # biology/NEET


def test_build_pipeline():
    req = {"subject": "Mathematics", "exam": "JEE", "min_experience": 2}
    result = build_contact_pipeline(EDUCATORS, req)
    emails = [e["email"] for e in result]
    assert emails == ["a@x.com"]  # D excluded: only 1 yr exp


def test_no_subject_filters_only_by_exam_and_exp():
    req = {"subject": "", "exam": "NEET", "min_experience": 0}
    result = build_contact_pipeline(EDUCATORS, req)
    assert [e["email"] for e in result] == ["b@x.com", "c@x.com"]