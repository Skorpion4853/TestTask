
from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, SmallInteger, String, create_engine, event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker





#------------- Create script --------------

DB_PATH = Path(__file__).parent / "database.db"

engine = create_async_engine(f"sqlite+aiosqlite:///{DB_PATH}")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(engine.sync_engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    # В SQLite проверка внешних ключей по умолчанию выключена
    dbapi_connection.execute("PRAGMA foreign_keys = ON")


class Base(DeclarativeBase):
    pass


class Tariff(Base):
    __tablename__ = "Tarrifs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    payments: Mapped[list["Payment"]] = relationship(back_populates="tariff")


class Payment(Base):
    __tablename__ = "Payments"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String(9), nullable=False)  # NVARCHAR(9)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("Tarrifs.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    discount: Mapped[int | None] = mapped_column(Integer)
    method: Mapped[str] = mapped_column(String(10), nullable=False)  # NVARCHAR(10)
    installment_months: Mapped[int | None] = mapped_column(SmallInteger)  # TINYINT
    schedule: Mapped[list | None] = mapped_column(JSON)  # список хранится как JSON
    email: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    tariff: Mapped["Tariff"] = relationship(back_populates="payments")


async def create_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

#------------ Interact command ----------------------
# ---------- Tarrifs ----------

async def create_tariff(title: str, price: int) -> Tariff:
    async with SessionLocal() as session:
        tariff = Tariff(title=title, price=price)
        session.add(tariff)
        await session.commit()
        await session.refresh(tariff)
        return tariff


async def get_tariffs() -> list[Tariff]:
    async with SessionLocal() as session:
        return list(await session.scalars(select(Tariff)))

def tariffs_to_list(tariffs: list[Tariff]) -> list:
    lst = []
    for tariff in tariffs:
        lst.append({
            "id": tariff.id,
            "title": tariff.title,
            "price": tariff.price,
        })
    return lst

# ---------- Payments ----------

async def get_payment(payment_id: int) -> Payment | None:
    async with SessionLocal() as session:
        return await session.get(Payment, payment_id)

async def get_payment_by_key(session, key: str) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.idempotency_key == key))

async def get_payment_by_id(session, id: int) -> Payment | None:
    return await session.scalar(select(Payment).where(Payment.id == id))

def payment_to_dict(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "status": payment.status,
        "tariff_id": payment.tariff_id,
        "amount": payment.amount,
        "discount": payment.discount,
        "method": payment.method,
        "installment_months": payment.installment_months,
        "schedule": payment.schedule,
        "email": payment.email,
        "created_at": payment.created_at.isoformat(),
    }