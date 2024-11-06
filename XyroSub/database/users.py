import datetime
from typing import List, Optional, Tuple

from sqlalchemy import (BigInteger, Boolean, Column, Float, Integer, String,
                        and_, select)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from XyroSub import SCHEMA, logger
from XyroSub.database import BASE

engine = create_async_engine(SCHEMA, echo=False)
async_session = async_sessionmaker(bind=engine,
                                   autoflush=True,
                                   expire_on_commit=False)


class Users(BASE):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    user_id = Column(BigInteger, nullable=False, unique=True)
    first_seen = Column(Float,
                        default=datetime.datetime.now(
                            datetime.timezone.utc).timestamp())

    def __init__(self, user_id: int):
        self.user_id = user_id

    def __repr__(self):
        return f"<Users  user_id={self.user_id}>"


class Blacklist(BASE):
    __tablename__ = 'blacklist'

    user_id = Column(BigInteger, primary_key=True, nullable=False)
    blacklisted = Column(Boolean, nullable=False, default=False)
    refund_used = Column(Boolean, nullable=False, default=False)

    def __init__(self, user_id, blacklisted=False, refund_used=False):
        self.user_id = user_id
        self.blacklisted = blacklisted
        self.refund_used = refund_used


class InviteLink(BASE):
    __tablename__ = 'invite_links'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, unique=True)
    invite_link = Column(String, nullable=False)

    def __init__(self, user_id: int, invite_link: str):
        self.user_id = user_id
        self.invite_link = invite_link

    def __repr__(self):
        return f"<InviteLink user_id={self.user_id}, link={self.invite_link}>"
    
async def create_user(user_id: int):
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Users).where(
                    and_(Users.user_id == user_id)))
            existing_user = result.scalar_one_or_none()

            if existing_user:
                logger.info(
                    f"User {user_id} already exists in chat")
                return existing_user

            new_user = Users(user_id=user_id)
            session.add(new_user)
            await session.commit()
            logger.info(
                f"User created for user_id={user_id}")
            return new_user


async def set_blacklist_status(user_id: int, status: bool):
    async with async_session() as session:
        async with session.begin():
            query = await session.execute(
                select(Blacklist).where(Blacklist.user_id == user_id))
            entry = query.scalar_one_or_none()
            if entry:
                entry.blacklisted = status
            else:
                new_entry = Blacklist(user_id=user_id, blacklisted=status)
                session.add(new_entry)
            await session.commit()


async def is_user_blacklisted(user_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(
                select(Blacklist).where(Blacklist.user_id == user_id))
            entry = result.scalar_one_or_none()
            return entry.blacklisted if entry else False


async def check_refund_eligibility(user_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            query = await session.execute(
                select(Blacklist).where(Blacklist.user_id == user_id))
            entry = query.scalar_one_or_none()

            if not entry:
                return True

            return not entry.refund_used


async def mark_refund_used(user_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            query = await session.execute(
                select(Blacklist).where(Blacklist.user_id == user_id))
            entry = query.scalar_one_or_none()

            if entry:
                if entry.refund_used:
                    return False

                entry.refund_used = True
                await session.commit()
                return True

            new_entry = Blacklist(user_id=user_id, refund_used=True)
            session.add(new_entry)
            await session.commit()
            return True


async def get_users_info_user(user_id: int) -> List[Tuple[Users]]:
    async with async_session() as session:
        async with session.begin():
            statement = select(Users).where(Users.user_id == user_id)
            results = await session.execute(statement)
            return results.all()

async def create_invite_link(user_id: int, invite_link: str):
    async with async_session() as session:
        async with session.begin():
            existing_entry = await session.get(InviteLink, user_id)
            
            if existing_entry:
                existing_entry.invite_link = invite_link
                logger.info(f"Invite link updated for user_id={user_id}")
            else:
                invite_entry = InviteLink(user_id=user_id, invite_link=invite_link)
                session.add(invite_entry)
                logger.info(f"Invite link created for user_id={user_id}")

            await session.commit()

async def get_invite_link(user_id: int) -> Optional[InviteLink]:
    async with async_session() as session:
        async with session.begin():
            result = await session.execute(select(InviteLink).where(InviteLink.user_id == user_id))
            return result.scalar_one_or_none()

async def delete_invite_link(user_id: int) -> bool:
    async with async_session() as session:
        async with session.begin():
            query = await session.execute(select(InviteLink).where(InviteLink.user_id == user_id))
            invite_entry = query.scalar_one_or_none()

            if invite_entry:
                await session.delete(invite_entry)
                await session.commit()
                logger.info(f"Invite link deleted for user_id={user_id}")
                return True
            return False
