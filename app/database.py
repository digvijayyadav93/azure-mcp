"""SQLite repository used by the local demo and mock database API."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

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

