from datetime import datetime, timezone
from typing import List, Optional, Tuple

import sqlalchemy
from sqlalchemy import (BigInteger, Column, Float, Integer, String,
                        UniqueConstraint, select)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from XyroSub import SCHEMA, logger
from XyroSub.database import BASE

engine = create_async_engine(SCHEMA, echo=False)
async_session = async_sessionmaker(bind=engine,
                                   autoflush=True,
                                   expire_on_commit=False)


class Subscriptions(BASE):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    transaction_id = Column(String, nullable=False)
    short_id = Column(String, nullable=False, unique=True)
    user_id = Column(BigInteger, nullable=False)
    amount = Column(Integer, nullable=False)
    payment_date = Column(
        Float, default=lambda: datetime.now(timezone.utc).timestamp())
    next_invoice_date = Column(Float, nullable=False)
    cancel_on_next_invoice = Column(Integer, nullable=False, default=0)
    plan_type = Column(String, nullable=False)
    recurring_interval = Column(Integer, nullable=False)
    first_time_payment = Column(
        Float, default=lambda: datetime.now(timezone.utc).timestamp())
    affiliate_code = Column(String, nullable=True)

    __table_args__ = (UniqueConstraint('short_id', name='_short_id_uc'), )

    def __init__(
        self,
        transaction_id: str,
        short_id: str,
        user_id: int,
        amount: int,
        payment_date: float,
        next_invoice_date: float,
        plan_type: str,
        recurring_interval: int,
        cancel_on_next_invoice: int = 0,
        first_time_payment: Optional[float] = None,
        affiliate_code: Optional[str] = None,
    ):
        self.transaction_id = transaction_id
        self.short_id = short_id
        self.user_id = user_id
        self.amount = amount
        self.payment_date = payment_date
        self.next_invoice_date = next_invoice_date
        self.plan_type = plan_type
        self.recurring_interval = recurring_interval
        self.cancel_on_next_invoice = cancel_on_next_invoice
        self.first_time_payment = first_time_payment or payment_date
        self.affiliate_code = affiliate_code

    def __repr__(self):
        return f"<Subscriptions transaction_id={self.transaction_id} short_id={self.short_id} user_id={self.user_id} amount={self.amount} payment_date={self.payment_date} next_invoice_date={self.next_invoice_date} cancel_on_next_invoice={self.cancel_on_next_invoice} plan_type={self.plan_type} recurring_interval={self.recurring_interval} first_time_payment={self.first_time_payment}>"


async def save_transaction(
    transaction_id: str,
    short_id: str,
    user_id: int,
    amount: int,
    payment_date: float,
    next_invoice_date: float,
    plan_type: str,
    recurring_interval: int,
    affiliate_code: Optional[str] = None,
):
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Subscriptions).where(
                    Subscriptions.transaction_id == transaction_id))
            existing_transaction = result.scalar_one_or_none()

            if existing_transaction:
                logger.info(f"Transaction {transaction_id} already exists.")
                return existing_transaction


            new_subscription = Subscriptions(
                transaction_id=transaction_id,
                short_id=short_id,
                user_id=user_id,
                amount=amount,
                payment_date=payment_date,
                next_invoice_date=next_invoice_date,
                plan_type=plan_type,
                recurring_interval=recurring_interval,
                first_time_payment=payment_date,
                affiliate_code=affiliate_code,
            )
            session.add(new_subscription)
            await session.commit()
            logger.info(
                f"Transaction saved for transaction_id={transaction_id} user_id={user_id}"
            )
            return new_subscription


async def get_all_subscriptions() -> List[Subscriptions]:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(Subscriptions))
            subscriptions = result.scalars().all()
            logger.info("All subscriptions retrieved")
            return subscriptions


async def get_transaction(transaction_id: str) -> Optional[Subscriptions]:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Subscriptions).where(
                    Subscriptions.transaction_id == transaction_id))
            transaction = result.scalar_one_or_none()
            logger.info(
                f"Transaction retrieved for transaction_id={transaction_id}: {transaction}"
            )
            return transaction


async def get_transaction_by_short_id(
        short_id: str) -> Optional[Subscriptions]:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Subscriptions).where(Subscriptions.short_id == short_id)
            )
            transaction = result.scalar_one_or_none()
            logger.info(
                f"Transaction retrieved for short_id={short_id}: {transaction}"
            )
            return transaction


async def delete_transaction(transaction_id: str):
    async with async_session() as session:
        async with session.begin():
            await session.execute(
                sqlalchemy.delete(Subscriptions).where(
                    Subscriptions.transaction_id == transaction_id))
            await session.commit()
            logger.info(
                f"Transaction deleted for transaction_id={transaction_id}")


async def update_next_invoice_date(transaction_id: str,
                                   next_invoice_date: float):
    async with async_session() as session:
        try:
            async with session.begin():
                query = (select(Subscriptions).where(
                    Subscriptions.transaction_id ==
                    transaction_id).with_for_update())
                result = await session.execute(query)
                subscription = result.scalar_one_or_none()

                if subscription:
                    subscription.next_invoice_date = next_invoice_date
                    await session.commit()
                    logger.info(
                        f"Updated next invoice date for transaction_id={transaction_id} to next_invoice_date={next_invoice_date}"
                    )
        except SQLAlchemyError as e:
            logger.error(
                f"Error updating next invoice date for transaction_id={transaction_id}: {e}"
            )
            await session.rollback()


async def mark_for_cancellation(transaction_id: str):
    async with async_session() as session:
        async with session.begin():
            query = (select(Subscriptions).where(
                Subscriptions.transaction_id ==
                transaction_id).with_for_update())
            result = await session.execute(query)
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.cancel_on_next_invoice = 1
                await session.commit()
                logger.info(
                    f"Marked subscription for cancellation for transaction_id={transaction_id}"
                )
            else:
                logger.error(
                    f"Subscription not found for transaction_id={transaction_id}"
                )
                return None


async def update_transaction(existing_transaction_id: str,
                             new_transaction_id: str, amount: int,
                             payment_date: float, next_invoice_date: float):
    async with async_session() as session:
        async with session.begin():
            query = (select(Subscriptions).where(
                Subscriptions.transaction_id ==
                existing_transaction_id).with_for_update())
            result = await session.execute(query)
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.transaction_id = new_transaction_id
                subscription.amount = amount
                subscription.payment_date = payment_date
                subscription.next_invoice_date = next_invoice_date
                await session.commit()
                logger.info(
                    f"Updated transaction for existing_transaction_id={existing_transaction_id} with new_transaction_id={new_transaction_id}"
                )
            else:
                logger.error(
                    f"Subscription not found for existing_transaction_id={existing_transaction_id}"
                )
                return None


async def update_cancel_on_next_invoice(transaction_id: str,
                                        cancel_on_next_invoice: int):
    async with async_session() as session:
        async with session.begin():
            query = (select(Subscriptions).where(
                Subscriptions.transaction_id ==
                transaction_id).with_for_update())
            result = await session.execute(query)
            subscription = result.scalar_one_or_none()

            if subscription:
                subscription.cancel_on_next_invoice = cancel_on_next_invoice
                await session.commit()
                logger.info(
                    f"Updated cancel_on_next_invoice for transaction_id={transaction_id} to cancel_on_next_invoice={cancel_on_next_invoice}"
                )
            else:
                logger.error(
                    f"Subscription not found for transaction_id={transaction_id}"
                )
                return None


async def get_all_transactions_user(
        user_id: int) -> List[Tuple[Subscriptions]]:
    async with async_session() as session:
        async with session.begin():
            statement = select(Subscriptions).where(
                Subscriptions.user_id == user_id)
            results = await session.execute(statement)
            return results.all()

async def has_active_subscription(user_id: int) -> bool:
    subscriptions = await get_all_subscriptions()
    user_subscriptions = [
        sub for sub in subscriptions if sub.user_id == user_id
    ]
    return any(sub for sub in user_subscriptions if sub.cancel_on_next_invoice == 0)

