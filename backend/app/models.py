from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.constants import car_label


class Base(DeclarativeBase):
    pass


class Car(Base):
    __tablename__ = "cars"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def label(self) -> str:
        return car_label(self.name)


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_sales_price_positive"),
        Index("ix_sales_car_part_price", "car_id", "part", "price"),
        Index("ix_sales_sold_at", "sold_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"))
    old_car_code: Mapped[str | None] = mapped_column(String(50))
    part: Mapped[str] = mapped_column(String(500))
    price: Mapped[int] = mapped_column(Integer)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    car: Mapped[Car] = relationship(lazy="joined", innerjoin=True)


class Return(Base):
    __tablename__ = "returns"
    __table_args__ = (
        CheckConstraint("price > 0", name="ck_returns_price_positive"),
        Index("ix_returns_returned_at", "returned_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"))
    old_car_code: Mapped[str | None] = mapped_column(String(50))
    part: Mapped[str] = mapped_column(String(500))
    price: Mapped[int] = mapped_column(Integer)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    car: Mapped[Car] = relationship(lazy="joined", innerjoin=True)
