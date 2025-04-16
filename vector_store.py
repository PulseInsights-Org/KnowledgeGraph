import numpy as np
import faiss
import json
from sentence_transformers import SentenceTransformer

class FaissStore():
    def __init__(self, chunks_path = "./data/chunks.json", vectors_path = "./data/vectors.index", id_map_path = "./data/id_map.json"):
        self.vectors_path = vectors_path
        self.id_map_path = id_map_path
        self.dim = 384
        self.chunks_path = chunks_path
        self.index = faiss.IndexFlatL2(self.dim)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_id_map = {}
        self.vector_idx = 0
        self.chunks = self._load_chunks()
    
    def _load_chunks(self):
        with open(self.chunks_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def build_index(self):
        for chunk in self.chunks:
            print(f"Processing index {chunk['chk_id']}")
            text = chunk["chunk_summary"]
            chk_id = chunk["chk_id"]

            embedding = self.model.encode([text])[0]
            embedding = np.array(embedding).astype('float32').reshape(1, -1)

            self.index.add(embedding)
            self.vector_id_map[self.vector_idx] = chk_id
            self.vector_idx += 1
        self.save()
    
    def search(self, query, k=3):
        query_vec = self.model.encode([query])
        query_vec = np.array(query_vec).astype('float32')

        distances, indices = self.index.search(query_vec, k)

        results = []
        for rank, idx in enumerate(indices[0]):
            chunk_id = self.vector_id_map.get(idx, "Unknown")
            chunk_text = next((c["chunk_summary"] for c in self.chunks if c["chk_id"] == chunk_id), "")
            results.append({
                "rank": rank + 1,
                "chk_id": chunk_id,
                "distance": float(distances[0][rank]),
                "chunk": chunk_text
            })

        return results

    def save(self):
        with open(self.vectors_path, 'w', encoding='utf-8') as f:
            pass
        faiss.write_index(self.index, self.vectors_path)
        with open(self.id_map_path, "w", encoding="utf-8") as f:
            json.dump(self.vector_id_map, f, indent=4)
    
    def load(self):
        self.index = faiss.read_index(self.vectors_path)
        with open(self.id_map_path, "r", encoding="utf-8") as f:
            self.vector_id_map = json.load(f)
        print("Index and ID map loaded.")
    
    def clear(self):
        self.index = faiss.IndexFlatL2(self.dim)  # Create a fresh, empty index
        self.vector_id_map = {}
        self.vector_idx = 0

    def load(self):
        self.index = faiss.read_index(self.vectors_path)
        with open(self.id_map_path, "r", encoding="utf-8") as f:
            self.vector_id_map = json.load(f)
        self.vector_id_map = {int(k): v for k, v in self.vector_id_map.items()}
        self.vector_idx = max(map(int, self.vector_id_map.keys())) + 1 if self.vector_id_map else 0
        self.index_loaded = True
        print("Index and ID map loaded.")