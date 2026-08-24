from app.services.job_employer_intelligence import canonical_employer_key,deduplicate_employers,employer_contract,normalize_domain,normalize_employer_name,same_employer


def test_legal_suffixes_do_not_fragment_canonical_name():
    assert normalize_employer_name("Example Manufacturing Ltd.")=="example manufacturing"
    assert normalize_employer_name("Example Manufacturing LLC")=="example manufacturing"


def test_domain_normalization_removes_scheme_www_and_path():
    assert normalize_domain("https://www.example.com/careers/jobs") == "example.com"


def test_same_verified_domain_produces_same_canonical_key_across_name_variants():
    a=canonical_employer_key(name="Example Manufacturing Ltd",domain="https://example.com",country="Canada")
    b=canonical_employer_key(name="Example Mfg",domain="www.example.com",country="United States")
    assert a==b


def test_name_without_domain_is_country_scoped_to_prevent_false_cross_country_merge():
    a=canonical_employer_key(name="Acme Ltd",country="Canada")
    b=canonical_employer_key(name="Acme Limited",country="Germany")
    assert a!=b
    result=same_employer({"name":"Acme Ltd","country":"Canada"},{"name":"Acme Limited","country":"Germany"})
    assert result["matched"] is False
    assert result["safety"]["cross_country_name_only_merge_allowed"] is False


def test_deduplication_groups_exact_canonical_identity_and_preserves_aliases():
    rows=[{"name":"Example Manufacturing Ltd","domain":"example.com"},{"name":"Example Mfg","domain":"https://www.example.com","aliases":["Example Group"]}]
    result=deduplicate_employers(rows)
    assert len(result)==1
    assert result[0]["source_records"]==2
    assert "Example Mfg" in result[0]["aliases"]


def test_employer_contract_does_not_turn_identity_into_sponsorship_or_verification_claim():
    result=employer_contract({"name":"Example Manufacturing","country":"Canada"})
    assert result["relationships"]["vacancies"] is True
    assert result["relationships"]["campaigns"] is True
    assert result["safety"]["canonical_identity_is_not_employer_verification"] is True
    assert result["safety"]["sponsorship_not_inferred"] is True
    assert result["safety"]["relocation_support_not_inferred"] is True
