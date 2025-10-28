# -*- coding: utf-8 -*-

"""
Модуль для работы с клавиатурами (ReplyKeyboardMarkup и InlineKeyboardMarkup) в Telegram боте.
Предоставляет функции для отображения, скрытия и создания различных типов клавиатур.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

from typing import List, Dict, Any, Optional
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton, Message


# --------------------------------------------------------------------------
# Функции для ReplyKeyboardMarkup
# --------------------------------------------------------------------------

async def show_keyboard(
    message: Message,
    text_message: str,
    keyboard: List[str],
    order: Optional[List[int]] = None,
    parse_mode: str = 'Markdown'
) -> None:
    """
    Отображает Reply-клавиатуру пользователю.

    :param message: Объект сообщения, на которое будет отправлена клавиатура.
    :param text_message: Текст сообщения, сопровождающего клавиатуру.
    :param keyboard: Список текстов кнопок для клавиатуры.
    :param order: Опциональный список, определяющий количество кнопок в каждом ряду.
                  Например, [2, 1] создаст два ряда: первый с двумя кнопками, второй с одной.
                  Если None, все кнопки будут в одном ряду.
    :param parse_mode: Режим парсинга текста сообщения (по умолчанию 'Markdown').
    """
    keyboard_layout: List[List[KeyboardButton]] = []
    current_button_index = 0

    if order is None:
        # Если порядок не задан, все кнопки в одном ряду
        keyboard_layout.append([KeyboardButton(text=btn_text) for btn_text in keyboard])
    else:
        # Формирование раскладки клавиатуры согласно заданному порядку
        for row_size in order:
            row: List[KeyboardButton] = []
            for _ in range(row_size):
                if current_button_index < len(keyboard):
                    row.append(KeyboardButton(text=keyboard[current_button_index]))
                    current_button_index += 1
            keyboard_layout.append(row)

    # Создание объекта ReplyKeyboardMarkup
    reply_keyboard = ReplyKeyboardMarkup(keyboard=keyboard_layout, resize_keyboard=True)
    # Отправка сообщения с клавиатурой
    await message.answer(text_message, reply_markup=reply_keyboard, parse_mode=parse_mode)


async def hide_keyboard(message: Message, text_message: str) -> None:
    """
    Скрывает Reply-клавиатуру у пользователя.

    :param message: Объект сообщения, на которое будет отправлено скрытие клавиатуры.
    :param text_message: Текст сообщения, сопровождающего скрытие клавиатуры.
    """
    await message.answer(text_message, reply_markup=ReplyKeyboardRemove())


# --------------------------------------------------------------------------
# Функции для InlineKeyboardMarkup
# --------------------------------------------------------------------------

def get_inline_keyboard(buttons_data: List[List[Dict[str, str]]]) -> InlineKeyboardMarkup:
    """
    Создает Inline-клавиатуру на основе переданного списка кнопок.

    :param buttons_data: Список списков словарей, где каждый словарь представляет кнопку
                         и содержит ключи 'text' (текст кнопки) и 'callback_data' (данные колбэка).
                         Пример: [[{'text': 'Кнопка 1', 'callback_data': 'data1'}], ...] 
    :return: Объект InlineKeyboardMarkup.
    """
    inline_keyboard_buttons: List[List[InlineKeyboardButton]] = []

    # Итерация по рядам кнопок
    for row_data in buttons_data:
        row_buttons: List[InlineKeyboardButton] = []
        # Итерация по кнопкам в текущем ряду
        for button_data in row_data:
            row_buttons.append(
                InlineKeyboardButton(
                    text=button_data["text"],
                    callback_data=button_data["callback_data"]
                )
            )
        inline_keyboard_buttons.append(row_buttons)

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard_buttons)
