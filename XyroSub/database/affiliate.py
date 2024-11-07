import asyncio
from typing import Optional, Tuple

from sqlalchemy import BigInteger, Column, Float, String, select, UniqueConstraint
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from XyroSub import SCHEMA, logger
from XyroSub.database import BASE
from XyroSub.database.subscription import get_all_transactions_user

engine = create_async_engine(SCHEMA, echo=False)
async_session = async_sessionmaker(bind=engine,
                                   autoflush=True,
                                   expire_on_commit=False)


class AffiliateUsers(BASE):
    __tablename__ = 'affiliate_users'

    affiliate_user = Column(BigInteger, nullable=False)
    referred_user = Column(BigInteger, primary_key=True, nullable=False)

    def __init__(self, affiliate_user: int, referred_user: int) -> None:
        self.affiliate_user = affiliate_user
        self.referred_user = referred_user

    def __repr__(self) -> str:
        return f'AffiliateUsers: affiliate_user: {self.affiliate_user}, referred_user: {self.referred_user}'


class AffiliateSettings(BASE):
    __tablename__ = 'affiliate_settings'

    affiliate_user = Column(BigInteger, primary_key=True, nullable=False)
    affiliate_code = Column(String, primary_key=True, nullable=False)
    earnings = Column(Float, default=0.0)

    def __init__(self,
                 affiliate_user: int,
                 affiliate_code: str,
                 earnings: float = 0.0) -> None:
        self.affiliate_user = affiliate_user
        self.affiliate_code = affiliate_code
        self.earnings = earnings

    def __repr__(self) -> str:
        return f'AffiliateSettings: affiliate_user: {self.affiliate_user}, affiliate_code: {self.affiliate_code}, earnings: {self.earnings}'


class Referrals(BASE):
    __tablename__ = 'referrals'

    affiliate_user_id = Column(BigInteger, nullable=False)
    referred_user_id = Column(BigInteger, nullable=False, primary_key=True)
    amount_earned = Column(Float, default=0.0)
    short_id = Column(String, unique=True, nullable=False)


    def __init__(self, affiliate_user_id: int, referred_user_id: int, amount_earned: float, short_id: str) -> None:
        self.affiliate_user_id = affiliate_user_id
        self.referred_user_id = referred_user_id
        self.amount_earned = amount_earned
        self.short_id = short_id

    def __repr__(self) -> str:
        return f'Referrals: affiliate_user_id: {self.affiliate_user_id}, referred_user_id: {self.referred_user_id}, amount_earned: {self.amount_earned}, short_id: {self.short_id}'


AFFILIATE_USER_LOCK = asyncio.Lock()
AFFILIATE_SETTINGS_LOCK = asyncio.Lock()


async def save_affiliate_user(affiliate_user: int, referred_user: int) -> None:
    try:
        async with AFFILIATE_USER_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateUsers).where(
                        AffiliateUsers.referred_user == referred_user)
                    ref_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    if ref_user:
                        ref_user.affiliate_user = affiliate_user
                    else:
                        ref_user = AffiliateUsers(
                            affiliate_user=affiliate_user,
                            referred_user=referred_user)
                        session.add(ref_user)
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while saving affiliate user, for affiliate_user: {affiliate_user} and referred_user: {referred_user}\n\
Actual error: {sqex}')

async def delete_affiliate_user(referred_user_id: int) -> Optional[bool]:
    try:
        async with async_session() as session:
            async with session.begin():
                statement = select(AffiliateUsers).where(AffiliateUsers.referred_user == referred_user_id)
                affiliate_user = (await session.execute(statement)).scalar_one_or_none()

                if affiliate_user:
                    await session.delete(affiliate_user)
                    await session.commit()
                    logger.info(f'Deleted affiliate user entry for referred_user_id: {referred_user_id}')
                    return True
                else:
                    logger.warning(f'No affiliate user entry found for referred_user_id: {referred_user_id}.')
                    return False
    except SQLAlchemyError as sqex:
        logger.error(f'Failed to delete affiliate user for referred_user_id: {referred_user_id}\nActual error: {sqex}')
        return False

async def get_affiliate_user(referred_user: int) -> Optional[AffiliateUsers]:
    try:
        async with AFFILIATE_USER_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateUsers).where(
                        AffiliateUsers.referred_user == referred_user)
                    ref_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    return ref_user
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while fetching affiliated user, for referred_user: {referred_user}\n\
Actual error: {sqex}')


async def set_affiliate_settings(affiliate_user: int, affiliate_code: str,
                                 earnings: float) -> None:
    try:
        async with AFFILIATE_SETTINGS_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateSettings).where(
                        AffiliateSettings.affiliate_user == affiliate_user)
                    aff_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    if aff_user:
                        aff_user.affiliate_code = affiliate_code
                        aff_user.earnings = aff_user.earnings + earnings
                    else:
                        aff_user = AffiliateSettings(
                            affiliate_user=affiliate_user,
                            affiliate_code=affiliate_code,
                            earnings=earnings)
                        session.add(aff_user)
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while saving affiliate settings, for affiliate_user: {affiliate_user}, with code: {affiliate_code} and earnings: {earnings}\n\
Actual error: {sqex}')


async def get_affiliate_settings(
        affiliate_user: int) -> Optional[AffiliateSettings]:
    try:
        async with AFFILIATE_SETTINGS_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateSettings).where(
                        AffiliateSettings.affiliate_user == affiliate_user)
                    aff_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    return aff_user
    except SQLAlchemyError as sqex:
        logger.error(
            f'Failed to fetch AffiliateSettings for affiliate_user: {affiliate_user}\n\
Actual error: {sqex}')


async def modify_earnings(affiliate_user: int,
                          earnings: float) -> Optional[bool]:
    try:
        async with AFFILIATE_SETTINGS_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateSettings).where(
                        AffiliateSettings.affiliate_user == affiliate_user)
                    aff_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    if not aff_user:
                        return None
                    aff_user.earnings = aff_user.earnings + earnings
                    return True
    except SQLAlchemyError as sqex:
        logger.error(
            f'Failed to modify balance for affiliate_user: {affiliate_user}, by XTR: {earnings}\n\
Actual error: {sqex}')
        return False


async def fetch_affiliate_settings_by_code(
        affiliate_code: str) -> Optional[AffiliateSettings]:
    try:
        async with AFFILIATE_SETTINGS_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateSettings).where(
                        AffiliateSettings.affiliate_code == affiliate_code)
                    aff_set = (
                        await session.execute(statement)).scalar_one_or_none()
                    return aff_set
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while fetching AffiliateSettings with affiliate_code: {affiliate_code}\n\
Actual error: {sqex}')


async def get_commission_info(
    affiliate_user: int
) -> Tuple[Optional[float], Optional[int], Optional[int]]:
    earnings, referred_users, total_users = 0.0, 0, 0
    try:
        async with AFFILIATE_USER_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateUsers).where(
                        AffiliateUsers.affiliate_user == affiliate_user)
                    ref_users = (await
                                 session.execute(statement)).scalars().all()
                    total_users = len(ref_users)
                    for ref_user in ref_users:
                        sub_user = (await get_all_transactions_user(
                            user_id=ref_user.referred_user))
                        if sub_user and sub_user[0]:
                            referred_users += 1
        async with AFFILIATE_SETTINGS_LOCK:
            async with async_session() as session:
                async with session.begin():
                    statement = select(AffiliateSettings).where(
                        AffiliateSettings.affiliate_user == affiliate_user)
                    aff_user = (
                        await session.execute(statement)).scalar_one_or_none()
                    if aff_user:
                        earnings = aff_user.earnings
        return earnings, referred_users, total_users
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while fetching commission and referred users info for affiliate_user: {affiliate_user}\n\
Actual error: {sqex}')
        return None, None, None


async def add_referral(affiliate_user_id: int, referred_user_id: int, amount_earned: float, short_id: str) -> bool:
    try:
        async with async_session() as session:
            async with session.begin():
                # Check if the referral already exists
                existing_referral = await session.execute(
                    select(Referrals).where(
                        Referrals.affiliate_user_id == affiliate_user_id,
                        Referrals.referred_user_id == referred_user_id
                    )
                )
                if existing_referral.scalar_one_or_none():
                    logger.info(f"Referral already exists for affiliate {affiliate_user_id} and user {referred_user_id}. No bonus awarded.")
                    return False  # The referral already exists; exit without creating a new entry

                # Create a new referral entry
                referral = Referrals(
                    affiliate_user_id=affiliate_user_id,
                    referred_user_id=referred_user_id,
                    amount_earned=amount_earned,
                    short_id=short_id
                )
                session.add(referral)
                await session.commit()
            logger.info(f'Referral added for affiliate_user_id={affiliate_user_id}, referred_user_id={referred_user_id}.')
            return True  # New referral added
    except SQLAlchemyError as sqex:
        logger.error(f'Failed to add referral for affiliate_user_id: {affiliate_user_id}, referred_user_id: {referred_user_id}, amount_earned: {amount_earned}, short_id: {short_id}\nActual error: {sqex}')
        return False

async def get_referral_by_short_id(short_id: str) -> Optional[Referrals]:
    try:
        async with async_session() as session:
            async with session.begin():
                statement = select(Referrals).where(Referrals.short_id == short_id)
                referral = (await session.execute(statement)).scalar_one_or_none()
                return referral
    except SQLAlchemyError as sqex:
        logger.error(
            f'Error while fetching referral by short_id: {short_id}\n\
Actual error: {sqex}')
        return None