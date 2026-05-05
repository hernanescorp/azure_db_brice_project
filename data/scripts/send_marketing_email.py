import argparse
import os
import time
from pathlib import Path

import pyodbc


try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    with dotenv_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")
else:
    load_dotenv_file(ROOT_DIR / ".env")


SQL_SERVER = os.getenv("SQL_SERVER", "graxiano.database.windows.net")
SQL_DATABASE = os.getenv("SQL_DATABASE", "free-sql-db-3910009")
SQL_USER = os.getenv("SQL_USER")
SQL_PASSWORD = os.getenv("SQL_PASSWORD")
SQL_DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")

ACS_CONNECTION_STRING = os.getenv("ACS_CONNECTION_STRING") or os.getenv("AZURE_EMAIL_CONNECTION_STRING")
ACS_SENDER_ADDRESS = os.getenv("ACS_SENDER_ADDRESS") or os.getenv("EMAIL_FROM")


def find_available_driver(preferred: str) -> str:
    available = [driver for driver in pyodbc.drivers() if driver]
    fallback = [preferred, "ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"]
    for driver_name in fallback:
        if driver_name in available:
            return driver_name
    if available:
        return available[-1]
    raise RuntimeError("No ODBC drivers are installed for SQL Server.")


def build_sql_connection() -> pyodbc.Connection:
    if not SQL_USER or not SQL_PASSWORD:
        raise ValueError("SQL_USER and SQL_PASSWORD must be defined in .env or environment variables.")

    driver_name = find_available_driver(SQL_DRIVER)
    if driver_name != SQL_DRIVER:
        print(f"Driver solicitado '{SQL_DRIVER}' no disponible, usando '{driver_name}' en su lugar.")

    conn_str = (
        f"DRIVER={{{driver_name}}};"
        f"SERVER={SQL_SERVER};DATABASE={SQL_DATABASE};"
        f"UID={SQL_USER};PWD={SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=yes;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def get_contacts(limit: int | None = None, include_without_consent: bool = False) -> list[dict[str, str]]:
    consent_filter = "" if include_without_consent else "AND consent_marketing = 1"
    sql = """
        SELECT
            contact_id,
            first_name,
            last_name,
            email
        FROM brice.marketing_contacts
        WHERE email IS NOT NULL
          AND LTRIM(RTRIM(email)) <> ''
          AND unsubscribed = 0
          {consent_filter}
        ORDER BY contact_id
    """.format(consent_filter=consent_filter)

    with build_sql_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

    contacts = [
        {
            "contact_id": row.contact_id,
            "first_name": row.first_name or "",
            "last_name": row.last_name or "",
            "email": row.email.strip().lower(),
        }
        for row in rows
        if row.email
    ]

    if limit is not None:
        return contacts[:limit]
    return contacts


def build_test_contact(email: str) -> dict[str, str]:
    return {
        "contact_id": "test",
        "first_name": "Hernan",
        "last_name": "",
        "email": email.strip().lower(),
    }


def render_template(template: str, contact: dict[str, str]) -> str:
    full_name = f"{contact['first_name']} {contact['last_name']}".strip()
    return (
        template.replace("{{first_name}}", contact["first_name"])
        .replace("{{last_name}}", contact["last_name"])
        .replace("{{full_name}}", full_name)
        .replace("{{email}}", contact["email"])
    )


def read_text_arg(value: str) -> str:
    path = Path(value)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return value


def send_email(
    email_client,
    recipient: str,
    subject: str,
    html_body: str,
    plain_text: str | None,
) -> str:
    message = {
        "senderAddress": ACS_SENDER_ADDRESS,
        "recipients": {"to": [{"address": recipient}]},
        "content": {
            "subject": subject,
            "html": html_body,
        },
    }

    if plain_text:
        message["content"]["plainText"] = plain_text

    poller = email_client.begin_send(message)
    result = poller.result()
    return str(result.get("id", ""))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read emails from brice.marketing_contacts and send a campaign with Azure Communication Services Email."
    )
    parser.add_argument("--subject", required=True, help="Email subject.")
    parser.add_argument("--html", required=True, help="HTML body text or path to an HTML file.")
    parser.add_argument("--text", help="Plain-text body text or path to a text file.")
    parser.add_argument("--test-recipient", help="Send only to this email address instead of reading contacts from SQL.")
    parser.add_argument("--limit", type=int, help="Maximum number of contacts to process.")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay in seconds between sends.")
    parser.add_argument(
        "--include-without-consent",
        action="store_true",
        help="Include contacts where consent_marketing is 0. Use only for lawful/test scenarios.",
    )
    parser.add_argument("--send", action="store_true", help="Actually send emails. Without this flag it only previews.")
    args = parser.parse_args()

    if args.test_recipient:
        contacts = [build_test_contact(args.test_recipient)]
    else:
        contacts = get_contacts(args.limit, args.include_without_consent)

    print(f"Contactos encontrados para enviar: {len(contacts)}")
    if args.include_without_consent:
        print("Aviso: se estan incluyendo contactos sin consent_marketing=1.")

    if not contacts:
        return

    html_template = read_text_arg(args.html)
    text_template = read_text_arg(args.text) if args.text else None

    if not args.send:
        print("Modo prueba: no se enviara ningun correo. Usa --send para enviar.")
        for contact in contacts[:10]:
            print(f"- {contact['contact_id']}: {contact['email']}")
        if len(contacts) > 10:
            print(f"... y {len(contacts) - 10} mas")
        return

    if not ACS_CONNECTION_STRING or not ACS_SENDER_ADDRESS:
        raise ValueError(
            "Define ACS_CONNECTION_STRING/ACS_SENDER_ADDRESS or "
            "AZURE_EMAIL_CONNECTION_STRING/EMAIL_FROM in .env or environment variables."
        )

    from azure.communication.email import EmailClient

    email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)
    sent = 0
    failed = 0

    for contact in contacts:
        html_body = render_template(html_template, contact)
        plain_text = render_template(text_template, contact) if text_template else None

        try:
            message_id = send_email(email_client, contact["email"], args.subject, html_body, plain_text)
            sent += 1
            print(f"OK {contact['email']} message_id={message_id}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {contact['email']}: {exc}")

        if args.delay > 0:
            time.sleep(args.delay)

    print(f"Finalizado. Enviados={sent}, fallidos={failed}")


if __name__ == "__main__":
    main()
