# -*- coding: utf-8 -*-

"""
Модуль RouteBuilder отвечает за логику построения маршрутов на основе интересов пользователя,
доступного времени и местоположения. Он использует данные о местах, синонимах и времени посещения
категорий, а также интегрируется с 2GIS API для расчета реальных расстояний и времени в пути.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import os
import json
import logging
import re
import requests
from geopy.distance import geodesic
import pandas as pd
from typing import Tuple, List, Dict, Any, Optional, Set
from snowballstemmer import RussianStemmer
from dotenv import load_dotenv
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from geopy.location import Location as GeoLocation

from src.ai.rag_fallback import RAGFallback
from content import messages
from content import buttons


# --------------------------------------------------------------------------
# Константы и конфигурация
# --------------------------------------------------------------------------

load_dotenv() # Загрузка переменных окружения из файла .env
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), 'data')

# Пути к файлам данных
PLACES_PATH = os.path.join(DATA_DIR, 'places.json')
SYNONYMS_PATH = os.path.join(DATA_DIR, 'synonyms.json')
CATEGORY_TIMES_PATH = os.path.join(DATA_DIR, 'category_times.json')
FOOD_PLACES_PATH = os.path.join(DATA_DIR, 'food_places.json')
FOOD_SYNONYMS_PATH = os.path.join(DATA_DIR, 'food_synonyms.json')
FOOD_CATEGORY_TIMES_PATH = os.path.join(DATA_DIR, 'food_category_times.json')
FOOD_CATEGORIES_PATH = os.path.join(DATA_DIR, 'food_categories.json')

AVG_WALKING_SPEED_KMH = 4.5 # Средняя скорость ходьбы в км/ч
DEFAULT_VISIT_TIME_MINUTES = 30 # Время по умолчанию на осмотр места
DEFAULT_FOOD_VISIT_TIME_MINUTES = 45 # Время по умолчанию на посещение заведения
MAX_ROUTE_POINTS_FOR_2GIS_MAP = 8 # Максимальное количество точек для отображения на карте 2GIS


# --------------------------------------------------------------------------
# Класс RouteBuilder
# --------------------------------------------------------------------------

class RouteBuilder:
    """
    Класс для построения и оптимизации туристических маршрутов.
    Загружает данные о местах, синонимах, времени посещения и использует их для
    формирования маршрута, учитывая интересы пользователя, время и местоположение.
    """
    def __init__(self):
        """
        Инициализация RouteBuilder. Загружает все необходимые данные и
        инициализирует стеммер и RAG-систему.
        """
        self.places: List[Dict[str, Any]] = []
        self.food_places: List[Dict[str, Any]] = []
        self.synonyms: Dict[str, str] = {}
        self.food_keywords: Set[str] = set()
        self.category_times: Dict[str, int] = {}
        self.food_categories: Dict[str, List[str]] = {}
        self.stemmer = RussianStemmer() # Стеммер для обработки русских слов
        self.gis_api_key: Optional[str] = os.getenv("2GIS_API_KEY") # Ключ API 2GIS
        self.rag_fallback = RAGFallback() # Система RAG для семантического поиска
        self._load_data() # Загрузка данных при инициализации
        if not self.gis_api_key:
            logging.warning("2GIS_API_KEY не найден в файле .env. Реальные дорожные расстояния будут недоступны.")

    def _load_data(self) -> None:
        """
        Загружает данные из JSON файлов: места, заведения, синонимы, время категорий и категории еды.
        Обрабатывает ошибки FileNotFoundError и JSONDecodeError.
        """
        try:
            with open(PLACES_PATH, 'r', encoding='utf-8') as f:
                self.places = json.load(f)
            with open(FOOD_PLACES_PATH, 'r', encoding='utf-8') as f:
                self.food_places = json.load(f)
            with open(SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                self.synonyms = json.load(f)
            with open(FOOD_SYNONYMS_PATH, 'r', encoding='utf-8') as f:
                food_synonyms = json.load(f)
                self.synonyms.update(food_synonyms) # Объединяем синонимы
                self.food_keywords = set(food_synonyms.keys()) # Ключевые слова для еды
            with open(CATEGORY_TIMES_PATH, 'r', encoding='utf-8') as f:
                self.category_times = json.load(f)
            with open(FOOD_CATEGORY_TIMES_PATH, 'r', encoding='utf-8') as f:
                food_category_times = json.load(f)
                self.category_times.update(food_category_times) # Объединяем время категорий
            with open(FOOD_CATEGORIES_PATH, 'r', encoding='utf-8') as f:
                self.food_categories = json.load(f)
            logging.info("Файлы данных (места, заведения, синонимы, время категорий, категории еды) успешно загружены.")
        except FileNotFoundError as e:
            logging.error(f"Ошибка загрузки файлов данных: {e}. Система поиска не будет работать.")
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка декодирования JSON из файлов данных: {e}. Система поиска не будет работать.")

    def get_place_by_id(self, place_id: int) -> Optional[Dict[str, Any]]:
        """
        Возвращает информацию о месте по его ID.

        :param place_id: Идентификатор места.
        :return: Словарь с информацией о месте или None, если место не найдено.
        """
        for place in self.places + self.food_places:
            if place.get('id') == place_id:
                return place
        return None

    def _normalize_interests(self, interests_str: str) -> Set[str]:
        """
        Нормализует строку интересов пользователя: токенизирует, стеммирует и заменяет синонимы.

        :param interests_str: Строка интересов пользователя.
        :return: Множество нормализованных ключевых слов.
        """
        tokens = re.findall(r'\w+', interests_str.lower()) # Извлечение слов
        stemmed_tokens: Set[str] = set()
        for token in tokens:
            stemmed_token = self.stemmer.stemWord(token) # Стемминг слова
            root_word = self.synonyms.get(stemmed_token, stemmed_token) # Замена на синоним, если есть
            stemmed_tokens.add(root_word)
        return stemmed_tokens

    def _find_places(self, interests: str) -> List[Dict[str, Any]]:
        """
        Находит места, соответствующие интересам пользователя, на основе тегов.
        Присваивает баллы местам и возвращает отсортированный список.

        :param interests: Строка интересов пользователя.
        :return: Список словарей с информацией о местах, отсортированных по релевантности.
        """
        normalized_interests = self._normalize_interests(interests)
        if not normalized_interests:
            return []
        
        scored_places: List[Dict[str, Any]] = []
        for place in self.places:
            place_tags: Set[str] = set(place.get('tags', []))
            score = len(normalized_interests.intersection(place_tags)) # Количество совпадений тегов
            
            # Корректировка баллов для специфических тегов
            if 'макет' in place_tags:
                score -= 0.5
            
            if 'мозаик' in place_tags and not ('мозаик' in normalized_interests or 'искусств' in normalized_interests):
                score -= 1.0

            if score > 0:
                scored_places.append({'place': place, 'score': score})

        scored_places.sort(key=lambda x: x['score'], reverse=True) # Сортировка по убыванию баллов
        return [sp['place'] for sp in scored_places[:30]] # Возвращаем до 30 наиболее релевантных мест

    def _find_food_places(self, interests: str) -> List[Dict[str, Any]]:
        """
        Находит заведения общественного питания, соответствующие интересам пользователя.

        :param interests: Строка интересов пользователя.
        :return: Список словарей с информацией о заведениях, отсортированных по релевантности.
        """
        normalized_interests = self._normalize_interests(interests)
        if not normalized_interests:
            return self.food_places # Если интересы не указаны, возвращаем все заведения

        scored_places: List[Dict[str, Any]] = []
        for place in self.food_places:
            place_tags: Set[str] = set(place.get('tags', []))
            score = len(normalized_interests.intersection(place_tags))

            if score > 0:
                scored_places.append({'place': place, 'score': score})

        scored_places.sort(key=lambda x: x['score'], reverse=True)
        return [sp['place'] for sp in scored_places]

    def _get_geodesic_travel_info(self, point1: Tuple[float, float], point2: Tuple[float, float]) -> Tuple[float, float]:
        """
        Рассчитывает геодезическое расстояние и время в пути между двумя точками.

        :param point1: Кортеж (широта, долгота) первой точки.
        :param point2: Кортеж (широта, долгота) второй точки.
        :return: Кортеж (время в минутах, расстояние в км).
        """
        distance_km = geodesic(point1, point2).kilometers
        duration_min = (distance_km / AVG_WALKING_SPEED_KMH) * 60
        return duration_min, distance_km

    def _optimize_route_by_geodesic(
        self,
        places: List[Dict[str, Any]],
        start_location: GeoLocation,
        time_limit_hours: int,
        food_candidates: List[Dict[str, Any]],
        explicit_food_request: bool
    ) -> List[Dict[str, Any]]:
        """
        Оптимизирует маршрут, выбирая места, ближайшие к текущей точке, с учетом временных ограничений.
        Также учитывает возможность включения остановок для еды.

        :param places: Список потенциальных мест для посещения.
        :param start_location: Начальное местоположение пользователя.
        :param time_limit_hours: Ограничение по времени в часах.
        :param food_candidates: Список потенциальных мест для еды.
        :param explicit_food_request: Флаг, указывающий, запросил ли пользователь еду явно.
        :return: Оптимальный список мест в маршруте.
        """
        time_limit_minutes = time_limit_hours * 60
        current_location = (start_location.latitude, start_location.longitude)
        remaining_places = places.copy()
        optimal_route: List[Dict[str, Any]] = []
        current_time = 0.0
        time_since_last_food_stop = 0.0

        # Время, через которое нужно искать место для еды
        food_stop_wait_time = 30 if explicit_food_request else 180

        while remaining_places and current_time < time_limit_minutes:
            
            # Попытка добавить место для еды, если пришло время
            if food_candidates and time_since_last_food_stop >= food_stop_wait_time:
                nearest_food_place = min(
                    food_candidates,
                    key=lambda place: self._get_geodesic_travel_info(current_location, (place['latitude'], place['longitude']))[0]
                )
                
                travel_time_to_food, _ = self._get_geodesic_travel_info(current_location, (nearest_food_place['latitude'], nearest_food_place['longitude']))
                visit_time_food = nearest_food_place.get('estimated_visit_minutes', DEFAULT_FOOD_VISIT_TIME_MINUTES)

                if current_time + travel_time_to_food + visit_time_food <= time_limit_minutes:
                    optimal_route.append(nearest_food_place)
                    current_time += travel_time_to_food + visit_time_food
                    current_location = (nearest_food_place['latitude'], nearest_food_place['longitude'])
                    time_since_last_food_stop = 0.0
                    food_candidates.remove(nearest_food_place)
                    continue # Продолжаем цикл, чтобы найти следующее место

            # Поиск ближайшего места из оставшихся
            nearest_place = min(
                remaining_places,
                key=lambda place: self._get_geodesic_travel_info(current_location, (place['latitude'], place['longitude']))[0]
            )
            
            travel_time_to_nearest, _ = self._get_geodesic_travel_info(current_location, (nearest_place['latitude'], nearest_place['longitude']))
            visit_time = nearest_place.get('estimated_visit_minutes', DEFAULT_VISIT_TIME_MINUTES)

            # Если место можно посетить в рамках оставшегося времени
            if current_time + travel_time_to_nearest + visit_time <= time_limit_minutes:
                optimal_route.append(nearest_place)
                current_time += travel_time_to_nearest + visit_time
                time_since_last_food_stop += travel_time_to_nearest + visit_time
                current_location = (nearest_place['latitude'], nearest_place['longitude'])
                remaining_places.remove(nearest_place)
            else:
                break # Если место не помещается, завершаем построение маршрута
                
        return optimal_route

    def _get_route_travel_times_from_2gis(self, final_route_points: List[Tuple[float, float]]) -> Tuple[List[float], List[float]]:
        """
        Получает время и расстояние в пути между точками маршрута с использованием 2GIS API.
        В случае ошибки или отсутствия ключа API, возвращается геодезическое расстояние.

        :param final_route_points: Список кортежей (широта, долгота) для точек маршрута.
        :return: Кортеж из двух списков: времени в пути (минуты) и расстояний (км) для каждого сегмента.
        """
        num_segments = len(final_route_points) - 1
        if not self.gis_api_key or num_segments < 1:
            # Если API ключ не указан или маршрут состоит из одной точки, используем геодезические расчеты
            durations: List[float] = []
            distances: List[float] = []
            for i in range(num_segments):
                d, dist = self._get_geodesic_travel_info(final_route_points[i], final_route_points[i+1])
                durations.append(d)
                distances.append(dist)
            return durations, distances

        try:
            url = f"https://routing.api.2gis.com/get_dist_matrix?key={self.gis_api_key}"
            payload = {
                "points": [{"lat": lat, "lon": lon} for lat, lon in final_route_points],
                "mode": "walking", # Режим передвижения: пешком
                "sources": list(range(len(final_route_points))),
                "targets": list(range(len(final_route_points)))
            }
            response = requests.post(url, json=payload)
            response.raise_for_status() # Вызывает исключение для плохих статусов HTTP
            data = response.json()

            # Парсинг ответа 2GIS API
            dist_matrix: List[List[Tuple[float, float]]] = [[(float('inf'), float('inf'))] * len(final_route_points) for _ in range(len(final_route_points))]
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
        
        # Возврат к геодезическим расчетам в случае ошибки API
        durations, distances = [], []
        for i in range(num_segments):
            d, dist = self._get_geodesic_travel_info(final_route_points[i], final_route_points[i+1])
            durations.append(d)
            distances.append(dist)
        return durations, distances

    def _format_route_text(self, route_places: List[Dict[str, Any]], start_location: GeoLocation, retrieved_docs: pd.DataFrame) -> Tuple[str, InlineKeyboardMarkup]:
        """
        Форматирует текстовое представление маршрута и создает Inline-клавиатуру.

        :param route_places: Список мест в маршруте.
        :param start_location: Начальное местоположение пользователя.
        :param retrieved_docs: DataFrame с информацией о местах для карты.
        :return: Кортеж из отформатированного текста маршрута и InlineKeyboardMarkup.
        """
        if not route_places:
            return messages.ERROR_CANNOT_CREATE_ROUTE, InlineKeyboardMarkup(inline_keyboard=[[]])

        # Подготовка точек для расчета маршрута через 2GIS API
        final_points: List[Tuple[float, float]] = [(start_location.latitude, start_location.longitude)] + [(p['latitude'], p['longitude']) for p in route_places]
        gis_travel_times, gis_travel_distances = self._get_route_travel_times_from_2gis(final_points)

        text = messages.ROUTE_HEADER
        
        logging.info("Сравнение времени в пути (по прямой vs 2GIS)")
        total_duration_minutes = 0.0
        total_distance_km = 0.0
        
        for i, place in enumerate(route_places):
            gis_time = gis_travel_times[i]
            gis_dist = gis_travel_distances[i]
            visit_time = place.get('estimated_visit_minutes', DEFAULT_VISIT_TIME_MINUTES)
            
            total_duration_minutes += gis_time + visit_time
            total_distance_km += gis_dist

            geodesic_time, _ = self._get_geodesic_travel_info(final_points[i], final_points[i+1])
            
            start_point_name = "Начало" if i == 0 else route_places[i-1]['title']
            logging.info(f"  Сегмент {i+1}: {start_point_name} -> {place['title']}")
            logging.info(f"    - Время по прямой: {geodesic_time:.2f} мин")
            logging.info(f"    - Время 2GIS: {gis_time:.2f} мин")

            # Форматирование информации о месте в зависимости от его типа (еда или обычное место)
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
            
        # Добавление сводки по маршруту
        hours, minutes = divmod(int(total_duration_minutes), 60)
        summary = messages.ROUTE_SUMMARY.format(hours=hours, minutes=minutes, distance=total_distance_km)
        text += summary

        # Формирование кнопок для Inline-клавиатуры
        main_buttons: List[List[InlineKeyboardButton]] = [[buttons.show_all_descriptions_button]]

        # Добавление кнопки для открытия карты 2GIS, если есть места
        if not retrieved_docs.empty:
            docs_for_map = retrieved_docs
            if len(retrieved_docs) > MAX_ROUTE_POINTS_FOR_2GIS_MAP:
                logging.warning(messages.MAP_POINT_LIMIT_WARNING)
                docs_for_map = retrieved_docs.head(MAX_ROUTE_POINTS_FOR_2GIS_MAP)

            start_point = f"{start_location.longitude},{start_location.latitude}"
            route_points = [f"{row['longitude']},{row['latitude']}" for _, row in docs_for_map.iterrows()]
            all_points_str = "|".join([start_point] + route_points)
            url = f"https://2gis.ru/n_novgorod/directions/points/{all_points_str}"
            main_buttons.append([InlineKeyboardButton(text=buttons.open_2gis_map_button_text, url=url)])
        
        main_buttons.append([buttons.remake_route_button])

        reply_markup = InlineKeyboardMarkup(inline_keyboard=main_buttons)

        return text, reply_markup

    async def generate_route(
        self,
        interests: str,
        time_str: str,
        location: GeoLocation
    ) -> Tuple[str, pd.DataFrame, InlineKeyboardMarkup, List[int], Optional[str]]:
        """
        Основная функция для генерации маршрута.

        :param interests: Интересы пользователя (строка).
        :param time_str: Доступное время в часах (строка).
        :param location: Начальное местоположение пользователя.
        :return: Кортеж: (текст маршрута, DataFrame с местами, InlineKeyboardMarkup, список ID мест, уведомление).
        """
        notification: Optional[str] = None
        if not self.places:
            return messages.ERROR_SEARCH_SYSTEM_INIT, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        try:
            time_limit_hours = float(time_str)
        except (ValueError, TypeError):
            return messages.ERROR_INVALID_TIME_FORMAT, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], None

        user_interests_normalized = self._normalize_interests(interests)
        # Проверяем, запросил ли пользователь еду явно
        explicit_food_request = not self.food_keywords.isdisjoint(user_interests_normalized)
        
        # Добавлять ли еду оппортунистически (если время позволяет)
        add_food_opportunistically = time_limit_hours >= 3

        candidate_places = self._find_places(interests)
        food_candidates: List[Dict[str, Any]] = []

        if explicit_food_request:
            food_candidates = self._find_food_places(interests)
        elif add_food_opportunistically:
            food_candidates = self._find_food_places("кафе") # Поиск кафе по умолчанию

        if not candidate_places:
            logging.info("Поиск по тегам не дал результатов. Переключаюсь на семантический поиск RAG.")
            notification = messages.RAG_FALLBACK_NOTIFICATION
            candidate_places = self.rag_fallback.find_places_by_semantic_search(interests)

        if not candidate_places:
            return messages.ERROR_NO_PLACES_FOUND, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], notification

        # Оптимизация маршрута
        final_route_places = self._optimize_route_by_geodesic(candidate_places, location, time_limit_hours, food_candidates, explicit_food_request)

        if not final_route_places:
            return messages.ERROR_CANNOT_CREATE_ROUTE, pd.DataFrame(), InlineKeyboardMarkup(inline_keyboard=[[]]), [], notification

        final_docs = pd.DataFrame(final_route_places)
        final_route_text, reply_markup = self._format_route_text(final_route_places, location, final_docs)
        place_ids = [place['id'] for place in final_route_places]

        return final_route_text, final_docs, reply_markup, place_ids, notification


