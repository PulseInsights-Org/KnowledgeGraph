from google import genai
from google.genai import types
from build_graph import GraphBuilder
from vector_store import FaissStore
from google.genai.types import FunctionDeclaration, GenerateContentConfig, Part, Tool

chunks_path = "./data/chunks.json"
builder = GraphBuilder()
store = FaissStore(chunks_path=chunks_path)



class KGAgent():
    def __init__(self, api_key):
        self.sys_prompt = '''
            You are an advanced search agent specializing in knowledge graph navigation and information retrieval.
            # CAPABILITIES
            You harness the power of graph database structures (Knowledge Graph) and vector embeddings to deliver comprehensive,
            accurate information in response to user queries.

            # AVAILABLE TOOLS
            1. Cypher Query Tool - Execute queries on the graph database
            2. Vector Search Tool - Retrieve relevant chunk summaries based on semantic similarity

            # SEARCH METHODOLOGY
            When presented with a user query:
            1.EXPLORE the Knowledge Graph to comprehensively understand:
            - Entity relationships and their semantic meaning
            - Community structures and their composition
            - Available information types and their interconnections
            
            2.ANALYZE the user query and initial vector semantic search results to:
            - Identify key information needs
            - Determine relevant entities and relationships
            - Understand the contextual framework of the inquiry

            3. ITERATIVE SEARCH PROCESS:
            - Use initial vector search results to identify key entities
            - Query the Knowledge Graph for these entities and their relationships
            - Perform additional vector searches based on newly discovered entities
            - Execute multi-hop relationship queries to uncover deeper connections
            - Continue this iterative process until comprehensive information is gathered

            4.INTERPRET all search results which provide:
            - Semantically similar chunks with their IDs and summaries
            - Entity descriptions and relationships from the Knowledge Graph
            - Connection patterns and contextual significance

            # DATA STRUCTURE UNDERSTANDING
            - Each node contains crucial metadata including "chunk_id" and "entity_description"
            - Utilize the provided schema (key_properties, labels, relationships) to navigate the graph effectively
            - Extract both direct information and multi-hop relationship insights

            # RESPONSE GUIDELINES
            1.Deliver detailed, comprehensive answers synthesizing:
            - Entity descriptions from the Knowledge Graph
            - Chunk summaries from vector search results
            - Relationship context between relevant entities

            2.Structure your response with:
            - Clear step-by-step explanation of your search methodology
            - Formatted sections using emojis, numbering, and appropriate text formatting
            - Refer to "chunk_id" as "data ID" and "graph database" as "Knowledge Graph"

            3. Synthesize information to:
            - Summarize chunk content rather than simply labeling them
            - Present multi-hop query results to provide depth and context
            - Exclude technical references (IDs, node labels, etc.) in the final answer

            # THOROUGHNESS REQUIREMENTS
            - Never conclude your search after initial findings
            - Utilize both tools extensively and repeatedly
            - Perform multiple vector searches with varied query formulations
            - Execute diverse Cypher queries to explore different relationship paths
            - Prioritize depth and comprehensiveness of information over brevity
            - Ensure all relevant entity relationships are explored through multi-hop queries

            # KEY DATABASE ELEMENTS
            - Key Properties: name, id, size, central_node, community_id, entity_description, entity_id, relationship_strength, relationship_id, chunk_id (type- integer)
            - Labels: Entity, EntityType, Community
            - Relationships: BELONGS_TO, REPORTSON, COMPLIESWITH, ACQUIRED, COMMITTEDTO, INVESTSIN, EMPLOYS, OPERATESWITH, OPERATESIN, EXPANDSCUSTOMERBASEIN, 
                BENEFITSFROM, PROVIDESSUPPORTTO, IMPLEMENTS, PROVIDES, PARTNERSWITH, AIMSFOR, FACESRISKOF, HASSHAREHOLDER, OWNS, CONTRIBUTESTO, DISCUSSESWITH, 
                HASSIGNIFICANTINFLUENCEON, EXPENDITUREOF, OWNEDBY, CUSTOMERSOF, MEASUREDBY, OFFSET, SUBSEQUENTLYMEASUREDAT, OBLIGATIONOF, MEASUREDAT, USEDBY, 
                APPLIEDTO, HELDBY, RELATEDTO, ISSUEDBY, MEASUREDASPER, RECOGNIZEDBY
        '''
        self.tools = []
        self.api_key = api_key
        self.chat = None
        self.define_tools()
        self.define_model()
        
    
    def define_tools(self):
        run_query = FunctionDeclaration(
            name = builder.execute_query.__name__,
            description = "Execute cypher query on graph database",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Cypher query to execute on graph database"
                    },
                    },
                "required": ["query"],
                },
        )

        search_VDB = FunctionDeclaration(
            name = store.search.__name__,
            description = "Get chunk summary from vector database",
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query to search in vector database"
                    },
                    "k": {
                        "type": "integer",
                        "description": "Number of results to return"
                    },
                },
                "required": ["query", "k"],
            }
        )

        self.tools = Tool(
            function_declarations=[
                run_query,
                search_VDB,
            ]
        )

    def define_model(self):
        client = genai.Client(api_key=self.api_key)
        self.chat = client.chats.create(
                         model="gemini-2.0-flash",
                        config=GenerateContentConfig(
                                temperature=1,
                                tools=[self.tools],
                                system_instruction=self.sys_prompt
                                ),
                            )
    
    async def QAgent(self, query):
        
        if not hasattr(store, 'index_loaded') or not store.index_loaded:
            store.load()
        store.index_loaded = True 
        
        initial_results = store.search(query=query, k=5)
        initial_message = f"User Query: {query} \n\n Initial Results: {initial_results} \n\n"
        response = self.chat.send_message(initial_message)

        while True:
            if response.function_calls is None:
                text_response = "".join(part.text for part in response.candidates[0].content.parts if part.text is not None)
                print("Final Answer:", text_response)
                if text_response:
                    # model_responses.append(text_response)
                    # full_response = "\n\n".join(model_responses)
                    # return full_response
                    yield text_response
                    return  

            function_responses = []

            for func_call in response.function_calls:
                function_name = func_call.name
                args = func_call.args
                text_response = "".join(part.text for part in response.candidates[0].content.parts if hasattr(part, 'text') and part.text is not None)
                if text_response:
                    print("Model Response:", text_response)
                    # model_responses.append(text_response)
                    yield text_response

                print(f"Executing function: {function_name}")
                if function_name == "execute_query":
                    query_text = args.get("query")
                    print("Cypher Query to be executed:", query_text)
                    data = builder.execute_query(query_text,uri="neo4j+ssc://57a9b645.databases.neo4j.io", username="neo4j", password="yswBDF-yFx-rmJ48mWianUe-CKqzEZLwPPYdsaOL_2k", database="neo4j")
                elif function_name == "search":
                    query_text = args.get("query")
                    k = args.get("k", 5)  
                    print("Vector Search Query:", query_text, f"k={k}")
                    data = store.search(query=query_text, k=k)
                else:
                    print(f"Function {function_name} is not implemented.")
                    data = {"error": f"Function {function_name} not found"}
                
                print("Data extracted:", data)
                function_responses.append(
                    Part.from_function_response(
                        name=function_name,
                        response={"results": data}
                    )
                )
        
            response = self.chat.send_message(function_responses)
        



