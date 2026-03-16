"""
test_isolation.py
=================
Demonstrates the behavioural difference between READ COMMITTED and
REPEATABLE READ isolation levels on two classic anomalies:

  1. Non-repeatable read
     T1 reads a row twice; T2 updates and commits between the two reads.
     READ COMMITTED  -> T1 sees the NEW value on the second read.
     REPEATABLE READ -> T1 sees the SAME value both times (snapshot).

  2. Lost update (application-level)
     T1 and T2 both read a balance, compute a new value, then write back.
     READ COMMITTED  -> T2 silently overwrites T1's increment -> lost update.
     REPEATABLE READ -> T2 is rolled back with a serialization error.

Usage
-----
  # ensure Postgres is running (docker compose up -d)
  uv run test_isolation.py
"""

import os
import threading
from enum import Enum
from typing import Any, TypedDict

import psycopg2
import psycopg2.extensions
from dotenv import load_dotenv

load_dotenv()


class DataSourceName(TypedDict):
    host: str
    port: str
    dbname: str
    user: str
    password: str


DSN: DataSourceName = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", "5432"),
    "dbname": os.getenv("POSTGRES_DB", "pgisolations"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
}


class IsolationLevel(Enum):
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"


SEP = "-" * 64


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def connect() -> psycopg2.extensions.connection:
    """Return a raw autocommit connection. Transactions are managed explicitly."""
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    return conn


def begin_transaction(cur: psycopg2.extensions.cursor, isolation: IsolationLevel) -> None:
    """Open an explicit transaction at the given isolation level."""
    cur.execute("BEGIN;")
    cur.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation.value};")


def setup() -> None:
    """Create or reset the accounts table with a single row (alice, 100)."""
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS accounts;")
        cur.execute(
            """
            CREATE TABLE accounts (
                id      SERIAL PRIMARY KEY,
                owner   TEXT    NOT NULL,
                balance INTEGER NOT NULL
            );
            """
        )
        cur.execute("INSERT INTO accounts (owner, balance) VALUES ('alice', 100);")
    conn.close()


def reset_balance(value: int = 100) -> None:
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE accounts SET balance = %s WHERE owner = 'alice';", (value,)
        )
    conn.close()


def read_balance() -> int:
    conn = psycopg2.connect(**DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT balance FROM accounts WHERE owner = 'alice';")
        row = cur.fetchone()
        assert row is not None, "No row found for alice"
        val: int = row[0]
    conn.close()
    return val


# ---------------------------------------------------------------------------
# Test 1 - Non-repeatable read
# ---------------------------------------------------------------------------

def test_non_repeatable_read(isolation: IsolationLevel) -> None:
    """
    Timeline
    --------
    T1: BEGIN --> read_1 --[barrier A]--[barrier B]--> read_2 --> COMMIT
    T2:                  --[barrier A]--> UPDATE+COMMIT --[barrier B]
    """
    print(f"\n{SEP}")
    print(f"  NON-REPEATABLE READ  |  {isolation.name}")
    print(SEP)

    reset_balance(100)

    barrier_a = threading.Barrier(2)  # T1 has done read_1; T2 may now update
    barrier_b = threading.Barrier(2)  # T2 has committed; T1 may now do read_2

    results: dict[str, Any] = {}

    def t1() -> None:
        conn = connect()
        with conn.cursor() as cur:
            try:
                begin_transaction(cur, isolation)
                print(f"    T1  BEGIN ({isolation.name})")

                cur.execute("SELECT balance FROM accounts WHERE owner = 'alice';")
                row1 = cur.fetchone()
                assert row1 is not None
                results["read_1"] = row1[0]
                print(f"    T1  read_1 = {results['read_1']}")

                barrier_a.wait()   # tell T2 to update
                barrier_b.wait()   # wait for T2 to commit

                cur.execute("SELECT balance FROM accounts WHERE owner = 'alice';")
                row2 = cur.fetchone()
                assert row2 is not None
                results["read_2"] = row2[0]
                print(f"    T1  read_2 = {results['read_2']}")

                cur.execute("COMMIT;")
                print("    T1  COMMIT")
            except Exception as exc:
                cur.execute("ROLLBACK;")
                print(f"    T1  ROLLBACK - {exc}")
                raise
        conn.close()

    def t2() -> None:
        conn = connect()
        barrier_a.wait()   # wait for T1's first read
        with conn.cursor() as cur:
            begin_transaction(cur, IsolationLevel.READ_COMMITTED)
            print(f"    T2  BEGIN ({IsolationLevel.READ_COMMITTED.name})")
            cur.execute(
                "UPDATE accounts SET balance = 200 WHERE owner = 'alice';"
            )
            cur.execute("COMMIT;")
            print("    T2  COMMIT - balance = 200")
        conn.close()
        barrier_b.wait()   # signal T1

    th1 = threading.Thread(target=t1)
    th2 = threading.Thread(target=t2)
    th1.start()
    th2.start()
    th1.join()
    th2.join()

    changed = results["read_1"] != results["read_2"]
    if isolation == IsolationLevel.READ_COMMITTED:
        verdict = "[FAIL]  Non-repeatable read occurred (read_1 != read_2) - expected"
    else:
        verdict = "[OK]  Snapshot preserved (read_1 == read_2) - expected"

    print(f"\n    {'changed [FAIL]' if changed else 'unchanged [OK]'}  |  {verdict}")


# ---------------------------------------------------------------------------
# Test 2 - Lost update
# ---------------------------------------------------------------------------

def test_lost_update(isolation: IsolationLevel) -> None:
    """
    Timeline
    --------
    T1: BEGIN --> read(100) --[barrier A]--> UPDATE(+50)--COMMIT --[barrier B]
    T2: BEGIN --> read(100) --[barrier A]--[barrier B]--> UPDATE(+30)--COMMIT?

    Expected total: 100 + 50 + 30 = 180
    READ COMMITTED  -> T2 writes 130 (lost T1's +50)
    REPEATABLE READ -> T2 is rolled back (serialization error)
    """
    print(f"\n{SEP}")
    print(f"  LOST UPDATE          |  {isolation.name}")
    print(SEP)

    reset_balance(100)

    barrier_a = threading.Barrier(2)  # both have read; T1 may now update
    barrier_b = threading.Barrier(2)  # T1 has committed; T2 may now update

    results: dict[str, Any] = {"t2_error": None}

    def t1() -> None:
        conn = connect()
        new_bal: int = 0
        with conn.cursor() as cur:
            try:
                begin_transaction(cur, isolation)
                print(f"    T1  BEGIN ({isolation.name})")

                cur.execute("SELECT balance FROM accounts WHERE owner = 'alice';")
                row = cur.fetchone()
                assert row is not None
                balance: int = row[0]
                print(f"    T1  read balance = {balance}")
                barrier_a.wait()

                new_bal = balance + 50
                cur.execute(
                    "UPDATE accounts SET balance = %s WHERE owner = 'alice';",
                    (new_bal,),
                )
                cur.execute("COMMIT;")
                print(f"    T1  COMMIT - balance = {new_bal} (+50)")
            except Exception as exc:
                cur.execute("ROLLBACK;")
                print(f"    T1  ROLLBACK - {exc}")
                raise
            finally:
                barrier_b.wait()  # always unblock T2, even on error
        conn.close()

    def t2() -> None:
        conn = connect()
        new_bal: int = 0
        with conn.cursor() as cur:
            try:
                begin_transaction(cur, isolation)
                print(f"    T2  BEGIN ({isolation.name})")

                cur.execute("SELECT balance FROM accounts WHERE owner = 'alice';")
                row = cur.fetchone()
                assert row is not None
                balance: int = row[0]
                print(f"    T2  read balance = {balance}")
                barrier_a.wait()
                barrier_b.wait()  # wait for T1 to commit

                new_bal = balance + 30
                cur.execute(
                    "UPDATE accounts SET balance = %s WHERE owner = 'alice';",
                    (new_bal,),
                )
                cur.execute("COMMIT;")
                print(f"    T2  COMMIT - balance = {new_bal} (+30)")
            except Exception as exc:
                cur.execute("ROLLBACK;")
                results["t2_error"] = str(exc).strip()
                print(f"    T2  ROLLBACK - {exc}")
        conn.close()

    th1 = threading.Thread(target=t1)
    th2 = threading.Thread(target=t2)
    th1.start()
    th2.start()
    th1.join()
    th2.join()

    final = read_balance()
    print(f"\n    Final balance = {final}  (wanted 180)")

    if results.get("t2_error") is not None:
        print(f"    [OK]  T2 serialization error -> retry required - expected for REPEATABLE READ")
        print(f"       error: {results['t2_error']}")
    elif final == 180:
        print("    [OK]  Both increments applied correctly - no lost update")
    elif final == 130:
        print("    [FAIL]  Lost update: T1's +50 was overwritten (READ COMMITTED - expected)")
    else:
        print(f"    [?]  Unexpected final balance: {final}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("Setting up accounts table ...")
    setup()
    print("alice's initial balance = 100\n")

    for level in IsolationLevel:
        test_non_repeatable_read(level)
        test_lost_update(level)

    print(f"\n{SEP}")
    print("  Done.")
    print(SEP)


if __name__ == "__main__":
    main()
