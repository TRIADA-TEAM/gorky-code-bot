import pandas as pd
import json
import re
import os
from snowballstemmer import RussianStemmer

stemmer = RussianStemmer()

def normalize_text(text):
    words = re.findall(r'\w+', text.lower())
    return [stemmer.stemWord(word) for word in words]

def generate_tags(row, tag_keywords):
    tags = set()
    text_to_search = str(row.get('title', '')) + ' ' + str(row.get('description', ''))
    normalized_text_tokens = normalize_text(text_to_search)

    for tag, keywords in tag_keywords.items():
        normalized_keywords = {stemmer.stemWord(kw) for kw in keywords}
        if not normalized_keywords.isdisjoint(normalized_text_tokens):
            tags.add(stemmer.stemWord(tag))

    category_map = {
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
    category_id = row.get('category_id')
    if category_id in category_map:
        for tag in category_map[category_id]:
            tags.add(stemmer.stemWord(tag))

    return list(tags) if tags else ['достопримечательност']

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_source_path = os.path.join(base_dir, 'src', 'ai', 'cultural_objects_mnn.xlsx')
    output_dir = os.path.join(base_dir, 'src', 'data')
    places_path = os.path.join(output_dir, 'places.json')
    synonyms_path = os.path.join(output_dir, 'synonyms.json')
    category_times_path = os.path.join(output_dir, 'category_times.json')

    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_excel(data_source_path)
    df = df[df['category_id'] != 9].copy()

    coords = df['coordinate'].str.extract(r'POINT \(([^ ]+) ([^ ]+)\)', expand=True)
    df['latitude'] = pd.to_numeric(coords[1], errors='coerce')
    df['longitude'] = pd.to_numeric(coords[0], errors='coerce')
    df.dropna(subset=['latitude', 'longitude'], inplace=True)

    tag_keywords = {
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
        "стрит-арт": ["арт", "мозаика", "панно", "граффити", "живопись"],
        "канатная дорога": ["канатка", "канатная дорога", "канатная"]
    }

    category_times = {
        "1": 10, "2": 60, "3": 5, "4": 45, "5": 30, "6": 45, "7": 90, "8": 15, "10": 10, "11": 60
    }
    with open(category_times_path, 'w', encoding='utf-8') as f:
        json.dump(category_times, f, ensure_ascii=False, indent=4)

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
            "tags": generate_tags(row, tag_keywords),
            "estimated_visit_minutes": category_times.get(category_id, 30)
        }
        places_data.append(place)

    with open(places_path, 'w', encoding='utf-8') as f:
        json.dump(places_data, f, ensure_ascii=False, indent=4)

    raw_synonyms = {
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
    
    stemmed_synonyms = {}
    for key, values in raw_synonyms.items():
        stemmed_key = stemmer.stemWord(key)
        stemmed_values = [stemmer.stemWord(v) for v in values]
        if stemmed_key not in stemmed_values:
            stemmed_values.append(stemmed_key)
        
        for val in stemmed_values:
            stemmed_synonyms[val] = stemmed_key

    with open(synonyms_path, 'w', encoding='utf-8') as f:
        json.dump(stemmed_synonyms, f, ensure_ascii=False, indent=4)

    print(f"Подготовка данных завершена. Файлы созданы в {output_dir}")

if __name__ == '__main__':
    main()
