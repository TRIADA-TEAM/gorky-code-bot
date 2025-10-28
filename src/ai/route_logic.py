import os
import json
import logging
import re
import requests
from geopy.distance import geodesic
import pandas as pd
from typing import Tuple, List
from snowballstemmer import RussianStemmer
from dotenv import load_dotenv
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from src.ai.rag_fallback import RAGFallback
from content import messages
from content import buttons

load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')
PLACES_PATH = os.path.join(DATA_DIR, 'places.json')
SYNONYMS_PATH = os.path.join(DATA_DIR, 'synonyms.json')
CATEGORY_TIMES_PATH = os.path.join(DATA_DIR, 'category_times.json')
FOOD_PLACES_PATH = os.path.join(DATA_DIR, 'food_places.json')
FOOD_SYNONYMS_PATH = os.path.join(DATA_DIR, 'food_synonyms.json')
FOOD_CATEGORY_TIMES_PATH = os.path.join(DATA_DIR, 'food_category_times.json')
FOOD_CATEGORIES_PATH = os.path.join(DATA_DIR, 'food_categories.json')
AVG_WALKING_SPEED_KMH = 4.5

class RouteBuilder:
    def __init__(self):
        self.places = []
        self.food_places = []
        self.synonyms = {}
        self.food_keywords = set()
        self.category_times = {}
        self.food_categories = {}
        self.stemmer = RussianStemmer()
        self.gis_api_key = os.getenv("2GIS_API_KEY")
        self.rag_fallback = RAGFallback()
        self._load_data()
        if not self.gis_api_key:
            logging.warning("2GIS_API_KEY не найден в файле .env. Реальные дорожные расстояния будут недоступны.")

    def _load_data(self):
        try:
            with open(PLACES_PATH, 'r', encoding='utf-8') as f:
                self.places = json.load(f)
            with open(FOOD_PLACES_PATH, 'r', encoding='utf-8') as f:
                self.food_places = json.load(f)
            with open(SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                self.synonyms = json.load(f)
            with open(FOOD_SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                food_synonyms = json.load(f)
                self.synonyms.update(food_synonyms)
                self.food_keywords = set(food_synonyms.keys())
            with open(CATEGORY_TIMES_PATH, 'r', encoding='utf-8') as f:
                self.category_times = json.load(f)
            with open(FOOD_CATEGORY_TIMES_PATH, 'r', encoding='utf-8') as f:
                food_category_times = json.load(f)
                self.category_times.update(food_category_times)
            with open(FOOD_CATEGORIES_PATH, 'r', encoding='utf-8') as f:
                self.food_categories = json.load(f)
            logging.info("Файлы данных (места, заведения, синонимы, время категорий, категории еды) успешно загружены.")
        except FileNotFoundError as e:
            logging.error(f"Ошибка загрузки файлов данных: {e}. Система поиска не будет работать.")
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка декодирования JSON из файлов данных: {e}. Система поиска не будет работать.")

    def get_place_by_id(self, place_id: int):
        for place in self.places + self.food_places:
            if place.get('id') == place_id:
                return place
        return None

    def _normalize_interests(self, interests_str: str) -> set:
        tokens = re.findall(r'\w+', interests_str.lower())
        stemmed_tokens = set()
        for token in tokens:
            stemmed_token = self.stemmer.stemWord(token)
            root_word = self.synonyms.get(stemmed_token, stemmed_token)
            stemmed_tokens.add(root_word)
        return stemmed_tokens

    def _find_places(self, interests: str) -> list:
        normalized_interests = self._normalize_interests(interests)
        if not normalized_interests:
            return []
        
        scored_places = []
        for place in self.places:
            place_tags = set(place.get('tags', []))
            score = len(normalized_interests.intersection(place_tags))
            
            if 'макет' in place_tags:
                score -= 0.5
            
            if 'мозаик' in place_tags and not ('мозаик' in normalized_interests or 'искусств' in normalized_interests):
                score -= 1.0

            if score > 0:
                scored_places.append({'place': place, 'score': score})

        scored_places.sort(key=lambda x: x['score'], reverse=True)
        return [sp['place'] for sp in scored_places[:30]]

    def _find_food_places(self, interests: str) -> list:
        normalized_interests = self._normalize_interests(interests)
        if not normalized_interests:
            return self.food_places

        scored_places = []
        for place in self.food_places:
            place_tags = set(place.get('tags', []))
            score = len(normalized_interests.intersection(place_tags))

            if score > 0:
                scored_places.append({'place': place, 'score': score})

        scored_places.sort(key=lambda x: x['score'], reverse=True)
        return [sp['place'] for sp in scored_places]

    def _get_geodesic_travel_info(self, point1, point2) -> Tuple[float, float]:
        distance_km = geodesic(point1, point2).kilometers
        duration_min = (distance_km / AVG_WALKING_SPEED_KMH) * 60
        return duration_min, distance_km

    def _optimize_route_by_geodesic(self, places: list, start_location, time_limit_hours: int, food_candidates: list, explicit_food_request: bool) -> list:
        time_limit_minutes = time_limit_hours * 60
        current_location = (start_location.latitude, start_location.longitude)
        remaining_places = places.copy()
        optimal_route = []
        current_time = 0
        time_since_last_food_stop = 0

        food_stop_wait_time = 30 if explicit_food_request else 180

        while remaining_places and current_time < time_limit_minutes:
            
            if food_candidates and time_since_last_food_stop >= food_stop_wait_time:
                nearest_food_place = min(
                    food_candidates,
                    key=lambda place: self._get_geodesic_travel_info(current_location, (place['latitude'], place['longitude']))[0]
                )
                
                travel_time_to_food, _ = self._get_geodesic_travel_info(current_location, (nearest_food_place['latitude'], nearest_food_place['longitude']))
                visit_time_food = nearest_food_place.get('estimated_visit_minutes', 45)

                if current_time + travel_time_to_food + visit_time_food <= time_limit_minutes:
                    optimal_route.append(nearest_food_place)
                    current_time += travel_time_to_food + visit_time_food
                    current_location = (nearest_food_place['latitude'], nearest_food_place['longitude'])
                    time_since_last_food_stop = 0
                    food_candidates.remove(nearest_food_place)
                    continue

            nearest_place = min(
                remaining_places,
                key=lambda place: self._get_geodesic_travel_info(current_location, (place['latitude'], place['longitude']))[0]
            )
            
            travel_time_to_nearest, _ = self._get_geodesic_travel_info(current_location, (nearest_place['latitude'], nearest_place['longitude']))
            visit_time = nearest_place.get('estimated_visit_minutes', 30)

            if current_time + travel_time_to_nearest + visit_time <= time_limit_minutes:
                optimal_route.append(nearest_place)
                current_time += travel_time_to_nearest + visit_time
                time_since_last_food_stop += travel_time_to_nearest + visit_time
                current_location = (nearest_place['latitude'], nearest_place['longitude'])
                remaining_places.remove(nearest_place)
            else:
                break
                
        return optimal_route

    def _get_route_travel_times_from_2gis(self, final_route_points: List[Tuple[float, float]]) -> Tuple[List[float], List[float]]:
        num_segments = len(final_route_points) - 1
        if not self.gis_api_key or num_segments < 1:
            durations, distances = [], []
            for i in range(num_segments):
                d, dist = self._get_geodesic_travel_info(final_route_points[i], final_route_points[i+1])
                durations.append(d)
                distances.append(dist)
            return durations, distances

        try:
            url = f"https://routing.api.2gis.com/get_dist_matrix?key={self.gis_api_key}"
            payload = {
                "points": [{"lat": lat, "lon": lon} for lat, lon in final_route_points],
                "mode": "walking",
                "sources": list(range(len(final_route_points))),
                "targets": list(range(len(final_route_points)))
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

            dist_matrix = [[(float('inf'), float('inf'))] * len(final_route_points) for _ in range(len(final_route_points))]
            for route in data['routes']:
                dist_matrix[route['source_id']][route['target_id']] = (route['duration'] / 60, route['distance'] / 1000)

            durations, distances = [], []
            for i in range(num_segments):
                duration, distance = dist_matrix[i][i+1]
                if duration == float('inf'):
                    logging.warning(f"2GIS API не вернул маршрут для сегмента {i}. Возврат к прямолинейному расстоянию.")
                    duration, distance = self._get_geodesic_travel_info(final_route_points[i], final_route_points[i+1])
                durations.append(duration)
                distances.append(distance)

            return durations, distances

        except requests.RequestException as e:
            logging.error(f"Запрос к 2GIS API завершился ошибкой: {e}. Возврат к прямолинейному расстоянию для всех сегментов.")
        except (KeyError, IndexError) as e:
            logging.error(f"Не удалось разобрать ответ 2GIS API: {e}. Возврат к прямолинейному расстоянию для всех сегментов.")
        
        durations, distances = [], []
        for i in range(num_segments):
            d, dist = self._get_geodesic_travel_info(final_route_points[i], final_route_points[i+1])
            durations.append(d)
            distances.append(dist)
        return durations, distances

    def _format_route_text(self, route_places: list, start_location, retrieved_docs: pd.DataFrame) -> Tuple[str, InlineKeyboardMarkup]:
        if not route_places:
            return messages.ERROR_CANNOT_CREATE_ROUTE, InlineKeyboardMarkup(inline_keyboard=[[]])

        final_points = [(start_location.latitude, start_location.longitude)] + [(p['latitude'], p['longitude']) for p in route_places]
        gis_travel_times, gis_travel_distances = self._get_route_travel_times_from_2gis(final_points)

        text = messages.ROUTE_HEADER
        
        logging.info("Сравнение времени в пути (по прямой vs 2GIS)")
        total_duration_minutes = 0
        total_distance_km = 0
        
        for i, place in enumerate(route_places):
            gis_time = gis_travel_times[i]
            gis_dist = gis_travel_distances[i]
            visit_time = place.get('estimated_visit_minutes', 30)
            
            total_duration_minutes += gis_time + visit_time
            total_distance_km += gis_dist

            geodesic_time, _ = self._get_geodesic_travel_info(final_points[i], final_points[i+1])
            
            start_point_name = "Начало" if i == 0 else route_places[i-1]['title']
            logging.info(f"  Сегмент {i+1}: {start_point_name} -> {place['title']}")
            logging.info(f"    - Время по прямой: {geodesic_time:.2f} мин")
            logging.info(f"    - Время 2GIS: {gis_time:.2f} мин")

            if 'ед' in place.get('tags', []):
                category_id = str(place.get('category_id', ''))
                category_name = self.food_categories.get(category_id, [''])[0]
                text += messages.ROUTE_FOOD_PLACE_INFO.format(
                    i=i+1,
                    title=place['title'],
                    category=category_name,
                    travel_time=int(gis_time),
                    address=place['address'],
                    visit_time=visit_time
                )
            else:
                text += messages.ROUTE_PLACE_INFO.format(
                    i=i+1,
                    title=place['title'],
                    travel_time=int(gis_time),
                    address=place['address'],
                    visit_time=visit_time
                )
            
        hours, minutes = divmod(total_duration_minutes, 60)
        summary = messages.ROUTE_SUMMARY.format(hours=int(hours), minutes=int(minutes), distance=total_distance_km)
        text += summary

        main_buttons = [[buttons.show_all_descriptions_button]]

        if retrieved_docs is not None and not retrieved_docs.empty:
            docs_for_map = retrieved_docs
            if len(retrieved_docs) > 8:
                logging.warning(messages.MAP_POINT_LIMIT_WARNING)
                docs_for_map = retrieved_docs.head(8)

            start_point = f"{start_location.longitude},{start_location.latitude}"
            route_points = [f"{row['longitude']},{row['latitude']}" for _, row in docs_for_map.iterrows()]
            all_points_str = "|".join([start_point] + route_points)
            url = f"https://2gis.ru/n_novgorod/directions/points/{all_points_str}"
            main_buttons.append([InlineKeyboardButton(text=buttons.open_2gis_map_button_text, url=url)])
        
        main_buttons.append([buttons.remake_route_button])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=main_buttons)

        return text, reply_markup

    async def generate_route(self, interests: str, time_str: str, location) -> Tuple[str, pd.DataFrame, InlineKeyboardMarkup, List[int], str | None]:
        notification = None
        if not self.places:
            return messages.ERROR_SEARCH_SYSTEM_INIT, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        try:
            time_limit_hours = float(time_str)
        except (ValueError, TypeError):
            return messages.ERROR_INVALID_TIME_FORMAT, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        user_interests_normalized = self._normalize_interests(interests)
        explicit_food_request = not self.food_keywords.isdisjoint(user_interests_normalized)
        
        add_food_opportunistically = time_limit_hours >= 3

        candidate_places = self._find_places(interests)
        food_candidates = []

        if explicit_food_request:
            food_as_places = self._find_food_places(interests)
            candidate_places.extend(food_as_places)
        elif add_food_opportunistically:
            food_candidates = self._find_food_places("кафе")

        candidate_places = self._find_places(interests)

        if not candidate_places:
            logging.info("Поиск по тегам не дал результатов. Переключаюсь на семантический поиск RAG.")
            notification = messages.RAG_FALLBACK_NOTIFICATION
            candidate_places = self.rag_fallback.find_places_by_semantic_search(interests)

        if not candidate_places:
            return messages.ERROR_NO_PLACES_FOUND, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        final_route_places = self._optimize_route_by_geodesic(candidate_places, location, time_limit_hours, food_candidates, explicit_food_request)

        if not final_route_places:
            return messages.ERROR_CANNOT_CREATE_ROUTE, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        final_docs = pd.DataFrame(final_route_places)
        final_route_text, reply_markup = self._format_route_text(final_route_places, location, final_docs)
        place_ids = [place['id'] for place in final_route_places]

        return final_route_text, final_docs, reply_markup, place_ids, notification

def create_index():
    logging.info("Функция create_index устарела и больше ничего не делает.")
    pass
