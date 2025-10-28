# -*- coding: utf-8 -*-

"""
Скрипт для подготовки данных о культурных объектах из XLSX файла.
Извлекает информацию, генерирует теги, нормализует текст и сохраняет данные
в JSON файлы для использования ботом.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import pandas as pd
import json
import re
import os
from typing import List, Dict, Any, Set, Optional
from snowballstemmer import RussianStemmer


# --------------------------------------------------------------------------
# Инициализация стеммера и константы
# --------------------------------------------------------------------------

stemmer = RussianStemmer() # Инициализация русского стеммера

# Карта категорий объектов для генерации тегов
CATEGORY_MAP: Dict[int, List[str]] = {
    1: ["памятник", "монумент"],
    2: ["парк", "сад", "общественное пространство"],
    3: ["макет", "тактильный макет"],
    4: ["набережная"],
    5: ["архитектура", "история", "исторический объект"],
    6: ["культура", "досуг", "кинотеатр"],
    7: ["музей", "галерея"],
    8: ["театр"],
    10: ["искусство", "мозаика", "стрит-арт", "монументальное искусство"],
    11: ["канатная дорога", "канатка", "канатная"]
}

DEFAULT_VISIT_TIME_MINUTES = 30 # Время по умолчанию на осмотр места
EXCLUDE_CATEGORY_ID = 9 # Категория, которую нужно исключить


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def normalize_text(text: str) -> List[str]:
    """
    Нормализует текстовую строку: приводит к нижнему регистру, извлекает слова
    и стеммирует их.

    :param text: Входная текстовая строка.
    :return: Список стеммированных слов.
    """
    words = re.findall(r'\w+', text.lower()) # Извлечение слов и приведение к нижнему регистру
    return [stemmer.stemWord(word) for word in words] # Стемминг каждого слова


def generate_tags(row: pd.Series, tag_keywords: Dict[str, List[str]]) -> List[str]:
    """
    Генерирует список тегов для объекта на основе его названия, описания и категории.

    :param row: Строка данных об объекте (из DataFrame).
    :param tag_keywords: Словарь ключевых слов для генерации тегов.
    :return: Список сгенерированных тегов.
    """
    tags: Set[str] = set()
    # Объединяем название и описание для поиска ключевых слов
    text_to_search = str(row.get('title', '')) + ' ' + str(row.get('description', ''))
    normalized_text_tokens = set(normalize_text(text_to_search))

    # Добавляем теги на основе совпадений ключевых слов
    for tag, keywords in tag_keywords.items():
        normalized_keywords = {stemmer.stemWord(kw) for kw in keywords}
        if not normalized_keywords.isdisjoint(normalized_text_tokens):
            tags.add(stemmer.stemWord(tag))

    # Добавляем теги на основе category_id
    category_id: Optional[int] = row.get('category_id')
    if category_id in CATEGORY_MAP:
        for tag in CATEGORY_MAP[category_id]:
            tags.add(stemmer.stemWord(tag))

    return list(tags) if tags else [stemmer.stemWord('достопримечательность')] # Если теги не сгенерированы, добавляем общий тег


# --------------------------------------------------------------------------
# Основная функция скрипта
# --------------------------------------------------------------------------

def main() -> None:
    """
    Главная функция скрипта.
    1. Определяет пути к входным и выходным файлам.
    2. Загружает данные из XLSX файла.
    3. Фильтрует данные (исключает category_id = 9).
    4. Обрабатывает координаты.
    5. Определяет ключевые слова для тегов и время посещения категорий.
    6. Генерирует данные об объектах с тегами и временем посещения.
    7. Сохраняет обработанные данные об объектах и синонимы в JSON файлы.
    """
    # Определение путей к файлам
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(base_dir, 'src', 'ai', 'cultural_objects_mnn.xlsx')
    output_dir = os.path.join(base_dir, 'src', 'data')
    places_path = os.path.join(output_dir, 'places.json')
    synonyms_path = os.path.join(output_dir, 'synonyms.json')
    category_times_path = os.path.join(output_dir, 'category_times.json')

    os.makedirs(output_dir, exist_ok=True) # Создание выходной директории, если ее нет

    # Загрузка данных из Excel файла и фильтрация
    df = pd.read_excel(data_source_path)
    df = df[df['category_id'] != EXCLUDE_CATEGORY_ID].copy() # Исключаем объекты с category_id = 9

    # Извлечение широты и долготы из строки 'coordinate'
    coords = df['coordinate'].str.extract(r'POINT \(([^ ]+) ([^ ]+)\)', expand=True)
    df['latitude'] = pd.to_numeric(coords[1], errors='coerce')
    df['longitude'] = pd.to_numeric(coords[0], errors='coerce')
    df.dropna(subset=['latitude', 'longitude'], inplace=True) # Удаление строк с некорректными координатами

    # Определение ключевых слов для генерации тегов
    tag_keywords: Dict[str, List[str]] = {
        "история": ["исторический", "история", "век", "война", "революция", "советский", "империя", "царь", "минин", "пожарский"],
        "памятник": ["памятник", "монумент", "статуя", "бюст"],
        "парк": ["парк", "сквер", "сад", "аллея", "природа", "зелень", "деревья", "цветы", "вода"],
        "музей": ["музей", "галерея", "выставка", "экспозиция", "картина"],
        "театр": ["театр", "сцена", "драма", "комедия", "опера", "балет", "концерт", "музыка"],
        "архитектура": ["архитектура", "зодчество", "здание", "дом", "усадьба", "особняк"],
        "собор": ["собор", "храм", "церковь", "монастырь"],
        "кремль": ["кремль", "крепость", "башня"],
        "искусство": ["искусство", "мозаика", "панно", "скульптура", "картина", "живопись", "графика", "кино"],
        "литература": ["пушкин", "горький", "писатель", "поэт"],
        "отдых": ["кафе", "ресторан", "гулять", "сидеть", "смотреть", "отдыхать", "пейзаж", "фотографировать"],
        "панорама": ["гулять", "сидеть", "смотреть", "отдыхать", "пейзаж", "фотографировать"],
        "шопинг": ["магазин", "покупки", "сувениры", "тц", "торговый центр"],
        "фото": ["фотографировать", "снимать", "пейзаж"],
        "стрит-арт": ["арт", "мозаика", "панно", "граффити", "рисунок"],
        "канатная дорога": ["канатка", "канатная дорога", "канатная"]
    }

    # Определение примерного времени посещения для категорий
    category_times: Dict[str, int] = {
        "1": 10, "2": 60, "3": 5, "4": 45, "5": 30, "6": 45, "7": 90, "8": 15, "10": 10, "11": 60
    }
    with open(category_times_path, 'w', encoding='utf-8') as f:
        json.dump(category_times, f, ensure_ascii=False, indent=4)

    # Обработка каждого объекта и генерация данных
    places_data: List[Dict[str, Any]] = []
    for _, row in df.iterrows():
        category_id = str(row['category_id'])
        place = {
            "id": row.get('id'),
            "address": row.get('address'),
            "latitude": row.get('latitude'),
            "longitude": row.get('longitude'),
            "description": row.get('description'),
            "title": row.get('title'),
            "category_id": row.get('category_id'),
            "tags": generate_tags(row, tag_keywords), # Генерация тегов
            "estimated_visit_minutes": category_times.get(category_id, DEFAULT_VISIT_TIME_MINUTES) # Время посещения
        }
        places_data.append(place)

    # Сохранение данных об объектах в JSON
    with open(places_path, 'w', encoding='utf-8') as f:
        json.dump(places_data, f, ensure_ascii=False, indent=4)

    # Определение и стемминг синонимов для объектов
    raw_synonyms: Dict[str, List[str]] = {
        "памятник": ["монумент", "статуя"],
        "парк": ["сквер", "сад", "природа", "пикник", "трава", "деревья"],
        "музей": ["галерея", "выставка", "картина"],
        "театр": ["сцена", "концерт", "музыка"],
        "набережная": ["берег", "волга", "река", "ока", "вода", "панорама", "вид"],
        "архитектура": ["зодчество", "здание", "дом", "сооружение"],
        "история": ["исторический", "советский"],
        "собор": ["храм", "церковь"],
        "кремль": ["крепость"],
        "отдых": ["кофе", "кафе", "ресторан", "гулять", "сидеть", "смотреть", "тусить", "туса", "движ", "пиво", "вино", "еда", "ужин", "обед", "завтрак"],
        "панорама": ["гулять", "сидеть", "смотреть", "вид"],
        "шопинг": ["магазин", "покупки", "сувениры", "тц", "торговый центр"],
        "фото": ["фотографировать", "снимать", "пейзаж"],
        "стрит-арт": ["арт", "мозаика", "панно", "граффити", "рисунок"],
        "канатная дорога": ["канатка", "канатная дорога", "канатная"]
    }
    
    stemmed_synonyms: Dict[str, str] = {}
    for key, values in raw_synonyms.items():
        stemmed_key = stemmer.stemWord(key)
        stemmed_values = [stemmer.stemWord(v) for v in values]
        if stemmed_key not in stemmed_values:
            stemmed_values.append(stemmed_key)
        
        for val in stemmed_values:
            stemmed_synonyms[val] = stemmed_key

    # Сохранение стеммированных синонимов в JSON
    with open(synonyms_path, 'w', encoding='utf-8') as f:
        json.dump(stemmed_synonyms, f, ensure_ascii=False, indent=4)

    print(f"Подготовка данных завершена. Файлы созданы в {output_dir}")


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------

if __name__ == '__main__':
    main()
