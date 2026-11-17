import re
from typing import Any, Dict, List, Optional, Set

from app.core.exceptions import ValidationException

_IDENTIFIER_REGEX = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_SUPPORTED_OPERATORS = {
    "all",
    "any",
    "not",
    "eq",
    "neq",
    "in",
    "contains",
    "gte",
    "lte",
    "bool",
}


def _validate_node(
    node: Any,
    current_depth: int,
    node_count: List[int],
    max_depth: int,
    max_nodes: int,
    allowed_attributes: Optional[Set[str]],
) -> None:
    if not isinstance(node, dict):
        raise ValidationException(
            message="Policy node must be a JSON object (dictionary)",
            code="INVALID_POLICY_AST",
        )

    node_count[0] += 1
    if node_count[0] > max_nodes:
        raise ValidationException(
            message=f"Policy AST exceeds maximum allowed rule node count of {max_nodes}",
            code="INVALID_POLICY_AST",
        )

    if current_depth > max_depth:
        raise ValidationException(
            message=f"Policy AST exceeds maximum allowed nesting depth of {max_depth}",
            code="INVALID_POLICY_AST",
        )

    op = node.get("op")
    if not isinstance(op, str) or not op.strip():
        raise ValidationException(
            message="Every policy node must contain a non-empty string 'op' operator",
            code="INVALID_POLICY_AST",
        )

    op = op.strip().lower()
    if op not in _SUPPORTED_OPERATORS:
        raise ValidationException(
            message=f"Unsupported policy operator '{op}'. Supported operators: {sorted(_SUPPORTED_OPERATORS)}",
            code="INVALID_POLICY_AST",
        )

    # Logical Operators
    if op in ("all", "any"):
        rules = node.get("rules")
        if not isinstance(rules, list) or len(rules) == 0:
            raise ValidationException(
                message=f"Logical operator '{op}' requires a non-empty list of 'rules'",
                code="INVALID_POLICY_AST",
            )
        for sub_rule in rules:
            _validate_node(
                sub_rule,
                current_depth=current_depth + 1,
                node_count=node_count,
                max_depth=max_depth,
                max_nodes=max_nodes,
                allowed_attributes=allowed_attributes,
            )

    elif op == "not":
        rule = node.get("rule")
        if not isinstance(rule, dict):
            raise ValidationException(
                message="Logical operator 'not' requires a single nested 'rule' object",
                code="INVALID_POLICY_AST",
            )
        _validate_node(
            rule,
            current_depth=current_depth + 1,
            node_count=node_count,
            max_depth=max_depth,
            max_nodes=max_nodes,
            allowed_attributes=allowed_attributes,
        )

    elif op == "bool":
        if "value" not in node or not isinstance(node["value"], bool):
            raise ValidationException(
                message="Boolean literal operator 'bool' requires a boolean 'value' (true or false)",
                code="INVALID_POLICY_AST",
            )

    # Comparison / Attribute Operators
    else:
        attr = node.get("attribute")
        if not isinstance(attr, str) or not _IDENTIFIER_REGEX.match(attr.strip().lower()):
            raise ValidationException(
                message=f"Operator '{op}' requires a valid lowercase snake_case 'attribute' name",
                code="INVALID_POLICY_AST",
            )
        attr = attr.strip().lower()

        if allowed_attributes is not None and attr not in allowed_attributes:
            raise ValidationException(
                message=f"Attribute '{attr}' in policy AST is not recognized in attribute catalog",
                code="DISALLOWED_POLICY_ATTRIBUTE",
            )

        if op in ("eq", "neq"):
            if "value" not in node or node["value"] is None:
                raise ValidationException(
                    message=f"Operator '{op}' requires a 'value' to compare against",
                    code="INVALID_POLICY_AST",
                )

        elif op == "in":
            values = node.get("values")
            if not isinstance(values, list) or len(values) == 0:
                raise ValidationException(
                    message="Operator 'in' requires a non-empty list of 'values'",
                    code="INVALID_POLICY_AST",
                )

        elif op == "contains":
            if "value" not in node or node["value"] is None:
                raise ValidationException(
                    message="Operator 'contains' requires a non-empty 'value' item to check",
                    code="INVALID_POLICY_AST",
                )

        elif op in ("gte", "lte"):
            val = node.get("value")
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValidationException(
                    message=f"Numeric comparison operator '{op}' requires a numeric (int/float) 'value'",
                    code="INVALID_POLICY_AST",
                )


def validate_policy_ast(
    ast: Dict[str, Any],
    allowed_attributes: Optional[Set[str]] = None,
    max_depth: int = 5,
    max_nodes: int = 50,
) -> None:
    """Recursively validate policy AST syntax, allowed operators, limits, and attribute names.

    Raises:
        ValidationException: if AST is malformed, exceeds depth/node limits, or references disallowed attributes.
    """
    if not isinstance(ast, dict):
        raise ValidationException(
            message="Policy AST must be a JSON object (dictionary)",
            code="INVALID_POLICY_AST",
        )

    node_count = [0]
    _validate_node(
        node=ast,
        current_depth=1,
        node_count=node_count,
        max_depth=max_depth,
        max_nodes=max_nodes,
        allowed_attributes=allowed_attributes,
    )
