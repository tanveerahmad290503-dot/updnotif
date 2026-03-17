import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Load .env FIRST
load_dotenv()


def ensure_database():
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")

    if not all([DB_NAME, DB_USER, DB_PASSWORD]):
        raise Exception("Database environment variables not properly set.")

    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_NAME,)
        )
        exists = cursor.fetchone()

        if not exists:
            cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"Database '{DB_NAME}' created successfully.")
        else:
            print(f"Database '{DB_NAME}' already exists.")

        cursor.close()
        conn.close()

    except Exception as e:
        print("Database bootstrap failed:", e)


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jobintel.settings')

    # Ensure database exists before Django starts
    ensure_database()

    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
