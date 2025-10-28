from aiogram.types import InlineKeyboardButton

compose_route_button = InlineKeyboardButton(text="🗺️ Составить маршрут", callback_data="compose_route")
remake_route_button = InlineKeyboardButton(text="🔄 Составить новый маршрут", callback_data="remake_route")
yes_button = InlineKeyboardButton(text="✅ Да, верно", callback_data="confirm_location_yes")
no_button = InlineKeyboardButton(text="❌ Нет, ввести заново", callback_data="confirm_location_no")
confirm_time_yes = InlineKeyboardButton(text="✅ Да, уверен", callback_data="confirm_time_yes")
confirm_time_no = InlineKeyboardButton(text="🕒 Нет, ввести другое время", callback_data="confirm_time_no")
show_all_descriptions_button = InlineKeyboardButton(text="Узнать подробнее", callback_data="show_all_descriptions")
open_2gis_map_button_text = "Открыть карту 2GIS"
close_description_button = InlineKeyboardButton(text="Закрыть описание", callback_data="close_description")
navigate_back_button_text = "< Назад"
navigate_forward_button_text = "Вперед >"
