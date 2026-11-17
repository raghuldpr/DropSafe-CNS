import pytest

from app.core.exceptions import ValidationException
from app.policies.evaluator import evaluate_policy
from app.policies.validator import validate_policy_ast


# ==============================================================================
# AST Validator Tests
# ==============================================================================

def test_validate_valid_ast():
    """Verify that a well-formed policy AST passes validation."""
    ast = {
        "op": "all",
        "rules": [
            {"op": "eq", "attribute": "department", "value": "engineering"},
            {"op": "gte", "attribute": "clearance_level", "value": 2},
            {"op": "in", "attribute": "role", "values": ["admin", "developer"]},
            {"op": "contains", "attribute": "projects", "value": "apollo"},
            {"op": "bool", "value": True},
            {
                "op": "not",
                "rule": {"op": "eq", "attribute": "is_contractor", "value": True},
            },
        ],
    }
    # Should not raise
    validate_policy_ast(ast)


def test_validate_non_dict_ast():
    """Verify non-dictionary AST is rejected."""
    with pytest.raises(ValidationException) as exc_info:
        validate_policy_ast(["not", "a", "dict"])  # type: ignore
    assert exc_info.value.code == "INVALID_POLICY_AST"


def test_validate_missing_or_invalid_op():
    """Verify missing or unknown operator raises ValidationException."""
    with pytest.raises(ValidationException) as exc1:
        validate_policy_ast({"attribute": "department", "value": "engineering"})
    assert exc1.value.code == "INVALID_POLICY_AST"

    with pytest.raises(ValidationException) as exc2:
        validate_policy_ast({"op": "unknown_operator", "attribute": "department", "value": "eng"})
    assert exc2.value.code == "INVALID_POLICY_AST"


def test_validate_logical_operators_requirements():
    """Verify 'all', 'any', and 'not' require valid sub-rules."""
    # 'all' with empty rules
    with pytest.raises(ValidationException) as exc1:
        validate_policy_ast({"op": "all", "rules": []})
    assert exc1.value.code == "INVALID_POLICY_AST"

    # 'any' with non-list rules
    with pytest.raises(ValidationException) as exc2:
        validate_policy_ast({"op": "any", "rules": "not-a-list"})  # type: ignore
    assert exc2.value.code == "INVALID_POLICY_AST"

    # 'not' without a rule object
    with pytest.raises(ValidationException) as exc3:
        validate_policy_ast({"op": "not"})
    assert exc3.value.code == "INVALID_POLICY_AST"


def test_validate_comparison_operators_requirements():
    """Verify comparison operators require valid attributes and operand values."""
    # Missing attribute
    with pytest.raises(ValidationException):
        validate_policy_ast({"op": "eq", "value": "engineering"})

    # Invalid attribute naming
    with pytest.raises(ValidationException):
        validate_policy_ast({"op": "eq", "attribute": "Invalid-Attr-Name!", "value": "val"})

    # 'in' with empty or non-list values
    with pytest.raises(ValidationException):
        validate_policy_ast({"op": "in", "attribute": "department", "values": []})

    # 'gte' with non-numeric value
    with pytest.raises(ValidationException):
        validate_policy_ast({"op": "gte", "attribute": "clearance_level", "value": "high"})


def test_validate_nesting_depth_limit():
    """Verify AST exceeding maximum nesting depth (5) is rejected."""
    # Construct an AST with depth 6
    deep_ast = {"op": "bool", "value": True}
    for _ in range(6):
        deep_ast = {"op": "all", "rules": [deep_ast]}

    with pytest.raises(ValidationException) as exc_info:
        validate_policy_ast(deep_ast, max_depth=5)
    assert exc_info.value.code == "INVALID_POLICY_AST"
    assert "depth" in exc_info.value.message.lower()


def test_validate_node_count_limit():
    """Verify AST exceeding maximum node count is rejected."""
    # 51 nodes in a flat 'all' rule
    rules = [{"op": "bool", "value": True} for _ in range(50)]
    large_ast = {"op": "all", "rules": rules}  # 1 root + 50 children = 51 nodes

    with pytest.raises(ValidationException) as exc_info:
        validate_policy_ast(large_ast, max_nodes=50)
    assert exc_info.value.code == "INVALID_POLICY_AST"
    assert "node count" in exc_info.value.message.lower()


def test_validate_allowed_attributes_catalog():
    """Verify validation strictly rejects attributes not present in the allowed catalog."""
    catalog = {"department", "clearance_level", "is_contractor"}

    valid_ast = {"op": "eq", "attribute": "department", "value": "engineering"}
    validate_policy_ast(valid_ast, allowed_attributes=catalog)

    disallowed_ast = {"op": "eq", "attribute": "unapproved_attribute", "value": "val"}
    with pytest.raises(ValidationException) as exc_info:
        validate_policy_ast(disallowed_ast, allowed_attributes=catalog)
    assert exc_info.value.code == "DISALLOWED_POLICY_ATTRIBUTE"


# ==============================================================================
# Policy Evaluator Tests
# ==============================================================================

def test_eval_bool_literals():
    """Verify boolean literal operators evaluate unconditionally."""
    assert evaluate_policy({"op": "bool", "value": True}, {}) is True
    assert evaluate_policy({"op": "bool", "value": False}, {}) is False


def test_eval_eq_and_neq_operators():
    """Verify eq and neq operators, including default-deny on missing attributes."""
    # 1. Matching eq
    assert evaluate_policy(
        {"op": "eq", "attribute": "department", "value": "engineering"},
        {"department": "engineering"},
    ) is True

    # 2. Non-matching eq
    assert evaluate_policy(
        {"op": "eq", "attribute": "department", "value": "finance"},
        {"department": "engineering"},
    ) is False

    # 3. Missing attribute on eq -> Default Deny (False)
    assert evaluate_policy(
        {"op": "eq", "attribute": "department", "value": "engineering"},
        {},
    ) is False

    # 4. Matching neq
    assert evaluate_policy(
        {"op": "neq", "attribute": "department", "value": "finance"},
        {"department": "engineering"},
    ) is True

    # 5. Non-matching neq (values are equal)
    assert evaluate_policy(
        {"op": "neq", "attribute": "department", "value": "engineering"},
        {"department": "engineering"},
    ) is False

    # 6. Missing attribute on neq -> Default Deny (False)
    assert evaluate_policy(
        {"op": "neq", "attribute": "department", "value": "finance"},
        {},
    ) is False


def test_eval_in_and_contains_operators():
    """Verify in and contains operators for list and string_set membership."""
    # 1. 'in' operator: subject attribute in target list
    assert evaluate_policy(
        {"op": "in", "attribute": "department", "values": ["engineering", "security"]},
        {"department": "security"},
    ) is True

    assert evaluate_policy(
        {"op": "in", "attribute": "department", "values": ["engineering", "security"]},
        {"department": "marketing"},
    ) is False

    # Missing attribute on 'in' -> False
    assert evaluate_policy(
        {"op": "in", "attribute": "department", "values": ["engineering"]},
        {},
    ) is False

    # 2. 'contains' operator: subject list/set attribute contains target value
    assert evaluate_policy(
        {"op": "contains", "attribute": "project_tags", "value": "civicos"},
        {"project_tags": ["civicos", "dropsafe"]},
    ) is True

    assert evaluate_policy(
        {"op": "contains", "attribute": "project_tags", "value": "secret_project"},
        {"project_tags": ["civicos", "dropsafe"]},
    ) is False

    # Missing attribute on 'contains' -> False
    assert evaluate_policy(
        {"op": "contains", "attribute": "project_tags", "value": "civicos"},
        {},
    ) is False


def test_eval_numeric_gte_and_lte_operators():
    """Verify numeric comparisons and strict type-safety."""
    # 1. gte
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 4},
    ) is True
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 3},
    ) is True
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 2},
    ) is False

    # 2. lte
    assert evaluate_policy(
        {"op": "lte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 2},
    ) is True
    assert evaluate_policy(
        {"op": "lte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 3},
    ) is True
    assert evaluate_policy(
        {"op": "lte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": 4},
    ) is False

    # 3. Missing attribute on numeric comparison -> False
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 1},
        {},
    ) is False

    # 4. Type mismatch (comparing string to int) -> False
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 3},
        {"clearance_level": "top_secret"},
    ) is False

    # 5. Boolean value passed for numeric attribute -> False
    assert evaluate_policy(
        {"op": "gte", "attribute": "clearance_level", "value": 1},
        {"clearance_level": True},
    ) is False


def test_eval_logical_all_any_not():
    """Verify logical composition and short-circuiting."""
    rule_dept = {"op": "eq", "attribute": "department", "value": "engineering"}
    rule_clearance = {"op": "gte", "attribute": "clearance_level", "value": 3}
    rule_contractor = {"op": "eq", "attribute": "is_contractor", "value": True}

    # 1. 'all' operator
    all_rule = {"op": "all", "rules": [rule_dept, rule_clearance]}
    assert evaluate_policy(all_rule, {"department": "engineering", "clearance_level": 4}) is True
    assert evaluate_policy(all_rule, {"department": "engineering", "clearance_level": 2}) is False

    # 2. 'any' operator
    any_rule = {"op": "any", "rules": [rule_dept, rule_clearance]}
    assert evaluate_policy(any_rule, {"department": "marketing", "clearance_level": 4}) is True
    assert evaluate_policy(any_rule, {"department": "marketing", "clearance_level": 1}) is False

    # 3. 'not' operator
    not_rule = {"op": "not", "rule": rule_contractor}
    assert evaluate_policy(not_rule, {"is_contractor": False}) is True
    assert evaluate_policy(not_rule, {"is_contractor": True}) is False


def test_eval_complex_real_world_abac_policy():
    """Verify a multi-clause production ABAC policy:
    (department == 'engineering' OR department == 'security')
    AND clearance_level >= 3
    AND contains(projects, 'apollo')
    AND NOT is_contractor
    """
    policy = {
        "op": "all",
        "rules": [
            {
                "op": "any",
                "rules": [
                    {"op": "eq", "attribute": "department", "value": "engineering"},
                    {"op": "eq", "attribute": "department", "value": "security"},
                ],
            },
            {"op": "gte", "attribute": "clearance_level", "value": 3},
            {"op": "contains", "attribute": "projects", "value": "apollo"},
            {
                "op": "not",
                "rule": {"op": "eq", "attribute": "is_contractor", "value": True},
            },
        ],
    }

    # 1. Permitted subject
    subject_pass = {
        "department": "engineering",
        "clearance_level": 4,
        "projects": ["apollo", "gemini"],
        "is_contractor": False,
    }
    assert evaluate_policy(policy, subject_pass) is True

    # 2. Contractor denied
    subject_contractor = {
        "department": "engineering",
        "clearance_level": 4,
        "projects": ["apollo"],
        "is_contractor": True,
    }
    assert evaluate_policy(policy, subject_contractor) is False

    # 3. Low clearance denied
    subject_low_clearance = {
        "department": "security",
        "clearance_level": 2,
        "projects": ["apollo"],
        "is_contractor": False,
    }
    assert evaluate_policy(policy, subject_low_clearance) is False

    # 4. Wrong project denied
    subject_wrong_project = {
        "department": "engineering",
        "clearance_level": 5,
        "projects": ["titan"],
        "is_contractor": False,
    }
    assert evaluate_policy(policy, subject_wrong_project) is False


def test_eval_credential_attribute_dict_and_environment():
    """Verify evaluation handles Step 4 credential payload format and environment context."""
    # Credential attributes dictionary format with nested 'value'
    credential_attributes = {
        "department": {
            "value": "engineering",
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": None,
        },
        "clearance_level": {
            "value": 3,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_until": None,
        },
    }

    # Policy checks subject clearance AND environment network_zone
    policy = {
        "op": "all",
        "rules": [
            {"op": "gte", "attribute": "clearance_level", "value": 3},
            {"op": "eq", "attribute": "network_zone", "value": "corporate_vpn"},
        ],
    }

    # Valid with corporate_vpn
    env_corp = {"network_zone": "corporate_vpn"}
    assert evaluate_policy(policy, credential_attributes, environment=env_corp) is True

    # Denied with external network
    env_public = {"network_zone": "public_wifi"}
    assert evaluate_policy(policy, credential_attributes, environment=env_public) is False
