"""Compute parent_code for HTS nodes from indent levels."""

from typing import Any


def assign_parent_codes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Walk nodes in file order; track last code at each indent.
    parent_code = hts_code at indent-1.
    """
    stack: dict[int, str] = {}

    for node in nodes:
        indent = int(node.get("indent_level") or 0)
        code = node.get("hts_code", "")

        parent = stack.get(indent - 1, "") if indent > 0 else ""
        node["parent_code"] = parent

        if code:
            stack[indent] = code
            for k in list(stack):
                if k > indent:
                    del stack[k]

    return nodes


def nodes_to_db_rows(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map parsed JSONL nodes to hts_nodes insert dicts."""
    rows = []
    for n in nodes:
        rows.append({
            "hts_code": n["hts_code"],
            "node_type": n.get("node_type", ""),
            "parent_code": n.get("parent_code", ""),
            "description": n.get("description", ""),
            "general_rate": n.get("general_rate", ""),
            "special_rate": n.get("special_rate", ""),
            "other_rate": n.get("other_rate", ""),
            "chapter": n.get("chapter", ""),
            "heading": n.get("heading", ""),
            "subheading": n.get("subheading", ""),
            "unit_of_qty": n.get("unit_of_qty", ""),
            "indent_level": n.get("indent_level"),
        })
    return rows
