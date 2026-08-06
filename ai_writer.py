import json

from openai import OpenAI

import config

FIELDS = ["student_name", "student_email", "parent_name", "parent_email"]


def _client(api_key: str = None, base_url: str = None) -> OpenAI:
    key = (api_key or config.GROQ_API_KEY).strip()
    if not key:
        raise SystemExit(
            "No Groq API key provided. Enter it in the Settings section of the page (or .env)."
        )
    return OpenAI(api_key=key, base_url=base_url or config.GROQ_BASE_URL)


def _chat_json(client: OpenAI, system: str, user: str, model: str = None) -> dict:
    response = client.chat.completions.create(
        model=model or config.GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.6,
    )
    return json.loads(response.choices[0].message.content)


def _guess_columns(headers: list) -> dict:
    mapping = {field: None for field in FIELDS}
    lowered = {header: header.lower() for header in headers}
    for header in headers:
        h = header.lower()
        if h in ("email", "mail", "email id", "email address"):
            mapping["student_email"] = header
        elif "parent" in h or "guardian" in h or "father" in h or "mother" in h:
            if "email" in h or "mail" in h:
                mapping["parent_email"] = header
            else:
                mapping["parent_name"] = header
        elif "student" in h or "name" in h:
            if "email" in h or "mail" in h:
                mapping["student_email"] = header
            else:
                mapping["student_name"] = header
    return mapping


def map_columns(
    headers: list,
    sample_rows: list,
    offline: bool = False,
    api_key: str = None,
    base_url: str = None,
    model: str = None,
) -> dict:
    if offline:
        return _guess_columns(headers)
    client = _client(api_key, base_url)
    system = (
        "You inspect the columns of a college student roster spreadsheet. "
        "Return ONLY JSON with the exact keys: student_name, student_email, "
        "parent_name, parent_email. Each value must be the exact column header "
        "that contains that data, or null if no column matches. Infer meaning "
        "from names like Name, Student, Roll, Email, Guardian, Parent, etc. "
        "student_email is the student's email; parent_email is the parent's "
        "separate email, "
    )
    user = (
        "Column headers: " + json.dumps(headers) + "\n"
        "First 2 sample rows: " + json.dumps(sample_rows)
    )
    result = _chat_json(client, system, user, model)
    return {field: result.get(field) for field in FIELDS}


def write_email(
    description: str,
    recipient_type: str,
    mapping: dict,
    offline: bool = False,
    api_key: str = None,
    base_url: str = None,
    model: str = None,
) -> dict:
    if offline:
        return {
            "subject": "Message from your professor",
            "body": "Dear {Name},\n\n" + description + "\n\nBest regards,\n" + config.SENDER_NAME,
        }
    client = _client(api_key, base_url)
    system = (
        "You are a professional academic email writer for a college professor. "
        "Write ONE polished, warm, clear plain-text email addressed to a single "
        "recipient. Return ONLY JSON with keys 'subject' and 'body'. "
        "Place the recipient's greeting name exactly as {Name} (no spaces inside "
        "the braces, no other placeholder names). You may optionally use "
        "{StudentName} for the student's full name. "
        "No markdown, no lists of placeholders, just the finished email."
    )
    audience = "the student" if recipient_type == "students" else "the parent of a student"
    user = (
        "Recipient: " + audience + "\n"
        "What the professor wants to say: " + description + "\n\n"
        "Available roster columns: " + json.dumps(mapping)
    )
    return _chat_json(client, system, user, model)
