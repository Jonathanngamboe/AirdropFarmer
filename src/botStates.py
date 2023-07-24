# botStates.py

from aiogram.dispatcher.filters.state import State, StatesGroup

class BotStates(StatesGroup):
    waiting_for_referral_code = State()
