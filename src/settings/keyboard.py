# -*- coding: utf-8 -*-

"""
Модуль для работы с клавиатурами (ReplyKeyboardMarkup и InlineKeyboardMarkup) в Telegram боте.
Предоставляет функции для отображения, скрытия и создания различных типов клавиатур.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, \
    InlineKeyboardButton


# --------------------------------------------------------------------------
# Функции для ReplyKeyboardMarkup
# --------------------------------------------------------------------------

async def show_keyboard(message, text_message, keyboard, order=None, parse_mode='Markdown'):
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
    keyboard_layout = []
    index = 0
    # Формирование раскладки клавиатуры согласно заданному порядку
    for row_size in order:
        row = []
        for _ in range(row_size):
            if index < len(keyboard):
                row.append(KeyboardButton(text=keyboard[index]))
                index += 1
        keyboard_layout.append(row)
    # Создание объекта ReplyKeyboardMarkup
    reply_keyboard = ReplyKeyboardMarkup(keyboard=keyboard_layout, resize_keyboard=True)
    # Отправка сообщения с клавиатурой
    await message.answer(text_message, reply_markup=reply_keyboard, parse_mode=parse_mode)


async def hide_keyboard(message, text_message):
    """
    Скрывает Reply-клавиатуру у пользователя.

    :param message: Объект сообщения, на которое будет отправлено скрытие клавиатуры.
    :param text_message: Текст сообщения, сопровождающего скрытие клавиатуры.
    """
    await message.answer(text_message, reply_markup=ReplyKeyboardRemove())


# --------------------------------------------------------------------------
# Функции для InlineKeyboardMarkup
# --------------------------------------------------------------------------

def get_inline_keyboard(buttons: list[list[dict[str, str]]]) -> InlineKeyboardMarkup:
    """
    Создает Inline-клавиатуру на основе переданного списка кнопок.

    :param buttons: Список списков словарей, где каждый словарь представляет кнопку
                    и содержит ключи 'text' (текст кнопки) и 'callback_data' (данные колбэка).
                    Пример: [[{'text': 'Кнопка 1', 'callback_data': 'data1'}], ...]
    :return: Объект InlineKeyboardMarkup.
    """
    keyboard_buttons = []

    # Итерация по рядам кнопок
    for row in buttons:
        row_buttons = []
        # Итерация по кнопкам в текущем ряду
        for button in row:
            row_buttons.append(
                InlineKeyboardButton(
                    text=button["text"],
                    callback_data=button["callback_data"]
                )
            )
        keyboard_buttons.append(row_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)