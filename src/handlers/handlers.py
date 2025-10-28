# -*- coding: utf-8 -*- 

"""
Модуль содержит основные обработчики сообщений пользователя, не являющихся командами или колбэками.
Обрабатывает ввод интересов, времени и местоположения, а также генерирует маршруты.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import logging
import os
import re

from aiogram import F, Router, Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from geopy.geocoders import Nominatim

from src.ai.route_logic import RouteBuilder
from content import messages, keyboards, buttons
from src.settings.classes import UserState


# --------------------------------------------------------------------------
# Инициализация роутера
# --------------------------------------------------------------------------

handlers_router = Router(name=__name__)


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def split_message(text: str, chunk_size: int = 4096) -> list[str]:
    """
    Разбивает длинное текстовое сообщение на части, чтобы оно соответствовало ограничению Telegram
    на длину сообщения (4096 символов).

    :param text: Исходный текст сообщения.
    :param chunk_size: Максимальный размер одной части сообщения (по умолчанию 4096).
    :return: Список строк, каждая из которых не превышает chunk_size.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    while len(text) > 0:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        
        # Ищем ближайший перенос строки, чтобы не разрывать слова
        split_pos = text.rfind('\n', 0, chunk_size)
        if split_pos == -1:
            split_pos = chunk_size # Если переноса строки нет, обрезаем по chunk_size
            
        chunks.append(text[:split_pos])
        text = text[split_pos:]
        
    return chunks


async def _generate_and_send_route(message: Message, state: FSMContext, location, bot: Bot):
    """
    Генерирует маршрут на основе данных пользователя и отправляет его в чат.

    :param message: Объект сообщения пользователя.
    :param state: Текущее состояние FSMContext.
    :param location: Объект местоположения (геокодированный адрес).
    :param bot: Объект бота.
    """
    await message.answer(messages.ROUTE_GENERATION_MESSAGE, reply_markup=ReplyKeyboardRemove())
    route_builder = RouteBuilder()

    user_data = await state.get_data()
    interests = user_data.get('interests')
    time = user_data.get('time')

    # Генерация маршрута с помощью RouteBuilder
    generated_route_text, retrieved_docs, reply_markup, place_ids, notification = await route_builder.generate_route(interests, time, location)

    if notification:
        await message.answer(notification)

    await state.update_data(route_place_ids=place_ids)

    # Отправка маршрута по частям, если он слишком длинный
    message_chunks = split_message(generated_route_text)
    for i, chunk in enumerate(message_chunks):
        if i == len(message_chunks) - 1:
            # Последняя часть сообщения содержит клавиатуру
            sent_route_message = await message.answer(
                chunk,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            await state.update_data(route_message_id=sent_route_message.message_id)
        else:
            # Промежуточные части сообщения
            await message.answer(
                chunk,
                parse_mode=ParseMode.MARKDOWN
            )


# --------------------------------------------------------------------------
# Обработчики состояний FSM
# --------------------------------------------------------------------------

@handlers_router.message(UserState.Interests)
async def process_interests(message: Message, state: FSMContext):
    """
    Обрабатывает введенные пользователем интересы.
    Сохраняет интересы и переводит пользователя в состояние ожидания времени.

    :param message: Объект сообщения с интересами пользователя.
    :param state: Текущее состояние FSMContext.
    """
    await state.update_data(interests=message.text)
    await message.answer(messages.TIME_MESSAGE)
    await state.set_state(UserState.Time)


@handlers_router.message(UserState.Time)
async def process_time(message: Message, state: FSMContext):
    """
    Обрабатывает введенное пользователем время.
    Валидирует время, сохраняет его и переводит пользователя в следующее состояние
    или запрашивает подтверждение, если время слишком большое.

    :param message: Объект сообщения со временем от пользователя.
    :param state: Текущее состояние FSMContext.
    """
    time_str = message.text.replace(',', '.')
    match = re.search(r'\d+[.]?\d*', time_str)

    if match:
        try:
            time_hours = float(match.group(0))
            
            if time_hours <= 0:
                await message.answer(messages.TIME_POSITIVE_ERROR)
                return
            
            if time_hours > 16:
                await message.answer(messages.TIME_TOO_LONG_ERROR)
                return

            await state.update_data(time=str(time_hours))

            if time_hours > 8:
                # Запрос подтверждения, если время превышает 8 часов
                builder = InlineKeyboardBuilder()
                builder.add(buttons.confirm_time_yes)
                builder.add(buttons.confirm_time_no)
                await message.answer(messages.TIME_TOO_LONG_CONFIRM.format(time_hours=time_hours), reply_markup=builder.as_markup())
                await state.set_state(UserState.ConfirmTime)
            else:
                # Переход к запросу местоположения
                await message.answer(messages.LOCATION_MESSAGE, reply_markup=keyboards.location_keyboard)
                await state.set_state(UserState.Location)

        except ValueError:
            await message.answer(messages.TIME_PARSE_ERROR)
            return
    else:
        await message.answer(messages.TIME_NOT_FOUND_ERROR)
        return


@handlers_router.message(UserState.Location, F.text)
async def process_manual_location(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает введенное пользователем текстовое местоположение.
    Использует Nominatim для геокодирования и запрашивает подтверждение.

    :param message: Объект сообщения с текстовым местоположением.
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    geolocator = Nominatim(user_agent="guide-bot-2", timeout=10)

    # Добавляем "Нижний Новгород" к запросу, если пользователь его не указал
    if "нижний новгород" in message.text.lower():
        location = geolocator.geocode(message.text)
    else:
        location = geolocator.geocode("Нижний Новгород, " + message.text)
    
    logging.info(f"Локация: {location}")

    if location:
        await state.update_data(confirmed_location=location)
        builder = InlineKeyboardBuilder()
        builder.add(buttons.yes_button)
        builder.add(buttons.no_button)
        await message.answer(messages.CONFIRM_LOCATION_MESSAGE.format(address=location.address), reply_markup=builder.as_markup())
        await state.set_state(UserState.ConfirmLocation)
    else:
        await message.answer(messages.LOCATION_NOT_FOUND_MESSAGE)


@handlers_router.message(UserState.Location, F.location)
async def process_location(message: Message, state: FSMContext, bot: Bot):
    """
    Обрабатывает отправленное пользователем местоположение (геолокацию).
    Использует Nominatim для обратного геокодирования и запрашивает подтверждение.

    :param message: Объект сообщения с геолокацией.
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    if message.location:
        geolocator = Nominatim(user_agent="guide-bot-2", timeout=10)
        location = geolocator.reverse((message.location.latitude, message.location.longitude), exactly_one=True)
        if location:
            await state.update_data(confirmed_location=location)
            builder = InlineKeyboardBuilder()
            builder.add(buttons.yes_button)
            builder.add(buttons.no_button)
            await message.answer(messages.CONFIRM_LOCATION_MESSAGE.format(address=location.address), reply_markup=builder.as_markup())
            await state.set_state(UserState.ConfirmLocation)
        else:
            await message.answer(messages.LOCATION_NOT_FOUND_MESSAGE)
    else:
        await message.answer(messages.GEOLOCATION_ERROR_MESSAGE)