import json
import numpy as np
import os
import pandas as pd
from sentence_transformers import SentenceTransformer

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

def create_embeddings():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'src', 'data')
    excel_path = os.path.join(base_dir, 'src', 'ai', 'cultural_objects_mnn.xlsx')
    embeddings_path = os.path.join(data_dir, 'embeddings.npy')
    ids_path = os.path.join(data_dir, 'place_ids.json')

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
    df = df[df['category_id'] != 9].copy()

    all_cols = df.columns.tolist()
    cols_to_exclude = ['id', 'category_id', 'url', 'address', 'coordinate']
    text_cols = [col for col in all_cols if col not in cols_to_exclude]
    print(f"Используемые столбцы для текста эмбеддингов: {text_cols}")

    df['text_for_embedding'] = df[text_cols].fillna('').astype(str).agg('; '.join, axis=1)

    texts_to_embed = df['text_for_embedding'].tolist()
    place_ids = df['id'].tolist()

    if not texts_to_embed:
        print("Нет текстовых данных для создания эмбеддингов.")
        return

    print(f"Загрузка модели Sentence Transformer '{EMBEDDING_MODEL}'...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Генерация эмбеддингов для {len(texts_to_embed)} мест... (Это может занять некоторое время)")
    embeddings = model.encode(texts_to_embed, show_progress_bar=True)

    print(f"Сохранение эмбеддингов в {embeddings_path}")
    np.save(embeddings_path, embeddings)

    print(f"Сохранение ID мест в {ids_path}")
    with open(ids_path, 'w', encoding='utf-8') as f:
        json.dump(place_ids, f)

    print("--- Подготовка RAG эмбеддингов завершена! ---")

if __name__ == '__main__':
    create_embeddings()
