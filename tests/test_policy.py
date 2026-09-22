import pytest

from ingestion.policy import (
    PolicyConflictError,
    build_policy_index,
    discover_documents,
    find_missing_policy_files,
    resolve_documents,
)


SAMPLE_POLICY = {
    "department_rules": {
        "hr_general": {
            "folders": ["hr/employee_handbook.md", "hr/benefits_guide.md"],
            "allowed_roles": ["hr_staff", "engineer", "executive"],
        },
        "hr_restricted": {
            "folders": ["hr/compensation_bands.md"],
            "allowed_roles": ["hr_staff", "executive"],
        },
        "engineering": {
            "folders": ["engineering/system_architecture.md"],
            "allowed_roles": ["engineer", "executive"],
        },
    },
    "default_rule": {"allowed_roles": ["executive"]},
}


def test_build_policy_index_maps_paths_to_rule_and_roles():
    index = build_policy_index(SAMPLE_POLICY)

    assert index["hr/employee_handbook.md"] == (
        "hr_general",
        ["hr_staff", "engineer", "executive"],
    )
    assert index["hr/compensation_bands.md"] == (
        "hr_restricted",
        ["hr_staff", "executive"],
    )


def test_build_policy_index_raises_on_conflict():
    conflicting = {
        "department_rules": {
            "hr_general": {
                "folders": ["hr/benefits_guide.md"],
                "allowed_roles": ["hr_staff", "engineer", "executive"],
            },
            "hr_restricted": {
                "folders": ["hr/benefits_guide.md"],
                "allowed_roles": ["hr_staff", "executive"],
            },
        }
    }

    with pytest.raises(PolicyConflictError) as exc_info:
        build_policy_index(conflicting)

    err = exc_info.value
    assert err.path == "hr/benefits_guide.md"
    assert {err.first_rule, err.second_rule} == {"hr_general", "hr_restricted"}


def test_discover_documents_finds_md_files(tmp_path):
    (tmp_path / "hr").mkdir()
    (tmp_path / "engineering").mkdir()
    (tmp_path / "hr" / "a.md").write_text("hi")
    (tmp_path / "hr" / "notes.txt").write_text("skip me")
    (tmp_path / "engineering" / "b.md").write_text("hi")

    found = discover_documents(str(tmp_path), ["hr", "engineering", "finance"])

    assert found == ["engineering/b.md", "hr/a.md"]


def test_discover_documents_matches_extension_case_insensitively(tmp_path):
    (tmp_path / "hr").mkdir()
    (tmp_path / "hr" / "a.md").write_text("hi")
    (tmp_path / "hr" / "b.MD").write_text("hi")
    (tmp_path / "hr" / "c.Md").write_text("hi")

    found = discover_documents(str(tmp_path), ["hr"])

    assert found == ["hr/a.md", "hr/b.MD", "hr/c.Md"]


def test_discover_documents_missing_folder_is_skipped(tmp_path):
    (tmp_path / "hr").mkdir()
    (tmp_path / "hr" / "a.md").write_text("hi")

    found = discover_documents(str(tmp_path), ["hr", "engineering", "finance"])

    assert found == ["hr/a.md"]


def test_resolve_documents_matched_file_uses_policy_roles():
    index = build_policy_index(SAMPLE_POLICY)
    resolved, warnings = resolve_documents(
        ["hr/compensation_bands.md"], index, SAMPLE_POLICY["default_rule"]
    )

    assert len(resolved) == 1
    doc = resolved[0]
    assert doc.department == "hr"
    assert doc.filename == "compensation_bands.md"
    assert doc.allowed_roles == ["hr_staff", "executive"]
    assert doc.used_default_rule is False
    assert warnings == []


def test_resolve_documents_unmatched_file_falls_back_to_default_and_warns():
    index = build_policy_index(SAMPLE_POLICY)
    resolved, warnings = resolve_documents(
        ["hr/unlisted_doc.md"], index, SAMPLE_POLICY["default_rule"]
    )

    assert len(resolved) == 1
    doc = resolved[0]
    assert doc.used_default_rule is True
    assert doc.allowed_roles == ["executive"]
    assert len(warnings) == 1
    assert "hr/unlisted_doc.md" in warnings[0]


def test_resolve_documents_empty_default_rule_warns_loudly_about_unreadability():
    index = build_policy_index(SAMPLE_POLICY)
    empty_default_rule = {"allowed_roles": []}

    resolved, warnings = resolve_documents(["hr/unlisted_doc.md"], index, empty_default_rule)

    assert resolved[0].allowed_roles == []
    assert len(warnings) == 2  # the generic "not listed" warning + the loud empty-roles one
    assert any("unreadable by ANY role" in w for w in warnings)
    assert any("default_rule" in w for w in warnings)


def test_resolve_documents_empty_allowed_roles_in_matched_rule_also_warns():
    policy_with_empty_rule = {
        "department_rules": {
            "broken_rule": {"folders": ["hr/broken.md"], "allowed_roles": []},
        },
        "default_rule": {"allowed_roles": ["executive"]},
    }
    index = build_policy_index(policy_with_empty_rule)

    resolved, warnings = resolve_documents(["hr/broken.md"], index, policy_with_empty_rule["default_rule"])

    assert resolved[0].allowed_roles == []
    assert resolved[0].used_default_rule is False  # it DID match a rule, just an empty one
    assert len(warnings) == 1
    assert "unreadable by ANY role" in warnings[0]
    assert "broken_rule" in warnings[0]


def test_resolve_documents_normal_case_has_no_empty_roles_warning():
    index = build_policy_index(SAMPLE_POLICY)
    resolved, warnings = resolve_documents(
        ["hr/compensation_bands.md"], index, SAMPLE_POLICY["default_rule"]
    )

    assert warnings == []


def test_find_missing_policy_files_detects_stale_entries():
    index = build_policy_index(SAMPLE_POLICY)
    # only one of the three policy-listed files actually exists on disk
    discovered = ["hr/employee_handbook.md"]

    missing = find_missing_policy_files(discovered, index)

    assert missing == [
        "engineering/system_architecture.md",
        "hr/benefits_guide.md",
        "hr/compensation_bands.md",
    ]
