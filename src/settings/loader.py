# -*- coding: utf-8 -*-

"""
Модуль для инициализации и загрузки основных компонентов Telegram бота: Bot и Dispatcher.
Использует переменные окружения для получения токена бота.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import os


# --------------------------------------------------------------------------
# Функции загрузки компонентов бота
# --------------------------------------------------------------------------

def load_dispatcher() -> Dispatcher:
    """
    Инициализирует и возвращает объект Dispatcher.
    Использует MemoryStorage для хранения состояний FSM.

    :return: Экземпляр Dispatcher.
    """
    return Dispatcher(storage=MemoryStorage())


def load_bot() -> Bot:
    """
    Загружает токен бота из переменных окружения и инициализирует объект Bot.

    :return: Экземпляр Bot.
    """
    load_dotenv() # Загрузка переменных окружения из файла .env
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN не найден в переменных окружения. Убедитесь, что .env файл настроен правильно.")
    return Bot(token=bot_token)