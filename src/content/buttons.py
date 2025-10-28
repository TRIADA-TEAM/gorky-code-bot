# -*- coding: utf-8 -*-

"""
Модуль содержит предопределенные Inline-кнопки для использования в Telegram боте.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

from aiogram.types import InlineKeyboardButton


# --------------------------------------------------------------------------
# Inline-кнопки для действий
# --------------------------------------------------------------------------

compose_route_button = InlineKeyboardButton(text="🗺️ Составить маршрут", callback_data="compose_route")
remake_route_button = InlineKeyboardButton(text="🔄 Составить новый маршрут", callback_data="remake_route")


# --------------------------------------------------------------------------
# Inline-кнопки для подтверждения местоположения
# --------------------------------------------------------------------------

yes_button = InlineKeyboardButton(text="✅ Да, верно", callback_data="confirm_location_yes")
no_button = InlineKeyboardButton(text="❌ Нет, ввести заново", callback_data="confirm_location_no")


# --------------------------------------------------------------------------
# Inline-кнопки для подтверждения времени
# --------------------------------------------------------------------------

confirm_time_yes = InlineKeyboardButton(text="✅ Да, уверен", callback_data="confirm_time_yes")
confirm_time_no = InlineKeyboardButton(text="🕒 Нет, ввести другое время", callback_data="confirm_time_no")


# --------------------------------------------------------------------------
# Inline-кнопки для описаний и навигации по маршруту
# --------------------------------------------------------------------------

show_all_descriptions_button = InlineKeyboardButton(text="Узнать подробнее", callback_data="show_all_descriptions")
open_2gis_map_button_text = "Открыть карту 2GIS" # Текст для кнопки, URL будет динамическим
close_description_button = InlineKeyboardButton(text="Закрыть описание", callback_data="close_description")
navigate_back_button_text = "< Назад"
navigate_forward_button_text = "Вперед >"