# -*- coding: utf-8 -*-

"""
Скрипт для подготовки данных о заведениях общественного питания из XLSX файла.
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
from snowballstemmer import RussianStemmer


# --------------------------------------------------------------------------
# Инициализация стеммера и константы
# --------------------------------------------------------------------------

stemmer = RussianStemmer() # Инициализация русского стеммера

# Карта категорий заведений для генерации тегов
CATEGORY_MAP = {
    1: ["ресторан"],
    2: ["кафе"],
    3: ["фастфуд"],
    4: ["бар"],
    5: ["паб"]
}


# --------------------------------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------------------------------

def normalize_text(text):
    """
    Нормализует текстовую строку: приводит к нижнему регистру, извлекает слова
    и стеммирует их.

    :param text: Входная текстовая строка.
    :return: Список стеммированных слов.
    """
    words = re.findall(r'\w+', text.lower()) # Извлечение слов и приведение к нижнему регистру
    return [stemmer.stemWord(word) for word in words] # Стемминг каждого слова


def generate_tags(row, tag_keywords):
    """
    Генерирует список тегов для заведения на основе его названия, описания и категории.

    :param row: Строка данных о заведении (из DataFrame).
    :param tag_keywords: Словарь ключевых слов для генерации тегов.
    :return: Список сгенерированных тегов.
    """
    tags = set()
    # Объединяем название и описание для поиска ключевых слов
    text_to_search = str(row.get('title', '')) + ' ' + str(row.get('description', ''))
    normalized_text_tokens = normalize_text(text_to_search)

    # Добавляем теги на основе совпадений ключевых слов
    for tag, keywords in tag_keywords.items():
        normalized_keywords = {stemmer.stemWord(kw) for kw in keywords}
        if not normalized_keywords.isdisjoint(normalized_text_tokens):
            tags.add(stemmer.stemWord(tag))
    
    # Добавляем теги на основе category_id
    category_id = row.get('category_id')
    if category_id in CATEGORY_MAP:
        for tag in CATEGORY_MAP[category_id]:
            tags.add(stemmer.stemWord(tag))

    tags.add(stemmer.stemWord("еда")) # Всегда добавляем тег "еда"
    return list(tags)


# --------------------------------------------------------------------------
# Основная функция скрипта
# --------------------------------------------------------------------------

def main():
    """
    Главная функция скрипта.
    1. Определяет пути к входным и выходным файлам.
    2. Загружает данные из XLSX файла.
    3. Обрабатывает координаты.
    4. Сохраняет карту категорий еды.
    5. Определяет ключевые слова для тегов и время посещения категорий.
    6. Генерирует данные о местах с тегами и временем посещения.
    7. Сохраняет обработанные данные о местах и синонимы в JSON файлы.
    """
    # Определение путей к файлам
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(base_dir, 'src', 'ai', 'food_places.xlsx')
    output_dir = os.path.join(base_dir, 'src', 'data')
    places_path = os.path.join(output_dir, 'food_places.json')
    synonyms_path = os.path.join(output_dir, 'food_synonyms.json')
    category_times_path = os.path.join(output_dir, 'food_category_times.json')
    food_categories_path = os.path.join(output_dir, 'food_categories.json')

    os.makedirs(output_dir, exist_ok=True) # Создание выходной директории, если ее нет

    # Загрузка данных из Excel файла
    df = pd.read_excel(data_source_path)

    # Извлечение широты и долготы из строки 'coordinate'
    coords = df['coordinate'].str.extract(r'POINT \(([^ ]+) ([^ ]+)\)', expand=True)
    df['latitude'] = pd.to_numeric(coords[1], errors='coerce')
    df['longitude'] = pd.to_numeric(coords[0], errors='coerce')
    df.dropna(subset=['latitude', 'longitude'], inplace=True) # Удаление строк с некорректными координатами

    # Сохранение карты категорий еды
    with open(food_categories_path, 'w', encoding='utf-8') as f:
        json.dump(CATEGORY_MAP, f, ensure_ascii=False, indent=4)

    # Определение ключевых слов для генерации тегов
    tag_keywords = {
        "ресторан": ["ресторан"],
        "кафе": ["кафе", "еда"],
        "бар": ["бар", "паб", "рюмочная"],
        "кофейня": ["кофе", "эспрессо", "капучино", "латте", "американо", "coffee", "пить", "попить", "кофейня"],
        "пиццерия": ["пицца", "итальянская"],
        "суши": ["суши", "роллы", "японская"],
        "бургерная": ["бургер", "американская", "burger", "american"],
        "шаурма": ["шаурма", "шаверма", "kebab", "shawarma"],
        "столовая": ["столовая", "комплексный обед"],
        "фастфуд": ["фастфуд", "быстрое питание", "стритфуд", "friture"],
        "европейская кухня": ["европейская", "europe"],
        "азиатская кухня": ["азиатская", "паназиатская", "китайская", "вьетнамская", "японская", "рамен", "лапша", "вок", "wok", "рамён", "суши", "роллы", "oriantal", "asian", "chinese"],
        "итальянская кухня": ["итальянская", "паста", "пицца", "пиццерия", "pizza", "italian"],
        "японская кухня": ["японская", "рамен", "рамён", "суши", "роллы", "фукурамен", "sushi", "japanese"],
        "русская кухня": ["русская", "домашняя", "борщ", "russian"],
        "пельмени": ["пельмени", "пельменная", "вареники"],
        "кавказская кухня": ["кавказская", "шашлык"],
        "грузинская кухня": ["хинкали", "хачапури", "georgian"],
        "завтрак": ["завтрак"],
        "обед": ["бизнес-ланч", "ланч", "обед"],
        "ужин": ["ужин"],
        "перекус": ["перекус", "закуски"],
        "чай": ["чай", "пить", "попить"],
        "вино": ["вино", "винная карта", "выпить"],
        "пиво": ["пиво", "крафтовое", "пить", "выпить"],
        "десерты": ["десерты", "сладкое", "торт", "пирожное", "pancake"],
        "выпечка": ["выпечка", "булочки", "хлеб", "пирог", "pie"]
    }

    # Определение примерного времени посещения для категорий
    category_times = {
        "1": 90, "2": 60, "3": 45, "4": 90, "5": 60
    }
    with open(category_times_path, 'w', encoding='utf-8') as f:
        json.dump(category_times, f, ensure_ascii=False, indent=4)

    # Обработка каждого заведения и генерация данных
    places_data = []
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
            "estimated_visit_minutes": category_times.get(category_id, 45) # Время посещения
        }
        places_data.append(place)

    # Сохранение данных о заведениях в JSON
    with open(places_path, 'w', encoding='utf-8') as f:
        json.dump(places_data, f, ensure_ascii=False, indent=4)

    # Определение и стемминг синонимов для заведений
    raw_synonyms = {
        "ресторан": ["гастрономическая", "европейская", "азиатская", "кухня", "вкусно", "дорого"],
        "кафе": ["кофейня", "поесть", "вкусно", "покушать", "недорого"],
        "паб": ["пиво", "выпить", "пить", "алкоголь", "нажраться", "набухаться", "бухнуть", "пить"],
        "бар": ["пиво", "выпить", "пить", "алкоголь", "бухнуть", "вино", "коктейль", "посидеть", "пить"],
        "пицца": ["пиццерия", "итальянская"],
        "суши": ["роллы", "японская", "азиатская"],
        "бургер": ["бургерная", "фастфуд"],
        "фастфуд": ["быстрое питание", "перекусить", "недорого", "быстро", "дёшево"],
        "шаурма": ["шаверма", "шавуха", "шава", "дёшево", "кебаб"],
        "еда": ["покушать", "кушать", "поесть", "пожрать", "похавать", "перекусить", "питание", "завтрак", "обед", "ужин", "кухня"],
        "кофе": ["кофейня", "кофе", "эспрессо", "капучино", "латте", "американо", "попить", "пить"],
        "кофейня": ["кофейня", "кофе", "эспрессо", "капучино", "латте", "американо", "попить", "пить"],
        "чай": ["чайная", "попить", "пить"]
    }
    
    stemmed_synonyms = {}
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

    print(f"Подготовка данных о заведениях завершена. Файлы созданы в {output_dir}")


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------

if __name__ == '__main__':
    main()