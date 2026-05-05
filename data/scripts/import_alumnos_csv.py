import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyodbc

def load_dotenv_file(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    with dotenv_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if load_dotenv:
    load_dotenv(ROOT_DIR / ".env")
else:
    load_dotenv_file(ROOT_DIR / ".env")

SERVER = os.getenv("SQL_SERVER", "graxiano.database.windows.net")
DATABASE = os.getenv("SQL_DATABASE", "free-sql-db-3910009")
USERNAME = os.getenv("SQL_USER")
PASSWORD = os.getenv("SQL_PASSWORD")
DRIVER = os.getenv("SQL_DRIVER", "ODBC Driver 18 for SQL Server")
CSV_PATH = Path(os.getenv("CSV_PATH", "data/sample/alumnos.csv"))
if not CSV_PATH.is_absolute():
    CSV_PATH = ROOT_DIR / CSV_PATH

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\d{9}$")


def split_name(full_name: str) -> tuple[str, str]:
    full_name = full_name.strip()
    if not full_name:
        return "", ""

    parts = full_name.split()
    if len(parts) == 1:
        return parts[0], ""

    return " ".join(parts[:-1]), parts[-1]


def normalize_phone(phone: str) -> str:
    return re.sub(r"[^0-9]", "", str(phone or "")).strip()


def find_available_driver(preferred: str) -> str:
    available = [driver for driver in pyodbc.drivers() if driver]
    fallback = [preferred, "ODBC Driver 17 for SQL Server", "SQL Server", "FreeTDS"]
    for driver_name in fallback:
        if driver_name in available:
            return driver_name
    if available:
        return available[-1]
    raise RuntimeError(
        "No ODBC drivers are installed. Instala un driver de SQL Server como 'ODBC Driver 18 for SQL Server'."
    )


def build_connection() -> pyodbc.Connection:
    if not USERNAME or not PASSWORD:
        raise ValueError(
            "SQL_USER and SQL_PASSWORD must be defined in environment variables or .env"
        )

    driver_name = find_available_driver(DRIVER)
    if driver_name != DRIVER:
        print(f"Driver solicitado '{DRIVER}' no disponible, usando '{driver_name}' en su lugar.")

    conn_str = (
        f"DRIVER={{{driver_name}}};"
        f"SERVER={SERVER};DATABASE={DATABASE};"
        f"UID={USERNAME};PWD={PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def get_existing_emails(connection: pyodbc.Connection) -> set[str]:
    cursor = connection.cursor()
    cursor.execute("SELECT email FROM brice.marketing_contacts")
    return {row.email.strip().lower() for row in cursor.fetchall() if row.email}


def insert_rows(connection: pyodbc.Connection, df: pd.DataFrame) -> int:
    insert_sql = (
        "INSERT INTO brice.marketing_contacts "
        "(first_name, last_name, email, phone, company, consent_marketing, consent_date, consent_source, unsubscribed, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    rows = [
        (
            row.first_name,
            row.last_name,
            row.email,
            row.phone,
            row.company,
            int(row.consent_marketing),
            row.consent_date,
            row.consent_source,
            int(row.unsubscribed),
            row.created_at,
        )
        for row in df.itertuples(index=False)
    ]

    if not rows:
        return 0

    cursor = connection.cursor()
    cursor.fast_executemany = True
    cursor.executemany(insert_sql, rows)
    connection.commit()
    return len(rows)


def main() -> None:
    print(f"Usando CSV_PATH={CSV_PATH}")
    print(f"Usando SQL_SERVER={SERVER}, SQL_DATABASE={DATABASE}, SQL_USER={USERNAME}")
    df = pd.read_csv(CSV_PATH)

    df["Nombre"] = df["Nombre"].astype(str).str.strip()
    df["Mail"] = df["Mail"].astype(str).str.strip().str.lower()
    df["numero"] = df["numero"].astype(str).str.strip()

    df["PhoneClean"] = df["numero"].apply(normalize_phone)
    df = df[df["Mail"].apply(lambda x: bool(EMAIL_RE.match(x)))]
    df = df[df["PhoneClean"].apply(lambda x: bool(PHONE_RE.match(x)))]

    df[["first_name", "last_name"]] = df["Nombre"].apply(
        lambda x: pd.Series(split_name(x))
    )

    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    df_final = pd.DataFrame({
        "first_name": df["first_name"],
        "last_name": df["last_name"],
        "email": df["Mail"],
        "phone": df["PhoneClean"],
        "company": "",
        "consent_marketing": False,
        "consent_date": now_utc,
        "consent_source": "csv_import",
        "unsubscribed": False,
        "created_at": now_utc,
    })

    df_final["email"] = df_final["email"].astype(str).str.strip().str.lower()
    df_final = df_final.drop_duplicates(subset=["email"])

    conn = build_connection()
    existing_emails = get_existing_emails(conn)
    df_final = df_final[~df_final["email"].isin(existing_emails)]

    if df_final.empty:
        print("No hay filas nuevas para insertar en brice.marketing_contacts.")
        conn.close()
        return

    inserted = insert_rows(conn, df_final)
    conn.close()

    print(f"Insertadas {inserted} filas en brice.marketing_contacts")


if __name__ == "__main__":
    main()
