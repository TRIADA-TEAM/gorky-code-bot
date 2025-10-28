import json
import numpy as np
import os
import faiss
from sentence_transformers import SentenceTransformer
import logging

EMBEDDING_MODEL = 'all-MiniLM-L6-v2'

class RAGFallback:
    def __init__(self):
        self.model = None
        self.places_data = []
        self.place_ids = []
        self.embeddings = None
        self.index = None
        self._load_all_data()

    def _load_all_data(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(os.path.dirname(base_dir), 'data')
        places_path = os.path.join(data_dir, 'places.json')
        embeddings_path = os.path.join(data_dir, 'embeddings.npy')
        ids_path = os.path.join(data_dir, 'place_ids.json')

        try:
            logging.info("Загрузка данных для фолбэка RAG...")
            self.model = SentenceTransformer(EMBEDDING_MODEL)

            with open(places_path, 'r', encoding='utf-8') as f:
                self.places_data = json.load(f)
            
            self.embeddings = np.load(embeddings_path)
            with open(ids_path, 'r', encoding='utf-8') as f:
                self.place_ids = json.load(f)

            self.places_map = {place['id']: place for place in self.places_data}

            if self.embeddings is not None:
                dimension = self.embeddings.shape[1]
                self.index = faiss.IndexFlatL2(dimension)
                self.index.add(self.embeddings.astype('float32'))
                logging.info("Система фолбэка RAG успешно загружена.")

        except FileNotFoundError as e:
            logging.error(f"Данные для фолбэка RAG не найдены: {e}. Система фолбэка будет отключена.")
            self.index = None
        except Exception as e:
            logging.error(f"Произошла ошибка при загрузке системы фолбэка RAG: {e}")
            self.index = None

    def find_places_by_semantic_search(self, query: str, top_k: int = 5) -> list:
        if self.index is None or self.model is None:
            logging.warning("Система фолбэка RAG недоступна.")
            return []

        try:
            logging.info(f"Выполняется семантический поиск по запросу: '{query}'")
            query_embedding = self.model.encode([query])
            distances, indices = self.index.search(query_embedding.astype('float32'), top_k)

            found_places = []
            for i in indices[0]:
                if i < len(self.place_ids):
                    place_id = self.place_ids[i]
                    place = self.places_map.get(place_id)
                    if place:
                        found_places.append(place)
            
            logging.info(f"Семантический поиск нашел {len(found_places)} мест.")
            return found_places

        except Exception as e:
            logging.error(f"Произошла ошибка во время семантического поиска: {e}")
            return []
