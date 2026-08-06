import re

import pandas as pd

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def load_roster(path: str) -> pd.DataFrame:
    if str(path).lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    return pd.read_csv(path)


def _cell(row: pd.Series, column) -> str:
    if not column or column not in row.index:
        return ""
    value = row[column]
    if pd.isna(value):
        return ""
    return str(value).strip()


def rows_for_campaign(df: pd.DataFrame, mapping: dict) -> list:
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "student_name": _cell(row, mapping.get("student_name")),
                "student_email": _cell(row, mapping.get("student_email")),
                "parent_name": _cell(row, mapping.get("parent_name")),
                "parent_email": _cell(row, mapping.get("parent_email")),
            }
        )
    return rows


def first_name(full_name: str) -> str:
    return full_name.split()[0] if full_name else ""


def _resolver(name: str, student_name: str, parent_name: str):
    def replace(match: re.Match) -> str:
        token = match.group(1).strip().lower().replace("_", " ").replace("-", " ")
        if token in ("name", "first name", "firstname"):
            return name
        if token in ("student name", "studentname", "student"):
            return student_name
        if token in ("parent name", "parentname", "parent"):
            return parent_name
        return match.group(0)
    return replace


def build_messages(rows: list, campaign: str, subject: str, body: str, cc_parents: bool = False) -> list:
    messages = []
    for row in rows:
        student_name = row["student_name"]
        parent_name = row["parent_name"]
        if campaign == "students":
            name = first_name(student_name)
            email = row["student_email"]
        else:
            name = first_name(parent_name) or "Parent"
            email = row["parent_email"]
        if not email:
            continue
        cc = row["parent_email"] if (campaign == "students" and cc_parents) else ""
        resolver = _resolver(name, student_name, parent_name)
        messages.append(
            {
                "email": email,
                "name": name,
                "cc": cc,
                "subject": _PLACEHOLDER.sub(resolver, subject),
                "body": _PLACEHOLDER.sub(resolver, body),
            }
        )
    return messages


def build_messages_from_grid(headers: list, grid_rows: list, mapping: dict, campaign: str, subject: str, body: str, cc_parents: bool = False) -> list:
    df = pd.DataFrame(grid_rows, columns=headers)
    rows = rows_for_campaign(df, mapping)
    return build_messages(rows, campaign, subject, body, cc_parents=cc_parents)
