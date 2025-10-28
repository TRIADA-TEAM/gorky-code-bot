from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
import re
from typing import List

from content import messages, keyboards, buttons
from src.settings.classes import UserState
from src.handlers.handlers import _generate_and_send_route
from src.ai.route_logic import RouteBuilder

callback_router = Router()
route_builder = RouteBuilder()


@callback_router.callback_query(F.data == "compose_route")
async def compose_route_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.answer(messages.INTERESTS_MESSAGE)
    await state.set_state(UserState.Interests)


@callback_router.callback_query(F.data == "remake_route")
async def remake_route_callback(callback_query: CallbackQuery, state: FSMContext):
    await callback_query.answer()
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.answer(messages.REMAKE_ROUTE_MESSAGE)
    await state.set_state(UserState.Interests)


@callback_router.callback_query(UserState.ConfirmTime, F.data == "confirm_time_yes")
async def confirm_time_yes(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(messages.LOCATION_MESSAGE, reply_markup=keyboards.location_keyboard)
    await state.set_state(UserState.Location)


@callback_router.callback_query(UserState.ConfirmTime, F.data == "confirm_time_no")
async def confirm_time_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(messages.TIME_MESSAGE)
    await state.set_state(UserState.Time)


@callback_router.callback_query(UserState.ConfirmLocation, F.data == "confirm_location_yes")
async def confirm_location_yes(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_data = await state.get_data()
    location = user_data.get('confirmed_location')
    if location:
        await callback.message.edit_reply_markup(reply_markup=None)
        await _generate_and_send_route(callback.message, state, location, bot)
    else:
        await callback.message.answer(messages.LOCATION_NOT_FOUND_MESSAGE)
        await state.set_state(UserState.Location)


@callback_router.callback_query(UserState.ConfirmLocation, F.data == "confirm_location_no")
async def confirm_location_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(messages.LOCATION_REPEAT_MESSAGE, reply_markup=keyboards.location_keyboard)
    await state.set_state(UserState.Location)


@callback_router.callback_query(F.data == "show_all_descriptions")
async def show_all_descriptions_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    user_data = await state.get_data()
    place_ids = user_data.get('route_place_ids', [])
    route_message_id = user_data.get('route_message_id')

    if not place_ids:
        await callback_query.message.answer("Не удалось найти объекты для отображения.")
        return

    current_index = 0
    await state.update_data(current_description_index=current_index)

    if route_message_id:
        original_keyboard = callback_query.message.reply_markup.inline_keyboard if callback_query.message.reply_markup else []
        new_keyboard = []
        for row in original_keyboard:
            new_row = []
            for button in row:
                if button.callback_data == "show_all_descriptions":
                    new_row.append(buttons.close_description_button)
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)
        
        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=route_message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )

    await _send_place_description(callback_query.message, state, place_ids, current_index, bot, message_to_edit_id=None)


@callback_router.callback_query(F.data.startswith("navigate_description_"))
async def navigate_description_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    user_data = await state.get_data()
    place_ids = user_data.get('route_place_ids', [])
    current_index = int(callback_query.data.split("_")[2])
    message_to_edit_id = user_data.get('current_description_message_id')

    if not place_ids or not (0 <= current_index < len(place_ids)):
        await callback_query.message.answer("Ошибка навигации по описаниям.")
        return

    await state.update_data(current_description_index=current_index)
    await _send_place_description(callback_query.message, state, place_ids, current_index, bot, message_to_edit_id=message_to_edit_id)


@callback_router.callback_query(F.data == "close_description")
async def close_description_callback(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    await callback_query.answer()
    user_data = await state.get_data()
    description_message_id = user_data.get('current_description_message_id')
    route_message_id = user_data.get('route_message_id')

    if description_message_id:
        await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=description_message_id)
        await state.update_data(current_description_message_id=None)

    if route_message_id:
        original_keyboard = callback_query.message.reply_markup.inline_keyboard if callback_query.message.reply_markup else []
        new_keyboard = []
        for row in original_keyboard:
            new_row = []
            for button in row:
                if button.callback_data == "close_description":
                    new_row.append(buttons.show_all_descriptions_button)
                else:
                    new_row.append(button)
            new_keyboard.append(new_row)
        
        await bot.edit_message_reply_markup(
            chat_id=callback_query.message.chat.id,
            message_id=route_message_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=new_keyboard)
        )


async def _send_place_description(message: Message, state: FSMContext, place_ids: List[int], current_index: int, bot: Bot, message_to_edit_id: int = None):
    place_id = place_ids[current_index]
    place = route_builder.get_place_by_id(place_id)

    if place and place.get('description'):
        full_description = re.sub('<[^<]+?>', '', place['description'])
        text = f"{place['title']}:\n\n{full_description}"

        keyboard_buttons = []
        if current_index > 0:
            keyboard_buttons.append(InlineKeyboardButton(text=buttons.navigate_back_button_text, callback_data=f"navigate_description_{current_index - 1}"))
        if current_index < len(place_ids) - 1:
            keyboard_buttons.append(InlineKeyboardButton(text=buttons.navigate_forward_button_text, callback_data=f"navigate_description_{current_index + 1}"))
        
        reply_markup = InlineKeyboardMarkup(inline_keyboard=[keyboard_buttons])

        if message_to_edit_id:
            await bot.edit_message_text(text, chat_id=message.chat.id, message_id=message_to_edit_id, reply_markup=reply_markup)
        else:
            sent_message = await message.answer(text, reply_markup=reply_markup)
            await state.update_data(current_description_message_id=sent_message.message_id)
    else:
        await message.answer("Описание не найдено.")
