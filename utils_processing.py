from typing import Any, Dict, List, Tuple


def filter_columns_excluding_points(columns: List[str]) -> List[str]:
    return [c for c in columns if 'point' not in c.lower()]


def format_table(records: List[Dict[str, Any]], max_width: int = 20) -> str:
    if not records:
        return ""
    # Build column set from first record
    columns = list(records[0].keys())
    columns = filter_columns_excluding_points(columns)
    if not columns:
        return ""

    # Header
    header = " | ".join([f"{col[:max_width]:<{max_width}}" for col in columns])
    sep = "-" * len(header)
    lines = [header, sep]

    # Rows (skip rows where remaining_issues is null/empty if present)
    remaining_key = None
    for c in columns:
        if 'remaining_issues' in c.lower():
            remaining_key = c
            break

    for rec in records:
        if remaining_key is not None:
            val = rec.get(remaining_key)
            if val is None or str(val).strip().lower() in ('', 'null'):
                continue
        row_values = []
        for col in columns:
            v = rec.get(col)
            row_values.append(f"{str(v)[:max_width] if v is not None else 'NULL':<{max_width}}")
        lines.append(" | ".join(row_values))

    return "\n".join(lines)


def clean_recommendation_text(text: str) -> str:
    import re
    s = re.sub(r'^\d+\.?\s*', '', text.strip())
    s = s.lstrip('*-•◦').strip()
    return ' '.join(s.split())


def extract_recommendations(llm_text: str, max_count: int = 2) -> List[str]:
    if not llm_text:
        return []
    lines = [ln.strip() for ln in llm_text.split('\n') if ln.strip()]
    items: List[str] = []
    current = ""
    for ln in lines:
        starts = ln.startswith(tuple([f"{i}." for i in range(1, 10)])) or ln.startswith(('*', '-', '•', '◦'))
        if starts:
            if current.strip():
                items.append(current.strip())
            current = ln
        else:
            if current:
                current += " " + ln
            else:
                current = ln
    if current.strip():
        items.append(current.strip())

    cleaned = []
    seen = set()
    for it in items:
        c = clean_recommendation_text(it)
        if c and c not in seen:
            cleaned.append(c)
            seen.add(c)
        if len(cleaned) >= max_count:
            break
    return cleaned


