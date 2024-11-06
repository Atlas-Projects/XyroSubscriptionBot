import asyncio
from typing import Optional, Tuple

from sqlalchemy import BigInteger, Column, Float, String, select
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
