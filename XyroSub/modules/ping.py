import time

from pyrogram import filters
from pyrogram.client import Client
from pyrogram.types import Message


@Client.on_message(filters.command("ping"))  # type: ignore
async def ping(_, message: Message):
    start_t = time.time()
    rm = await message.reply_text("...")  # type: ignore
    end_t = time.time()
    time_taken_s = (end_t - start_t) * 1000
    await rm.edit(f"Pong!\n{time_taken_s:.3f} ms")