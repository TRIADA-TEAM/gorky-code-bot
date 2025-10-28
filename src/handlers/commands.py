# -*- coding: utf-8 -*-

"""
Модуль содержит обработчики команд Telegram бота, таких как /start.
Отвечает за начальное взаимодействие с пользователем и запуск процесса составления маршрута.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import logging

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from src.content import messages, buttons


# --------------------------------------------------------------------------
# Инициализация роутера
# --------------------------------------------------------------------------

commands_router = Router(name=__name__)


# --------------------------------------------------------------------------
# Обработчики команд
# --------------------------------------------------------------------------

@commands_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    """
    Обрабатывает команду /start.
    Отправляет приветственное сообщение и предлагает начать составление маршрута
    с помощью Inline-кнопки.

    :param message: Объект сообщения с командой /start.
    :param state: Текущее состояние FSMContext.
    """
    builder = InlineKeyboardBuilder()
    builder.add(buttons.compose_route_button) # Добавляем кнопку "Составить маршрут"
    
    # Отправляем приветственное сообщение, убирая Reply-клавиатуру, если она была
    await message.answer(
        messages.GREETING_MESSAGE,
        reply_markup=ReplyKeyboardRemove()
    )
    # Отправляем сообщение с предложением составить маршрут и Inline-кнопкой
    await message.answer(
        messages.START_ROUTE_MESSAGE,
        reply_markup=builder.as_markup()
    )