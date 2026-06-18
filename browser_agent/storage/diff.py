"""
storage/diff.py — Compares two ApplicationModel versions.
"""
from schema import ApplicationModel


def diff_models(old: ApplicationModel, new: ApplicationModel) -> dict:
    """
    Compare two ApplicationModel versions and return a structured diff.
    
    Matches pages by url_pattern, elements by semantic_label, flows by name.
    
    Returns:
        {
            "new_pages": [...],
            "removed_pages": [...],
            "new_elements": [{"page": ..., "label": ...}],
            "removed_elements": [...],
            "changed_elements": [{"label": ..., "changes": [...]}],
            "new_flows": [...],
            "removed_flows": [...],
            "changed_flows": [...]
        }
    """
    result = {
        "new_pages": [],
        "removed_pages": [],
        "new_elements": [],
        "removed_elements": [],
        "changed_elements": [],
        "new_flows": [],
        "removed_flows": [],
        "changed_flows": []
    }

    # ─── Pages ───────────────────────────────────────────────────────
    old_pages = {p.url_pattern: p for p in old.pages}
    new_pages = {p.url_pattern: p for p in new.pages}

    result["new_pages"] = [
        {"url_pattern": p, "title": new_pages[p].title}
        for p in new_pages if p not in old_pages
    ]
    result["removed_pages"] = [
        {"url_pattern": p, "title": old_pages[p].title}
        for p in old_pages if p not in new_pages
    ]

    # ─── Elements ────────────────────────────────────────────────────
    old_elements = {e.semantic_label: e for e in old.elements}
    new_elements = {e.semantic_label: e for e in new.elements}

    for label, elem in new_elements.items():
        if label not in old_elements:
            # Find page name for context
            page = next(
                (p for p in new.pages if p.id == elem.page_id),
                None
            )
            result["new_elements"].append({
                "page": page.url_pattern if page else "unknown",
                "label": label,
                "type": elem.element_type
            })

    for label, elem in old_elements.items():
        if label not in new_elements:
            result["removed_elements"].append({
                "label": label,
                "type": elem.element_type
            })

    # Check changed elements (same label but different properties)
    for label in old_elements:
        if label not in new_elements:
            continue
        old_elem = old_elements[label]
        new_elem = new_elements[label]
        changes = []

        if old_elem.element_type != new_elem.element_type:
            changes.append(f"type: {old_elem.element_type} → {new_elem.element_type}")

        old_rules = {vr.rule for vr in old_elem.validation_rules}
        new_rules = {vr.rule for vr in new_elem.validation_rules}
        if old_rules != new_rules:
            added = new_rules - old_rules
            removed_rules = old_rules - new_rules
            if added:
                changes.append(f"validation rules added: {', '.join(added)}")
            if removed_rules:
                changes.append(f"validation rules removed: {', '.join(removed_rules)}")

        if changes:
            result["changed_elements"].append({
                "label": label,
                "changes": changes
            })

    # ─── Flows ───────────────────────────────────────────────────────
    old_flows = {f.name: f for f in old.flows}
    new_flows = {f.name: f for f in new.flows}

    result["new_flows"] = [
        {"name": n, "description": new_flows[n].description}
        for n in new_flows if n not in old_flows
    ]
    result["removed_flows"] = [
        {"name": n, "description": old_flows[n].description}
        for n in old_flows if n not in new_flows
    ]

    for name in old_flows:
        if name not in new_flows:
            continue
        old_flow = old_flows[name]
        new_flow = new_flows[name]
        changes = []

        if old_flow.start_url != new_flow.start_url:
            changes.append(f"start URL: {old_flow.start_url} → {new_flow.start_url}")

        if len(old_flow.steps) != len(new_flow.steps):
            changes.append(f"step count: {len(old_flow.steps)} → {len(new_flow.steps)}")

        if changes:
            result["changed_flows"].append({
                "name": name,
                "changes": changes
            })

    return result
