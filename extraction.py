from google import genai
from google.genai import types
import os
import json
from prompts.extract_ER import ER_prompt as extract_ER_prompt

class Generate_ER:

    def __init__(self, api_key, entity_file="./data/entities.json", relationship_file="./data/relationships.json"):

        self.api_key = api_key
        self.entity_file = entity_file
        self.relationship_file = relationship_file
        self.known_entities = []
    
    def get_last_id(self, file_path, item_id):

        if not os.path.exists(file_path):
            return 1
        with open(file_path, "r") as f :
            try : 
                data = json.load(f)
                if data:
                    last_id = max(item[item_id] for item in data)
                    return last_id + 1
            except json.JSONDecodeError:
                return 1
        return 1
    
    @staticmethod
    def load_json(file_path):

        if not os.path.exists(file_path):
            return []
        with open(file_path, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def append_to_file(self, file_path, new_data):

        data = self.load_json(file_path)
        data.extend(new_data)
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)

    def process_entities(self, entity_data, chunk_id):

        entity_counter = self.get_last_id(self.entity_file, "entity_id")
        new_entities = []
        for entry in entity_data:
            entity = {
                "entity_id": entity_counter,
                "chunk_id": chunk_id,
                "entity_name": entry["entity_name"],
                "entity_type": entry["entity_type"],
                "entity_description": entry["entity_description"]
            }
            new_entities.append(entity)
            entity_counter += 1

            self.known_entities.append(entry["entity_name"])
        self.append_to_file(self.entity_file, new_entities)

    def process_relations(self, relation_data):

        relationship_counter = self.get_last_id(self.relationship_file, "relationship_id")
        new_relationships = []
        for entry in relation_data:
            relationship = {
                "relationship_id": relationship_counter,
                "source": entry["source_entity"],
                "target": entry["target_entity"],
                "relationship_description": entry["relationship_description"],
                "relationship_strength": entry["relationship_strength"]
            }
            new_relationships.append(relationship)
            relationship_counter += 1
        self.append_to_file(self.relationship_file, new_relationships)
    
    
    def extract_entity_relation(self, chunk, chunk_id):

        prompt = extract_ER_prompt(previous_entities=self.known_entities)
        
        client = genai.Client(api_key=self.api_key)
        ER_json = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=chunk,
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=0.0
                ),
        )
        response_text = ER_json.text if hasattr(ER_json, "text") else str(ER_json)
        try:
            clean_json = response_text.strip().strip("```json").strip("```")
            data = json.loads(clean_json)
        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini output as JSON: {e}")
        
        entities = data.get("entities", [])
        relationships = data.get("relationships", [])
        self.process_entities(entities, chunk_id)
        self.process_relations(relationships)

        print(f"summary : {data.get('summary')}")
        return data.get("summary", "")

