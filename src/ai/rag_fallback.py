# -*- coding: utf-8 -*-

"""
Модуль RAGFallback реализует механизм семантического поиска с использованием
Retrieval-Augmented Generation (RAG) для поиска мест по запросам пользователя.
Он загружает предобученную модель для создания эмбеддингов и FAISS индекс
для быстрого поиска ближайших векторов.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import json
import numpy as np
import os
import faiss
from sentence_transformers import SentenceTransformer
import logging
from typing import List, Dict, Any, Optional


# --------------------------------------------------------------------------
# Константы
# --------------------------------------------------------------------------

EMBEDDING_MODEL = 'all-MiniLM-L6-v2' # Название предобученной модели для эмбеддингов


# --------------------------------------------------------------------------
# Класс RAGFallback
# --------------------------------------------------------------------------

class RAGFallback:
    """
    Класс для реализации фолбэка на основе RAG (Retrieval-Augmented Generation).
    Используется для семантического поиска мест, когда обычный поиск по тегам не дает результатов.
    """
    def __init__(self) -> None:
        """
        Инициализация RAGFallback. Загружает модель эмбеддингов, данные о местах,
        их ID и создает FAISS индекс.
        """
        self.model: Optional[SentenceTransformer] = None
        self.places_data: List[Dict[str, Any]] = []
        self.place_ids: List[int] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index: Optional[faiss.IndexFlatL2] = None
        self._load_all_data() # Загрузка всех необходимых данных при инициализации

    def _load_all_data(self) -> None:
        """
        Загружает данные о местах, их эмбеддинги и ID из файлов.
        Инициализирует модель SentenceTransformer и создает FAISS индекс для поиска.
        Обрабатывает ошибки, связанные с отсутствием файлов или некорректными данными.
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(base_dir), 'data')
        places_path = os.path.join(data_dir, 'places.json')
        embeddings_path = os.path.join(data_dir, 'embeddings.npy')
        ids_path = os.path.join(data_dir, 'place_ids.json')

        try:
            logging.info("Загрузка данных для фолбэка RAG...")
            self.model = SentenceTransformer(EMBEDDING_MODEL) # Загрузка модели эмбеддингов

            with open(places_path, 'r', encoding='utf-8') as f:
                self.places_data = json.load(f) # Загрузка данных о местах
            
            self.embeddings = np.load(embeddings_path) # Загрузка эмбеддингов
            with open(ids_path, 'r', encoding='utf-8') as f:
                self.place_ids = json.load(f) # Загрузка ID мест

            self.places_map: Dict[int, Dict[str, Any]] = {place['id']: place for place in self.places_data} # Создание карты ID -> место

            if self.embeddings is not None:
                dimension = self.embeddings.shape[1]
                self.index = faiss.IndexFlatL2(dimension) # Инициализация FAISS индекса
                self.index.add(self.embeddings.astype('float32')) # Добавление эмбеддингов в индекс
                logging.info("Система фолбэка RAG успешно загружена.")

        except FileNotFoundError as e:
            logging.error(f"Данные для фолбэка RAG не найдены: {e}. Система фолбэка будет отключена.")
            self.index = None # Отключение индекса при ошибке
            self.model = None # Отключение модели при ошибке
        except Exception as e:
            logging.error(f"Произошла ошибка при загрузке системы фолбэка RAG: {e}")
            self.index = None # Отключение индекса при ошибке
            self.model = None # Отключение модели при ошибке

    def find_places_by_semantic_search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Выполняет семантический поиск мест по заданному запросу.

        :param query: Запрос пользователя.
        :param top_k: Количество наиболее релевантных мест для возврата (по умолчанию 5).
        :return: Список словарей с информацией о найденных местах.
        """
        if self.index is None or self.model is None:
            logging.warning("Система фолбэка RAG недоступна.")
            return []

        try:
            logging.info(f"Выполняется семантический поиск по запросу: '{query}'")
            query_embedding = self.model.encode([query]) # Получение эмбеддинга запроса
            distances, indices = self.index.search(query_embedding.astype('float32'), top_k) # Поиск ближайших векторов

            found_places: List[Dict[str, Any]] = []
            for i in indices[0]:
                if 0 <= i < len(self.place_ids):
                    place_id = self.place_ids[i]
                    place = self.places_map.get(place_id)
                    if place:
                        found_places.append(place)
            
            logging.info(f"Семантический поиск нашел {len(found_places)} мест.")
            return found_places

        except Exception as e:
            logging.error(f"Произошла ошибка во время семантического поиска: {e}")
            return []
