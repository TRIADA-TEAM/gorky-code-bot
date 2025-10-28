# -*- coding: utf-8 -*-

"""
Главный файл запуска бота.
Этот файл отвечает за инициализацию и запуск бота.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import asyncio
import logging
import sys

from dotenv import load_dotenv

from src.handlers.callbacks import callback_router
from src.settings.loader import load_dispatcher, load_bot
from src.handlers.commands import commands_router
from src.handlers.handlers import handlers_router
from src.ai.route_logic import create_index


# --------------------------------------------------------------------------
# Асинхронная функция main
# --------------------------------------------------------------------------

async def main() -> None:
    """
    Главная асинхронная функция для запуска бота.
    - Устанавливает логирование.
    - Загружает переменные окружения.
    - Создает индекс для поиска.
    - Загружает диспетчер и бота.
    - Подключает роутеры для команд, обработчиков и колбэков.
    - Запускает опрос (polling) для получения обновлений от Telegram.
    """
    logging.info("Бот запущен")
    load_dotenv()
    create_index()
    dp = load_dispatcher()
    bot = load_bot()
    dp.include_router(commands_router)
    dp.include_router(handlers_router)
    dp.include_router(callback_router)
    await dp.start_polling(bot)


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------

if __name__ == "__main__":
    """
    Точка входа в программу.
    - Настраивает базовую конфигурацию логирования.
    - Запускает асинхронную функцию main.
    """
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())