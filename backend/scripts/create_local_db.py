"""Create the local EchoLearn database and its login role (used by setup.bat on Windows).

Connects to a LOCAL PostgreSQL server as the superuser, then creates (or updates) the role
and database named in the arguments. Safe to run again: existing objects are kept and the
role's password is reset to the one given.

The superuser password is read from the ECHOLEARN_PG_SUPERPASS environment variable and the
app role's password from ECHOLEARN_DB_PASS, so neither appears in the process list.

Usage (from the backend folder):
    python scripts/create_local_db.py --db echolearn --user echolearn [--host localhost --port 5432]
Exit codes: 0 ok, 2 could not log in as the superuser, 1 anything else.
"""
import argparse
import os
import sys

import psycopg2
from psycopg2 import sql


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="echolearn")
    p.add_argument("--user", default="echolearn")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", default="5432")
    p.add_argument("--superuser", default="postgres")
    a = p.parse_args()

    if a.host not in ("localhost", "127.0.0.1", "::1"):
        print("Refusing to create a database on a non-local server.", file=sys.stderr)
        return 1
    app_pass = os.environ.get("ECHOLEARN_DB_PASS", "")
    if not app_pass:
        print("ECHOLEARN_DB_PASS is not set.", file=sys.stderr)
        return 1

    try:
        conn = psycopg2.connect(host=a.host, port=a.port, dbname="postgres", user=a.superuser,
                                password=os.environ.get("ECHOLEARN_PG_SUPERPASS", ""), connect_timeout=10)
    except psycopg2.OperationalError as e:
        print(f"Could not log in to PostgreSQL as '{a.superuser}': {str(e).strip()}", file=sys.stderr)
        return 2
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (a.user,))
    if cur.fetchone():
        cur.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(a.user)), (app_pass,))
        print(f"Role '{a.user}' already existed; password updated.")
    else:
        cur.execute(sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(a.user)), (app_pass,))
        print(f"Created role '{a.user}'.")

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (a.db,))
    if cur.fetchone():
        print(f"Database '{a.db}' already exists.")
    else:
        cur.execute(sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8' TEMPLATE template0").format(
            sql.Identifier(a.db), sql.Identifier(a.user)))
        print(f"Created database '{a.db}'.")
    cur.execute(sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(sql.Identifier(a.db), sql.Identifier(a.user)))
    conn.close()

    # PostgreSQL 15+ no longer lets ordinary roles create tables in "public" by default.
    conn = psycopg2.connect(host=a.host, port=a.port, dbname=a.db, user=a.superuser,
                            password=os.environ.get("ECHOLEARN_PG_SUPERPASS", ""), connect_timeout=10)
    conn.autocommit = True
    conn.cursor().execute(sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(a.user)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
