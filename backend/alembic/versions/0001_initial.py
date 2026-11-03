"""Начальная схема: cars, sales, returns и стартовые марки.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SEED_CARS = ["к10", "к20", "к25", "мерс210", "пб5+", "с"]


def upgrade() -> None:
    cars = op.create_table(
        "cars",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "sales",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("car_id", sa.Integer, sa.ForeignKey("cars.id"), nullable=False),
        sa.Column("old_car_code", sa.String(50), nullable=True),
        sa.Column("part", sa.String(500), nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_sales_price_positive"),
    )
    op.create_index("ix_sales_car_part_price", "sales", ["car_id", "part", "price"])
    op.create_index("ix_sales_sold_at", "sales", ["sold_at"])
    op.create_table(
        "returns",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("car_id", sa.Integer, sa.ForeignKey("cars.id"), nullable=False),
        sa.Column("old_car_code", sa.String(50), nullable=True),
        sa.Column("part", sa.String(500), nullable=False),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("price > 0", name="ck_returns_price_positive"),
    )
    op.create_index("ix_returns_returned_at", "returns", ["returned_at"])
    op.bulk_insert(cars, [{"name": name} for name in SEED_CARS])


def downgrade() -> None:
    op.drop_table("returns")
    op.drop_table("sales")
    op.drop_table("cars")
