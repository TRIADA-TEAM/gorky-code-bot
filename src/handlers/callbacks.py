# -*- coding: utf-8 -*-

"""
Модуль содержит обработчики для Inline-кнопок (CallbackQuery).
Отвечает за обработку действий, связанных с формированием маршрута, подтверждением данных
и навигацией по описаниям мест.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import re
from typing import List, Optional, Any

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext

from src.content import messages, keyboards, buttons
from src.settings.classes import UserState
from src.handlers.handlers import _generate_and_send_route
from src.ai.route_logic import RouteBuilder


# --------------------------------------------------------------------------
# Инициализация роутера и компонентов
# --------------------------------------------------------------------------

callback_router = Router()
route_builder = RouteBuilder() # Экземпляр RouteBuilder для доступа к логике маршрутов


# --------------------------------------------------------------------------
# Обработчики колбэков для формирования маршрута
# --------------------------------------------------------------------------

@callback_router.callback_query(F.data == "compose_route")
async def compose_route_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает нажатие кнопки "Составить маршрут".
    Запрашивает у пользователя интересы и переводит в соответствующее состояние.

    :param callback_query: Объект CallbackQuery при нажатии кнопки.
    :param state: Текущее состояние FSMContext.
    """
    await callback_query.answer() # Убираем индикатор загрузки на кнопке
    if callback_query.message:
        await callback_query.message.answer(messages.INTERESTS_MESSAGE)
        await state.set_state(UserState.Interests)


@callback_router.callback_query(F.data == "remake_route")
async def remake_route_callback(callback_query: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает нажатие кнопки "Пересоставить маршрут".
    Очищает предыдущую клавиатуру, уведомляет пользователя и начинает процесс составления маршрута заново.

    :param callback_query: Объект CallbackQuery при нажатии кнопки.
    :param state: Текущее состояние FSMContext.
    """
    await callback_query.answer()
    if callback_query.message:
        await callback_query.message.edit_reply_markup(reply_markup=None) # Убираем клавиатуру под сообщением
        await callback_query.message.answer(messages.REMAKE_ROUTE_MESSAGE)
        await state.set_state(UserState.Interests)


# --------------------------------------------------------------------------
# Обработчики колбэков для подтверждения времени
# --------------------------------------------------------------------------

@callback_router.callback_query(UserState.ConfirmTime, F.data == "confirm_time_yes")
async def confirm_time_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает подтверждение пользователем большого промежутка времени.
    Переводит пользователя в состояние ожидания местоположения.

    :param callback: Объект CallbackQuery при нажатии кнопки "Да".
    :param state: Текущее состояние FSMContext.
    """
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(messages.LOCATION_MESSAGE, reply_markup=keyboards.location_keyboard)
        await state.set_state(UserState.Location)
    await callback.answer()


@callback_router.callback_query(UserState.ConfirmTime, F.data == "confirm_time_no")
async def confirm_time_no(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает отказ пользователя от большого промежутка времени.
    Заново запрашивает время.

    :param callback: Объект CallbackQuery при нажатии кнопки "Нет".
    :param state: Текущее состояние FSMContext.
    """
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(messages.TIME_MESSAGE)
        await state.set_state(UserState.Time)
    await callback.answer()


# --------------------------------------------------------------------------
# Обработчики колбэков для подтверждения местоположения
# --------------------------------------------------------------------------

@callback_router.callback_query(UserState.ConfirmLocation, F.data == "confirm_location_yes")
async def confirm_location_yes(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает подтверждение пользователем выбранного местоположения.
    Запускает процесс генерации и отправки маршрута.

    :param callback: Объект CallbackQuery при нажатии кнопки "Да".
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    await callback.answer()
    user_data = await state.get_data()
    location: Optional[Any] = user_data.get('confirmed_location')
    if callback.message:
        if location:
            await callback.message.edit_reply_markup(reply_markup=None)
            await _generate_and_send_route(callback.message, state, location, bot)
        else:
            await callback.message.answer(messages.LOCATION_NOT_FOUND_MESSAGE)
            await state.set_state(UserState.Location)


@callback_router.callback_query(UserState.ConfirmLocation, F.data == "confirm_location_no")
async def confirm_location_no(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обрабатывает отказ пользователя от выбранного местоположения.
    Заново запрашивает местоположение.

    :param callback: Объект CallbackQuery при нажатии кнопки "Нет".
    :param state: Текущее состояние FSMContext.
    """
    await callback.answer()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(messages.LOCATION_REPEAT_MESSAGE, reply_markup=keyboards.location_keyboard)
        await state.set_state(UserState.Location)


# --------------------------------------------------------------------------
# Обработчики колбэков для навигации по описаниям мест
# --------------------------------------------------------------------------

@callback_router.callback_query(F.data == "show_all_descriptions")
async def show_all_descriptions_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает нажатие кнопки "Показать описания объектов".
    Начинает показ описаний мест маршрута.

    :param callback_query: Объект CallbackQuery.
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    await callback_query.answer()
    user_data = await state.get_data()
    place_ids: List[int] = user_data.get('route_place_ids', [])
    route_message_id: Optional[int] = user_data.get('route_message_id')

    if not callback_query.message:
        return

    if not place_ids:
        await callback_query.message.answer("Не удалось найти объекты для отображения.")
        return

    current_index = 0
    await state.update_data(current_description_index=current_index)

    # Обновление клавиатуры под сообщением с маршрутом
    if route_message_id:
        original_keyboard_markup: Optional[InlineKeyboardMarkup] = callback_query.message.reply_markup
        if original_keyboard_markup:
            new_inline_keyboard = []
            for row in original_keyboard_markup.inline_keyboard:
                new_row = []
                for button in row:
                    if button.callback_data == "show_all_descriptions":
                        new_row.append(buttons.close_description_button)
                    else:
                        new_row.append(button)
                new_inline_keyboard.append(new_row)
            
            await bot.edit_message_reply_markup(
                chat_id=callback_query.message.chat.id,
                message_id=route_message_id,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=new_inline_keyboard)
            )

    # Отправка первого описания
    await _send_place_description(callback_query.message, state, place_ids, current_index, bot, message_to_edit_id=None)


@callback_router.callback_query(F.data.startswith("navigate_description_"))
async def navigate_description_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает навигацию между описаниями мест (кнопки 'Вперед'/'Назад').

    :param callback_query: Объект CallbackQuery с данными навигации.
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    await callback_query.answer()
    user_data = await state.get_data()
    place_ids: List[int] = user_data.get('route_place_ids', [])
    
    if not callback_query.message:
        return

    # Извлекаем индекс из callback_data
    try:
        current_index = int(callback_query.data.split("_")[2])
    except (IndexError, ValueError):
        await callback_query.message.answer("Ошибка навигации по описаниям: некорректные данные.")
        return

    message_to_edit_id: Optional[int] = user_data.get('current_description_message_id')

    if not place_ids or not (0 <= current_index < len(place_ids)):
        await callback_query.message.answer("Ошибка навигации по описаниям: объекты не найдены или индекс вне диапазона.")
        return

    await state.update_data(current_description_index=current_index)
    # Отправляем (или редактируем) сообщение с новым описанием
    await _send_place_description(callback_query.message, state, place_ids, current_index, bot, message_to_edit_id=message_to_edit_id)


@callback_router.callback_query(F.data == "close_description")
async def close_description_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """
    Обрабатывает нажатие кнопки "Скрыть описания".
    Удаляет сообщение с описанием и восстанавливает исходную клавиатуру маршрута.

    :param callback_query: Объект CallbackQuery.
    :param state: Текущее состояние FSMContext.
    :param bot: Объект бота.
    """
    await callback_query.answer()
    user_data = await state.get_data()
    description_message_id: Optional[int] = user_data.get('current_description_message_id')
    route_message_id: Optional[int] = user_data.get('route_message_id')

    if not callback_query.message:
        return

    if description_message_id:
        try:
            await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=description_message_id)
            await state.update_data(current_description_message_id=None)
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения с описанием: {e}")

    # Восстановление оригинальной клавиатуры маршрута
    if route_message_id:
        original_keyboard_markup: Optional[InlineKeyboardMarkup] = callback_query.message.reply_markup
        if original_keyboard_markup:
            new_inline_keyboard = []
            for row in original_keyboard_markup.inline_keyboard:
                new_row = []
                for button in row:
                    if button.callback_data == "close_description":
                        new_row.append(buttons.show_all_descriptions_button)
                    else:
                        new_row.append(button)
                new_inline_keyboard.append(new_row)
            
            try:
                await bot.edit_message_reply_markup(
                    chat_id=callback_query.message.chat.id,
                    message_id=route_message_id,
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=new_inline_keyboard)
                )
            except Exception as e:
                logging.error(f"Ошибка при восстановлении клавиатуры маршрута: {e}")


# --------------------------------------------------------------------------
# Вспомогательная функция для отправки описания места
# --------------------------------------------------------------------------

async def _send_place_description(
    message: Message,
    state: FSMContext,
    place_ids: List[int],
    current_index: int,
    bot: Bot,
    message_to_edit_id: Optional[int] = None
) -> None:
    """
    Отправляет описание конкретного места из маршрута с кнопками навигации.

    :param message: Объект сообщения для ответа.
    :param state: Текущее состояние FSMContext.
    :param place_ids: Список ID мест в маршруте.
    :param current_index: Текущий индекс отображаемого места.
    :param bot: Объект бота.
    :param message_to_edit_id: ID сообщения, которое нужно отредактировать (для навигации).
    """
    if not place_ids or not (0 <= current_index < len(place_ids)):
        await message.answer("Ошибка: Неверный индекс или пустой список мест для описания.")
        return

    place_id = place_ids[current_index]
    place = route_builder.get_place_by_id(place_id)

    if place and place.get('description'):
        # Удаляем HTML-теги из описания
        full_description = re.sub('<[^<]+?>', '', str(place['description']))
        text = f"{place['title']}:\n\n{full_description}"

        keyboard_buttons: List[InlineKeyboardButton] = []
        # Добавляем кнопку "Назад", если это не первое описание
        if current_index > 0:
            keyboard_buttons.append(InlineKeyboardButton(text=buttons.navigate_back_button_text, callback_data=f"navigate_description_{current_index - 1}"))
        # Добавляем кнопку "Вперед", если это не последнее описание
        if current_index < len(place_ids) - 1:
            keyboard_buttons.append(InlineKeyboardButton(text=buttons.navigate_forward_button_text, callback_data=f"navigate_description_{current_index + 1}"))
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[keyboard_buttons])

        # Редактируем или отправляем новое сообщение с описанием
        if message_to_edit_id:
            try:
                await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_to_edit_id, reply_markup=reply_markup)
            except Exception as e:
                logging.error(f"Ошибка при редактировании сообщения с описанием: {e}")
                sent_message = await message.answer(text, reply_markup=reply_markup)
                await state.update_data(current_description_message_id=sent_message.message_id)
        else:
            sent_message = await message.answer(text, reply_markup=reply_markup)
            await state.update_data(current_description_message_id=sent_message.message_id)
    else:
        await message.answer("Описание не найдено.")
