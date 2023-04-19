from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode
from aiogram.utils import executor
from aiogram.utils.markdown import text, quote_html
from config import settings
import logging

logging.basicConfig(level=logging.INFO)

TOKEN = settings.TELEGRAM_TOKEN

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())


async def on_startup(dp):
    await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text="Bot has been started")


async def on_shutdown(dp):
    await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text="Bot has been stopped")

    await bot.session.close()
    await dp.storage.close()
    await dp.storage.wait_closed()


async def cmd_start(message: types.Message):
    start_message = "Welcome to the Airdrop Farming Bot! Here are the available actions:\n\n"
    action_list = [
        "/action1 - Description of action 1",
        "/action2 - Description of action 2",
        "/action3 - Description of action 3",
    ]

    for action in action_list:
        start_message += action + "\n"

    await message.reply(start_message)


async def cmd_action1(message: types.Message):
    # Code to execute action 1
    await message.reply("Action 1 executed")


async def cmd_action2(message: types.Message):
    # Code to execute action 2
    await message.reply("Action 2 executed")


async def cmd_action3(message: types.Message):
    # Code to execute action 3
    await message.reply("Action 3 executed")


def register_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start", "help"])
    dp.register_message_handler(cmd_action1, commands=["action1"])
    dp.register_message_handler(cmd_action2, commands=["action2"])
    dp.register_message_handler(cmd_action3, commands=["action3"])


if __name__ == "__main__":
    from aiogram import executor

    register_handlers(dp)
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
