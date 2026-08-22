from app.services.job_vacancy_identity import canonical_candidate_fingerprint


def test_same_vacancy_different_urls_has_same_identity():
    first = {
        "job_title": "Manufacturing Technician",
        "job_url": "https://example.com/jobs/123?source=careers",
        "city": "Bolton",
        "province": "Ontario",
        "country": "Canada",
    }
    second = {
        "job_title": "  manufacturing   technician ",
        "job_url": "https://ats.example.com/job/123",
        "city": "BOLTON",
        "province": "ontario",
        "country": "CANADA",
    }
    assert canonical_candidate_fingerprint(first, "watch-1") == canonical_candidate_fingerprint(second, "watch-1")


def test_different_titles_remain_distinct():
    first = {"job_title": "Manufacturing Technician", "city": "Bolton", "province": "Ontario", "country": "Canada"}
    second = {"job_title": "Quality Technician", "city": "Bolton", "province": "Ontario", "country": "Canada"}
    assert canonical_candidate_fingerprint(first, "watch-1") != canonical_candidate_fingerprint(second, "watch-1")


def test_same_title_different_location_remains_distinct():
    first = {"job_title": "Manufacturing Technician", "city": "Bolton", "province": "Ontario", "country": "Canada"}
    second = {"job_title": "Manufacturing Technician", "city": "Calgary", "province": "Alberta", "country": "Canada"}
    assert canonical_candidate_fingerprint(first, "watch-1") != canonical_candidate_fingerprint(second, "watch-1")


def test_same_role_on_different_watch_remains_distinct():
    candidate = {"job_title": "Manufacturing Technician", "city": "Bolton", "province": "Ontario", "country": "Canada"}
    assert canonical_candidate_fingerprint(candidate, "watch-1") != canonical_candidate_fingerprint(candidate, "watch-2")
