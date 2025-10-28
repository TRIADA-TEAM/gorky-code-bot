# -*- coding: utf-8 -*-

"""
Скрипт для создания и сохранения эмбеддингов (векторных представлений) культурных объектов.
Использует предобученную модель SentenceTransformer для преобразования текстовых описаний
объектов в числовые векторы, которые затем сохраняются для использования в системе RAG.
"""

# --------------------------------------------------------------------------
# Импорты
# --------------------------------------------------------------------------

import json
import numpy as np
import os
import pandas as pd
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any


# --------------------------------------------------------------------------
# Константы
# --------------------------------------------------------------------------

EMBEDDING_MODEL = 'all-MiniLM-L6-v2' # Название предобученной модели для создания эмбеддингов
EXCLUDE_CATEGORY_ID = 9 # Категория, которую нужно исключить из данных


# --------------------------------------------------------------------------
# Основная функция скрипта
# --------------------------------------------------------------------------

def create_embeddings() -> None:
    """
    Главная функция для создания эмбеддингов.
    1. Определяет пути к исходным данным и файлам для сохранения эмбеддингов и ID.
    2. Проверяет наличие уже созданных файлов, чтобы избежать повторной генерации.
    3. Загружает данные о культурных объектах из XLSX файла.
    4. Фильтрует данные, исключая определенные категории.
    5. Объединяет текстовые столбцы для создания единого описания для эмбеддинга.
    6. Загружает модель SentenceTransformer.
    7. Генерирует эмбеддинги для всех текстовых описаний.
    8. Сохраняет эмбеддинги в файл .npy и ID объектов в JSON файл.
    """
    # Определение путей к файлам
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'src', 'data')
    excel_path = os.path.join(base_dir, 'src', 'ai', 'cultural_objects_mnn.xlsx')
    embeddings_path = os.path.join(data_dir, 'embeddings.npy')
    ids_path = os.path.join(data_dir, 'place_ids.json')

    # Проверка наличия уже созданных файлов
    if os.path.exists(embeddings_path) and os.path.exists(ids_path):
        print("Файлы эмбеддингов и ID уже существуют. Пропускаю создание.")
        return

    print("Загрузка исходных данных Excel...")
    try:
        df = pd.read_excel(excel_path)
    except FileNotFoundError:
        print(f"Ошибка: {excel_path} не найден.")
        return

    print("Фильтрация данных в соответствии с требованиями RAG...")
    df = df[df['category_id'] != EXCLUDE_CATEGORY_ID].copy() # Исключаем объекты с category_id = 9

    # Определение текстовых столбцов для эмбеддинга
    all_cols: List[str] = df.columns.tolist()
    cols_to_exclude: List[str] = ['id', 'category_id', 'url', 'address', 'coordinate']
    text_cols: List[str] = [col for col in all_cols if col not in cols_to_exclude]
    print(f"Используемые столбцы для текста эмбеддингов: {text_cols}")

    # Объединение текстовых столбцов в одну строку для каждого объекта
    df['text_for_embedding'] = df[text_cols].fillna('').astype(str).agg('; '.join, axis=1)

    texts_to_embed: List[str] = df['text_for_embedding'].tolist()
    place_ids: List[int] = df['id'].tolist()

    if not texts_to_embed:
        print("Нет текстовых данных для создания эмбеддингов.")
        return

    print(f"Загрузка модели Sentence Transformer '{EMBEDDING_MODEL}'...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Генерация эмбеддингов для {len(texts_to_embed)} мест... (Это может занять некоторое время)")
    embeddings: np.ndarray = model.encode(texts_to_embed, show_progress_bar=True) # Генерация эмбеддингов

    print(f"Сохранение эмбеддингов в {embeddings_path}")
    np.save(embeddings_path, embeddings) # Сохранение эмбеддингов в файл .npy

    print(f"Сохранение ID мест в {ids_path}")
    with open(ids_path, 'w', encoding='utf-8') as f:
        json.dump(place_ids, f) # Сохранение ID мест в JSON файл

    print("--- Подготовка RAG эмбеддингов завершена! ---")


# --------------------------------------------------------------------------
# Точка входа
# --------------------------------------------------------------------------

if __name__ == '__main__':
    create_embeddings()
