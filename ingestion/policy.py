"""Resolve which department + allowed roles apply to each document on
disk, using access_policy.json as the source of truth."""

import json
import os
from dataclasses import dataclass, field


class PolicyConflictError(Exception):
    """Raised when a file path appears under more than one policy rule."""

    def __init__(self, path, first_rule, second_rule):
        self.path = path
        self.first_rule = first_rule
        self.second_rule = second_rule
        super().__init__(
            f"'{path}' is listed under both '{first_rule}' and "
            f"'{second_rule}' in access_policy.json. Fix the policy file "
            f"before ingesting."
        )


@dataclass
class ResolvedDocument:
    relative_path: str  # e.g. "hr/employee_handbook.md"
    filename: str  # e.g. "employee_handbook.md"
    department: str  # e.g. "hr"
    allowed_roles: list = field(default_factory=list)
    used_default_rule: bool = False
    matched_rule: str = None


def load_policy(policy_path):
    with open(policy_path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_policy_index(policy):
    """Map each policy-listed relative path -> (rule_name, allowed_roles).

    Raises PolicyConflictError if the same path is listed under two
    different rules.
    """
    index = {}
    for rule_name, rule in policy.get("department_rules", {}).items():
        for path in rule.get("folders", []):
            if path in index:
                first_rule = index[path][0]
                raise PolicyConflictError(path, first_rule, rule_name)
            index[path] = (rule_name, list(rule.get("allowed_roles", [])))
    return index


def discover_documents(root_dir, department_folders):
    """Return sorted relative paths (e.g. "hr/employee_handbook.md") for
    every .md file found under each department folder."""
    found = []
    for folder in department_folders:
        folder_path = os.path.join(root_dir, folder)
        if not os.path.isdir(folder_path):
            continue
        for name in os.listdir(folder_path):
            if name.lower().endswith(".md"):
                found.append(f"{folder}/{name}")
    return sorted(found)


def resolve_documents(discovered_paths, policy_index, default_rule):
    """Resolve each discovered file path to a ResolvedDocument.

    Files not listed in policy_index fall back to default_rule (fail
    closed) and are flagged with used_default_rule=True.
    """
    resolved = []
    warnings = []

    for path in discovered_paths:
        department = path.split("/", 1)[0]
        filename = os.path.basename(path)

        if path in policy_index:
            rule_name, allowed_roles = policy_index[path]
            used_default_rule = False
        else:
            rule_name = None
            allowed_roles = list(default_rule.get("allowed_roles", []))
            used_default_rule = True
            warnings.append(
                f"'{path}' is not listed in access_policy.json — "
                f"defaulting to allowed_roles={allowed_roles}"
            )

        if not allowed_roles:
            # Materially worse than "restricted" -- zero roles means this
            # document will be unreadable by EVERYONE, including
            # executives, not fail-closed-to-one-role. Worth its own loud
            # warning distinct from the generic default-rule one above,
            # since it's easy to miss "allowed_roles=[]" buried in a list.
            source = f"rule '{rule_name}'" if rule_name else "default_rule"
            warnings.append(
                f"'{path}' resolved to an EMPTY allowed_roles list via {source} — "
                f"this document will be unreadable by ANY role, including executive, "
                f"until access_policy.json is fixed."
            )

        resolved.append(
            ResolvedDocument(
                relative_path=path,
                filename=filename,
                department=department,
                allowed_roles=allowed_roles,
                used_default_rule=used_default_rule,
                matched_rule=rule_name,
            )
        )

    return resolved, warnings


def find_missing_policy_files(discovered_paths, policy_index):
    """Return policy-listed paths that don't correspond to any file on disk."""
    discovered_set = set(discovered_paths)
    return sorted(p for p in policy_index if p not in discovered_set)
