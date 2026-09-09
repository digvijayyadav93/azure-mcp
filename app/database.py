"""Database repositories for local SQLite and Azure SQL execution."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Protocol

from app.errors import NotFoundError


CUSTOMERS = (
    (1, "Aarav Sharma", "aarav.sharma@example.com", "India", "Gold"),
    (2, "Emma Wilson", "emma.wilson@example.com", "UK", "Silver"),
    (3, "Kenji Sato", "kenji.sato@example.com", "Japan", "Gold"),
)

ORDERS = (
    (1001, 1, "2026-01-10", 1250.00, "Completed"),
    (1002, 1, "2026-02-15", 450.50, "Pending"),
    (1003, 2, "2026-01-20", 799.99, "Completed"),
    (1004, 3, "2026-03-01", 2200.00, "Completed"),
    (1005, 3, "2026-03-18", 310.25, "Cancelled"),
)


class CustomerRepository(Protocol):
    """Operations required by the API and MCP backend."""

    def initialize(self) -> None: ...

    def get_customer(self, customer_id: int) -> dict[str, Any]: ...

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]: ...


class SQLiteRepository:
    """Small repository with parameterized queries and deterministic seed data."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    country TEXT NOT NULL,
                    tier TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    order_date TEXT NOT NULL,
                    amount REAL NOT NULL CHECK (amount >= 0),
                    status TEXT NOT NULL,
                    FOREIGN KEY (customer_id) REFERENCES customers(id)
                );
                """
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO customers (id, name, email, country, tier)
                VALUES (?, ?, ?, ?, ?)
                """,
                CUSTOMERS,
            )
            connection.executemany(
                """
                INSERT OR IGNORE INTO orders (id, customer_id, order_date, amount, status)
                VALUES (?, ?, ?, ?, ?)
                """,
                ORDERS,
            )

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, name, email, country, tier FROM customers WHERE id = ?",
                (customer_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"Customer {customer_id} was not found")
        return dict(row)

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[str] = []
        if name:
            clauses.append("LOWER(name) LIKE LOWER(?)")
            parameters.append(f"%{name}%")
        if country:
            clauses.append("LOWER(country) = LOWER(?)")
            parameters.append(country)
        if tier:
            clauses.append("LOWER(tier) = LOWER(?)")
            parameters.append(tier)

        query = "SELECT id, name, email, country, tier FROM customers"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if customer_id is not None:
            clauses.append("customer_id = ?")
            parameters.append(customer_id)
        if status:
            clauses.append("LOWER(status) = LOWER(?)")
            parameters.append(status)

        query = "SELECT id, customer_id, order_date, amount, status FROM orders"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    COUNT(*) AS order_count,
                    COALESCE(ROUND(SUM(amount), 2), 0) AS total_amount,
                    COALESCE(ROUND(AVG(amount), 2), 0) AS average_order_amount
                FROM orders
                WHERE customer_id = ?
                """,
                (customer_id,),
            ).fetchone()
        return {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "order_count": row["order_count"],
            "total_amount": row["total_amount"],
            "average_order_amount": row["average_order_amount"],
        }


class AzureSQLRepository:
    """Read-only Azure SQL repository authenticated with managed identity."""

    def __init__(self, connection_string: str):
        if not connection_string.strip():
            raise ValueError("Azure SQL connection string cannot be empty")
        self.connection_string = connection_string

    def _connect(self) -> Any:
        from mssql_python import connect

        return connect(self.connection_string)

    @staticmethod
    def _rows(cursor: Any) -> list[dict[str, Any]]:
        columns = [column[0] for column in cursor.description]
        result: list[dict[str, Any]] = []
        for row in cursor.fetchall():
            item = dict(zip(columns, row))
            if "order_date" in item and hasattr(item["order_date"], "isoformat"):
                item["order_date"] = item["order_date"].isoformat()
            if "amount" in item and item["amount"] is not None:
                item["amount"] = float(item["amount"])
            result.append(item)
        return result

    def _query(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        connection = self._connect()
        cursor = None
        try:
            cursor = connection.cursor()
            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)
            return self._rows(cursor)
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def initialize(self) -> None:
        """Azure SQL schema is provisioned separately; startup is read-only."""

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        rows = self._query(
            "SELECT id, name, email, country, tier FROM dbo.customers WHERE id = ?",
            (customer_id,),
        )
        if not rows:
            raise NotFoundError(f"Customer {customer_id} was not found")
        return rows[0]

    def search_customers(
        self,
        name: str | None = None,
        country: str | None = None,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if name:
            clauses.append("LOWER(name) LIKE LOWER(?)")
            parameters.append(f"%{name}%")
        if country:
            clauses.append("LOWER(country) = LOWER(?)")
            parameters.append(country)
        if tier:
            clauses.append("LOWER(tier) = LOWER(?)")
            parameters.append(tier)

        query = "SELECT id, name, email, country, tier FROM dbo.customers"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        return self._query(query, tuple(parameters))

    def list_orders(
        self,
        customer_id: int | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if customer_id is not None:
            clauses.append("customer_id = ?")
            parameters.append(customer_id)
        if status:
            clauses.append("LOWER(status) = LOWER(?)")
            parameters.append(status)

        query = "SELECT id, customer_id, order_date, amount, status FROM dbo.orders"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY id"
        return self._query(query, tuple(parameters))

    def get_sales_summary(self, customer_id: int) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        rows = self._query(
            """
            SELECT
                COUNT(*) AS order_count,
                COALESCE(ROUND(SUM(amount), 2), 0) AS total_amount,
                COALESCE(ROUND(AVG(amount), 2), 0) AS average_order_amount
            FROM dbo.orders
            WHERE customer_id = ?
            """,
            (customer_id,),
        )
        summary = rows[0]
        return {
            "customer_id": customer_id,
            "customer_name": customer["name"],
            "order_count": int(summary["order_count"]),
            "total_amount": float(summary["total_amount"]),
            "average_order_amount": float(summary["average_order_amount"]),
        }
