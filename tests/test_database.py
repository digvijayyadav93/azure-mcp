import pytest

from app.database import SQLiteRepository
from app.errors import NotFoundError


def test_seeded_customer_and_filters(repository: SQLiteRepository) -> None:
    customer = repository.get_customer(1)
    assert customer["name"] == "Aarav Sharma"
    assert customer["country"] == "India"
    assert [item["name"] for item in repository.search_customers(tier="Gold")] == [
        "Aarav Sharma",
        "Kenji Sato",
    ]
    assert repository.search_customers(name="wilson")[0]["id"] == 2


def test_orders_and_sales_summary(repository: SQLiteRepository) -> None:
    assert len(repository.list_orders()) == 5
    assert len(repository.list_orders(customer_id=1)) == 2
    assert len(repository.list_orders(status="Completed")) == 3
    assert repository.get_sales_summary(1) == {
        "customer_id": 1,
        "customer_name": "Aarav Sharma",
        "order_count": 2,
        "total_amount": 1700.5,
        "average_order_amount": 850.25,
    }


def test_missing_customer_raises(repository: SQLiteRepository) -> None:
    with pytest.raises(NotFoundError, match="999"):
        repository.get_customer(999)

