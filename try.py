from build_graph import GraphBuilder
from extraction import Generate_ER
from vector_store import FaissStore
import os
import json

api_key = "AIzaSyAwjHgfipkRfZfmrTl-tDsY-7UfAKjcTu8"
chunks = []
chk_len = 8000 
chunks_path = "./data/chunks.json"

builder = GraphBuilder()
extractor = Generate_ER(api_key)

if not os.path.exists(chunks_path):
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump([], f) 

store = FaissStore(chunks_path=chunks_path)

# with open("C:\\Users\\Admin\\Desktop\\KnowledgeGraph\\data\\output.md", "r", encoding="utf-8") as f:
#     content = f.read()

# def chunk_text(text, max_length):
#     result = []
#     while len(text) > max_length:
#         split_at = text[:max_length].rfind('.')
#         if split_at == -1:
#             split_at = max_length
#         chunk = text[:split_at + 1].strip()
#         result.append(chunk)
#         text = text[split_at + 1:].strip()
#     if text:
#         result.append(text.strip())
#     return result

# chunks = chunk_text(content, chk_len)

# for i, chk in enumerate(chunks):
#     print(f"Processing chunk {i + 1} of {len(chunks)}")
#     chk_summary = extractor.extract_entity_relation(chk, i+1)
#     chunk_json = {
#         "chk_id": i + 1,
#         "chunk_summary": chk_summary
#     }

#     with open(chunks_path, "r+", encoding="utf-8") as f:
#         data = json.load(f)
#         data.append(chunk_json)
#         f.seek(0)
#         json.dump(data, f, indent=2)
    
    
# builder.create_node()
# builder.create_edge()
# builder.build_community()
# builder.add_entity_types()
# builder.push_to_auradb(uri="neo4j+ssc://57a9b645.databases.neo4j.io", username="neo4j", password="yswBDF-yFx-rmJ48mWianUe-CKqzEZLwPPYdsaOL_2k", database="neo4j")
store.build_index()

query = "Tell me about Gokaldas Exports"
results = store.search(query, k=5)

print("\n🔍 Search Results:")
for r in results:
    print(f"[Rank {r['rank']}] Chunk ID: {r['chk_id']} (Distance: {r['distance']:.4f})")
    print(r['chunk'], "\n")


query = f'''
MATCH (e:Entity)
WHERE e.chunk_id = 81
RETURN e.name AS name, e.chunk_id AS chunk_id, e.entity_id AS entity_id, e.entity_description AS entity_description
'''
results = builder.execute_query(query=query, uri="neo4j+ssc://57a9b645.databases.neo4j.io", username="neo4j", password="yswBDF-yFx-rmJ48mWianUe-CKqzEZLwPPYdsaOL_2k", database="neo4j")
print(results)

store.clear()
