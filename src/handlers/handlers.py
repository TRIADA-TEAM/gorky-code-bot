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

handlers_router = Router(name=__name__)

def split_message(text: str, chunk_size: int = 4096) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    while len(text) > 0:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        
        split_pos = text.rfind('\n', 0, chunk_size)
        if split_pos == -1:
            split_pos = chunk_size
            
        chunks.append(text[:split_pos])
        text = text[split_pos:]
        
    return chunks


async def _generate_and_send_route(message: Message, state: FSMContext, location, bot: Bot):
    await message.answer(messages.ROUTE_GENERATION_MESSAGE, reply_markup=ReplyKeyboardRemove())
    route_builder = RouteBuilder()

    user_data = await state.get_data()
    interests = user_data.get('interests')
    time = user_data.get('time')

    generated_route_text, retrieved_docs, reply_markup, place_ids, notification = await route_builder.generate_route(interests, time, location)

    if notification:
        await message.answer(notification)

    await state.update_data(route_place_ids=place_ids)

    message_chunks = split_message(generated_route_text)
    for i, chunk in enumerate(message_chunks):
        if i == len(message_chunks) - 1:
            sent_route_message = await message.answer(
                chunk,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            await state.update_data(route_message_id=sent_route_message.message_id)
        else:
            await message.answer(
                chunk,
                parse_mode=ParseMode.MARKDOWN
            )


@handlers_router.message(UserState.Interests)
async def process_interests(message: Message, state: FSMContext):
    await state.update_data(interests=message.text)
    await message.answer(messages.TIME_MESSAGE)
    await state.set_state(UserState.Time)


@handlers_router.message(UserState.Time)
async def process_time(message: Message, state: FSMContext):
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
                builder = InlineKeyboardBuilder()
                builder.add(buttons.confirm_time_yes)
                builder.add(buttons.confirm_time_no)
                await message.answer(messages.TIME_TOO_LONG_CONFIRM.format(time_hours=time_hours), reply_markup=builder.as_markup())
                await state.set_state(UserState.ConfirmTime)
            else:
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
    geolocator = Nominatim(user_agent="guide-bot-2", timeout=10)

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
