from aiogram.fsm.state import StatesGroup, State
from enum import Enum


class UserState(StatesGroup):
    Interests = State()
    Time = State()
    ConfirmTime = State()
    Location = State()
    ConfirmLocation = State()


class FileType(Enum):
    DOCUMENT = "document"
    PHOTO = "photo"
    VIDEO = "video"
    AUDIO = "audio"
    STICKER = "sticker"
