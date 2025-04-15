import json

def ER_prompt(previous_entities=None):
    previous_entities_context = ""
    if previous_entities and len(previous_entities) > 0:
        previous_entities_json = previous_entities
        previous_entities_context = f"""
        For consistency, here are entities that have already been identified in previous chunks of text:
        {previous_entities_json}
        When identifying entities in this new chunk:
        1. If an entity matches or is highly similar to one already identified (listed above), use the EXACT SAME entity_name that was used previously
        2. Only create new entities for concepts that are truly not represented in the existing entities
        3. Add any new information about existing entities to your relationship descriptions rather than creating duplicate entities
        4. If entity is already present, just provide the relationship from it without again defining the entity
        """
    
    extract_ER_prompt = f'''
    Given a text, understand the context of text and generate a summary of it. The summary must focus on domain specific information which should be 
    highlight the key concepts, components, and changes or watsoever is provided within the text in not more than 500 words.
    From this summary generated, you need to extract entities are relationships by following the below instructions:
    - Entity Consistency: Use consistent names for entities throughout the document. For example, if "John Smith" is mentioned as "John", "Mr. Smith", and "John Smith" in different places, use a single consistent form (preferably the most complete one) in all triples.
    - Atomic Terms: Identify distinct key terms (e.g., objects, locations, organizations, acronyms, people, conditions, concepts, feelings). Avoid merging multiple ideas into one term (they should be as "atomistic" as possible).
    - Unified References: Replace any pronouns (e.g., "he," "she," "it," "they," etc.) with the actual referenced entity, if identifiable.
    - Standardize terminology: If the same concept appears with slight variations (e.g., "artificial intelligence" and "AI"), use the most common or canonical form consistently.
    - Aim for precision in entity naming - use specific forms that distinguish between similar but different entities
    - Aviod common and under values information like personal names, address, random dates, locations etc. Include these details only if they are providing some significance to the text. 
    - {previous_entities_context}
    -Steps-
    1. Identify all entities. For each identified entity, extract the following information:
    - entity_name: Name of the entity (maintain consistency with previously identified entities if provided)
    - entity_type: Type of the entity (e.g., person, organization, location, event, etc.)
    - entity_description: A detailed description of the entity which includes referencing of both generated summary as well as the text provided.
    
    2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
    For each pair of related entities, extract the following information:
    - source_entity: name of the source entity, as identified in step 1
    - target_entity: name of the target entity, as identified in step 1
    - relationship_description: explanation as to why you think the source entity and the target entity are related to each other
    - relationship_strength: a numeric score (1-10) indicating strength of the relationship between the source entity and target entity
    
    3. Output format : strictly adhere to the following JSON format:
    {{
    "summary": "<summary>",
    "entities": [
        {{
            "entity_name" : "<entity_name>",
            "entity_type" : "<entity_type>",
            "entity_description" : "<entity_description>"
        }}....
    ],
    "relationships": [
        {{
            "source_entity" : "<source_entity>",
            "target_entity" : "<target_entity>",
            "relationship_description" : "<relationship_description>",
            "relationship_strength" : "<relationship_strength>"
        }}....
    ]
    }}
    '''
    
    return extract_ER_prompt

