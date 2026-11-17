from typing import Any, Dict, Optional, Tuple


def _resolve_attribute(
    name: str,
    subject_attributes: Dict[str, Any],
    environment: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Any]:
    """Retrieve attribute value from subject_attributes or environment context.

    Supports both flat key-value attributes and nested credential attribute objects.
    """
    clean_name = name.strip().lower()

    # 1. Check subject attributes
    if clean_name in subject_attributes:
        val = subject_attributes[clean_name]
        if isinstance(val, dict) and "value" in val:
            return True, val["value"]
        return True, val

    # 2. Check environment context
    if environment and clean_name in environment:
        val = environment[clean_name]
        if isinstance(val, dict) and "value" in val:
            return True, val["value"]
        return True, val

    return False, None


def _eval_node(
    node: Any,
    subject_attributes: Dict[str, Any],
    environment: Optional[Dict[str, Any]],
) -> bool:
    if not isinstance(node, dict):
        return False

    op = node.get("op")
    if not isinstance(op, str):
        return False
    op = op.strip().lower()

    # 1. Logical: all
    if op == "all":
        rules = node.get("rules")
        if not isinstance(rules, list) or len(rules) == 0:
            return False
        return all(_eval_node(r, subject_attributes, environment) for r in rules)

    # 2. Logical: any
    if op == "any":
        rules = node.get("rules")
        if not isinstance(rules, list) or len(rules) == 0:
            return False
        return any(_eval_node(r, subject_attributes, environment) for r in rules)

    # 3. Logical: not
    if op == "not":
        rule = node.get("rule")
        if not isinstance(rule, dict):
            return False
        return not _eval_node(rule, subject_attributes, environment)

    # 4. Boolean literal
    if op == "bool":
        return bool(node.get("value", False))

    # All comparison operators require an attribute
    attr_name = node.get("attribute")
    if not isinstance(attr_name, str):
        return False

    found, attr_val = _resolve_attribute(attr_name, subject_attributes, environment)
    if not found:
        # Default-deny: subject missing the attribute never passes comparison
        return False

    # 5. Comparison: eq
    if op == "eq":
        target = node.get("value")
        return attr_val == target

    # 6. Comparison: neq
    if op == "neq":
        target = node.get("value")
        return attr_val != target

    # 7. Set / List membership: in
    if op == "in":
        values = node.get("values")
        if not isinstance(values, (list, tuple, set)):
            return False
        return attr_val in values

    # 8. Collection contains element: contains
    if op == "contains":
        target = node.get("value")
        if isinstance(attr_val, (list, tuple, set)):
            return target in attr_val
        if isinstance(attr_val, str) and isinstance(target, str):
            return target in attr_val
        return False

    # 9. Comparison: gte
    if op == "gte":
        target = node.get("value")
        if isinstance(attr_val, bool) or isinstance(target, bool):
            return False
        if not isinstance(attr_val, (int, float)) or not isinstance(target, (int, float)):
            return False
        return attr_val >= target

    # 10. Comparison: lte
    if op == "lte":
        target = node.get("value")
        if isinstance(attr_val, bool) or isinstance(target, bool):
            return False
        if not isinstance(attr_val, (int, float)) or not isinstance(target, (int, float)):
            return False
        return attr_val <= target

    # Default-deny on unknown operator
    return False


def evaluate_policy(
    ast: Dict[str, Any],
    subject_attributes: Dict[str, Any],
    environment: Optional[Dict[str, Any]] = None,
) -> bool:
    """Evaluate a JSON policy AST against subject attributes and environment context.

    Operates strictly under a DEFAULT-DENY paradigm:
    Any error, missing attribute, malformed node, or unexpected type evaluates to False (Deny).
    Never uses eval(), exec(), or dynamic code.

    Returns:
        bool: True if access is permitted, False otherwise.
    """
    try:
        return _eval_node(ast, subject_attributes, environment)
    except Exception:
        # Fail-safe default deny
        return False
