import argparse
import json
import os

import ai_writer
import config
import merge as merge_mod
import sender

DRAFT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "draft.json")


def _print_message(message: dict) -> None:
    print("\n--- TO:", message["email"], "---")
    if message.get("cc"):
        print("CC:", message["cc"])
    print(message["subject"])
    print()
    print(message["body"])
    print("---------------------")


def save_draft(payload: dict) -> None:
    try:
        with open(DRAFT_PATH, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        print("\nDraft saved to draft.json.")
    except OSError as exc:
        print("Could not save draft:", exc)


def load_draft():
    if not os.path.exists(DRAFT_PATH):
        return None
    try:
        with open(DRAFT_PATH, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-powered bulk mail merge")
    parser.add_argument("--students", action="store_true", help="send to students")
    parser.add_argument("--parents", action="store_true", help="send to parents")
    parser.add_argument("--file", default="data/roster.csv", help="roster path (.csv/.xlsx)")
    parser.add_argument("--dry-run", action="store_true", help="preview only, send nothing")
    parser.add_argument("--offline", action="store_true", help="skip the AI API (free, no credits needed)")
    parser.add_argument("--cc-parents", action="store_true", help="CC parents on student emails")
    args = parser.parse_args()

    campaign = "parents" if args.parents else "students"

    if args.offline:
        print("\n[OFFLINE MODE] AI API is skipped; using built-in fallback.")

    df = merge_mod.load_roster(args.file)
    headers = list(df.columns)
    sample = df.head(2).to_dict(orient="records")

    print("\nColumns in spreadsheet:", ", ".join(headers))
    print("Asking AI to identify columns...")
    mapping = ai_writer.map_columns(headers, sample, offline=args.offline)
    print("\nAI column mapping:")
    for key, value in mapping.items():
        print(f"  {key:14} <- {value}")
    if input("\nIs the mapping correct? (y/n): ").strip().lower() != "y":
        print("Aborted. Rename the column headers in the spreadsheet and retry.")
        return

    rows = merge_mod.rows_for_campaign(df, mapping)
    print(f"Loaded {len(rows)} row(s) from {args.file}.")

    draft = None
    saved = load_draft()
    if saved and saved.get("campaign") == campaign:
        if input(f"\nSaved draft found for {saved.get('campaign')}. Use it? (y/n): ").strip().lower() == "y":
            draft = {"subject": saved["subject"], "body": saved["body"]}
            print("\n----- Subject -----")
            print(draft["subject"])
            print("\n----- Body -----")
            print(draft["body"])

    if draft is None:
        while True:
            description = input(f"\nDescribe the email to send to {campaign}: ")
            print("Asking AI to write it...")
            draft = ai_writer.write_email(description, campaign, mapping, offline=args.offline)
            save_draft(
                {
                    "campaign": campaign,
                    "description": description,
                    "subject": draft["subject"],
                    "body": draft["body"],
                }
            )
            print("\n----- Subject -----")
            print(draft["subject"])
            print("\n----- Body -----")
            print(draft["body"])
            choice = input("\nUse this email (y), rewrite (r), or abort (n)? ").strip().lower()
            if choice == "y":
                break
            if choice == "n":
                print("Aborted. Nothing sent.")
                return

    messages = merge_mod.build_messages(rows, campaign, draft["subject"], draft["body"], cc_parents=args.cc_parents)
    skipped = len(rows) - len(messages)
    print(f"\nRecipients with a valid email: {len(messages)}" + (f" ({skipped} row(s) skipped)" if skipped else ""))
    for message in messages[:2]:
        _print_message(message)
    if len(messages) > 2 and input(f"\nShow all {len(messages)} previews? (y/n): ").strip().lower() == "y":
        for message in messages[2:]:
            _print_message(message)

    if args.dry_run:
        print(f"\n[DRY RUN] Would send {len(messages)} email(s). Nothing was sent.")
        return

    if not messages:
        print("Nothing to send.")
        return

    if input(f"\nSend {len(messages)} email(s) for real? (y/n): ").strip().lower() != "y":
        print("Aborted. Nothing sent.")
        return

    sent, failed = sender.send_emails(messages)
    print(f"\nDone. Sent: {len(sent)}  Failed: {len(failed)}")
    for email, error in failed:
        print("  failed:", email, "-", error)


if __name__ == "__main__":
    main()
