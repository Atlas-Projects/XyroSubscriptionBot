from datetime import datetime, timezone
from typing import List, Optional

import sqlalchemy
from sqlalchemy import (BigInteger, Boolean, Column, Float, Integer, String,
                        UniqueConstraint, select)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from XyroSub import SCHEMA, logger
from XyroSub.database import BASE

engine = create_async_engine(SCHEMA, echo=False)
async_session = async_sessionmaker(bind=engine,
                                   autoflush=True,
                                   expire_on_commit=False)


class Discounts(BASE):
    __tablename__ = 'discounts'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    code = Column(String, nullable=False, unique=True)
    discount_type = Column(String, nullable=False)
    discount_value = Column(Integer, nullable=False)
    discount_scope = Column(String, nullable=False)
    discount_plan_type = Column(String, default='all', nullable=False)
    max_uses = Column(Integer, nullable=True)
    expiry_time = Column(Float, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint('code', name='_code_uc'), )

    def __init__(
        self,
        code: str,
        discount_type: str,
        discount_value: int,
        discount_scope: str,
        max_uses: Optional[int] = None,
        expiry_time: Optional[float] = None,
        discount_plan_type: str = 'all',
    ):
        self.code = code
        self.discount_type = discount_type
        self.discount_value = discount_value
        self.discount_scope = discount_scope
        self.max_uses = max_uses
        self.expiry_time = expiry_time
        self.discount_plan_type = discount_plan_type

    def __repr__(self):
        return f"<Discounts code={self.code} type={self.discount_type} value={self.discount_value} scope={self.discount_scope} max_uses={self.max_uses} expiry_time={self.expiry_time}>"


class DiscountUsage(BASE):
    __tablename__ = 'discount_usage'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    discount_id = Column(Integer,
                         sqlalchemy.ForeignKey('discounts.id'),
                         nullable=False)
    user_id = Column(BigInteger, nullable=False)
    usage_time = Column(Float,
                        default=lambda: datetime.now(timezone.utc).timestamp())

    __table_args__ = (UniqueConstraint('discount_id',
                                       'user_id',
                                       name='_discount_user_uc'), )

    def __init__(self, discount_id: int, user_id: int):
        self.discount_id = discount_id
        self.user_id = user_id

    def __repr__(self):
        return f"<DiscountUsage discount_id={self.discount_id} user_id={self.user_id} usage_time={self.usage_time}>"


async def create_discount(code: str,
                          discount_type: str,
                          discount_value: int,
                          discount_scope: str,
                          max_uses: Optional[int],
                          expiry_time: Optional[float],
                          discount_plan_type: str = 'all'):
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(Discounts).where(Discounts.code == code))
                existing_discount = result.scalar_one_or_none()

                if existing_discount:
                    logger.info(f"Discount with code {code} already exists.")
                    return existing_discount

                new_discount = Discounts(
                    code=code,
                    discount_type=discount_type,
                    discount_value=discount_value,
                    discount_scope=discount_scope,
                    max_uses=max_uses,
                    expiry_time=expiry_time,
                    discount_plan_type=discount_plan_type,
                )

                session.add(new_discount)
                await session.commit()
                logger.info(f"Discount saved with code={code}")
                return new_discount

            except SQLAlchemyError as e:
                logger.error(f"Failed to create discount: {e}")
                await session.rollback()
                return None


async def change_discount_status(code: str,
                                 active: bool) -> Optional[Discounts]:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(Discounts).where(Discounts.code == code))
                discount = result.scalar_one_or_none()

                if discount is None:
                    return None

                discount.active = active
                await session.commit()
                return discount

            except SQLAlchemyError as e:
                logger.error(f"Failed to change discount status: {e}")
                await session.rollback()
                return None


async def get_act_discount() -> Optional[List[Discounts]]:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(Discounts).where(
                        Discounts.active == True)  # noqa: E712
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                logger.error(f"Failed to check active discount: {e}")
                return None


async def get_discount(discount_code: str) -> Optional[Discounts]:
    async with async_session() as session:
        async with session.begin():
            try:
                statement = select(Discounts).where(
                    Discounts.code == discount_code)
                discount = (await
                            session.execute(statement)).scalar_one_or_none()
                return discount
            except SQLAlchemyError as sqex:
                logger.error(
                    f'Failed to fetch discount with code: {discount_code}\n\
Actual error: {sqex}')
                return None


async def get_discount_by_id(discount_id: int) -> Optional[Discounts]:
    try:
        async with async_session() as session:
            async with session.begin():
                statement = select(Discounts).where(
                    Discounts.id == discount_id)
                discount = (await
                            session.execute(statement)).scalar_one_or_none()
                return discount
    except SQLAlchemyError as sqex:
        logger.error(f'Failed to fetch discount with id: {discount_id}\n\
Actual error: {sqex}')
        return None


async def get_active_discount(user_id: int) -> List[Discounts]:
    async with async_session() as session:
        async with session.begin():
            try:
                now = datetime.now(timezone.utc).timestamp()

                result = await session.execute(
                    select(Discounts).where(
                        Discounts.active == True,  # noqa: E712
                        (Discounts.expiry_time == None) |  # noqa: E711
                        (Discounts.expiry_time > now),
                        (Discounts.max_uses == None) |  # noqa: E711
                        (Discounts.usage_count < Discounts.max_uses)))
                active_discounts = result.scalars().all()
                active_available_discounts = []

                for active_discount in active_discounts:
                    used_discount = await session.execute(
                        select(DiscountUsage).where(
                            DiscountUsage.discount_id == active_discount.id,
                            DiscountUsage.user_id == user_id))
                    if not used_discount.scalar_one_or_none():
                        active_available_discounts.append(active_discount)

                return active_available_discounts

            except SQLAlchemyError as e:
                logger.error(
                    f"Failed to check active discount for user {user_id}: {e}")
                return None


async def update_discount_usage(discount_code: str) -> Optional[Discounts]:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(Discounts).where(
                        Discounts.code == discount_code,
                        Discounts.active == True)  # noqa: E712
                )
                discount = result.scalar_one_or_none()

                if discount:
                    discount.usage_count += 1
                    await session.commit()
                    logger.info(
                        f"Updated usage count for discount '{discount_code}' to {discount.usage_count}"
                    )
                    return discount

                return None

            except SQLAlchemyError as e:
                logger.error(
                    f"Failed to update usage count for discount '{discount_code}': {e}"
                )
                await session.rollback()
                return None


async def save_discount_usage(discount_id: int, user_id: int):
    async with async_session() as session:
        async with session.begin():
            try:
                discount_usage = DiscountUsage(discount_id=discount_id,
                                               user_id=user_id)
                session.add(discount_usage)
                await session.commit()
                logger.info(
                    f"Saved discount usage for discount_id {discount_id} and user_id {user_id}"
                )
            except SQLAlchemyError as e:
                logger.error(f"Failed to save discount usage: {e}")
                await session.rollback()


async def get_discount_usage(discount_id: int,
                             user_id: int) -> Optional[DiscountUsage]:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(DiscountUsage).where(
                        DiscountUsage.discount_id == discount_id,
                        DiscountUsage.user_id == user_id))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                logger.error(f"Failed to check discount usage: {e}")
                return None


async def get_all_discounts() -> List[Discounts]:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(select(Discounts))
                return result.scalars().all()
            except SQLAlchemyError as e:
                logger.error(f"Failed to fetch all discounts: {e}")
                return []


async def delete_discount(code: str) -> bool:
    async with async_session() as session:
        async with session.begin():
            try:
                result = await session.execute(
                    select(Discounts).where(Discounts.code == code))
                discount = result.scalar_one_or_none()

                if discount:
                    await session.delete(discount)
                    await session.commit()
                    logger.info(f"Deleted discount with code: {code}")
                    return True
                else:
                    logger.info(f"No discount found with code: {code}")
                    return False
            except SQLAlchemyError as e:
                logger.error(f"Failed to delete discount: {e}")
                await session.rollback()
                return False
