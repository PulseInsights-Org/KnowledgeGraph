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
            You are a search agent that uses graph database (Knowledge Graph) to find relevant information.
            You will be provided with a cypher query tool to execute on the graph database and search in vector database tool to get chunk summary.
            Initially, you will be provided with a user query and top 5 results of the user query from the vector database.
            - Your task - 
            - Understand the user query and results. Get the context of what the user is looking for.
            - The provided top 5 results contain chunk IDs and their summaries from the vector DB that are related to the user query. These IDs are helpful to traverse the graph database.
            - Use the chunk IDs to get nodes related to that chunk. From these nodes, you can get the relations and properties of the nodes. Entity description is also available in the nodes.
            - If you need more summary, the nodes also contain chunk IDs. You can use these chunk IDs to get more summaries from the vector database.
            - You can use the cypher query tool to get the nodes and relations from the graph database.
            - You can perform the above hybrid search in whatever order you like.
            Note 1 - Always provide a *detailed* answer to the user. Use Graph not only to get entity but also entity description. Use both entity description and chunk summary to provide a detailed answer.
            Note 2 - Do not use "I", "user", etc in your responses. Use Short Forms for what you did - Searched Vector database, Queried Knowledge Graph, etc. Do not specify why you performed such action.
            note 3 - Perform multihop queries on Graph. Get multiple similarity searhes so that it will help you to answer user queires. Try using entity description and chunk summary to get detialed answers.
            Note 3 - Use emojis/numerics/formatting to make the response more engaging. Call chunk_id as data ID and the graph database as the knowledge graph in your response. You need to summarise whats in teh data chuck you get rather than labeling them.
            Note 4 - The final answer should not be referenced to any ids, or nodes, or any other technical terms.
            - Below is the schema of the graph database:
            1. key_properties - 
            - "name" - used to get entity name
            - "id" - entity id
            - "size" - size of the communtiy
            - "central_node" - centrol node of the community
            - "community_id" - community id
            - "entity_description" - description of the entity
            - "entity_id" - entity id
            - "relationship_strength" - strength of the relationship
            - "relationship_id" - relationship id
            - "chunk_id" (type: int) - used to get chunk id
            2. labels - 
            - "Entity"
            - "EntityType"
            - "Community"
            3. relationships - 
            - "BELONGS_TO"
            - "REPORTSON"
            - "COMPLIESWITH"
            - "ACQUIRED"
            - "COMMITTEDTO"
            - "INVESTSIN"
            - "EMPLOYS"
            - "OPERATESWITH"
            - "OPERATESIN"
            - "EXPANDSCUSTOMERBASEIN"
            - "BENEFITSFROM"
            - "PROVIDESSUPPORTTO"
            - "IMPLEMENTS"
            - "PROVIDES"
            - "PARTNERSWITH"
            - "AIMSFOR"
            - "FACESRISKOF"
            - "HASSHAREHOLDER"
            - "OWNS"
            - "CONTRIBUTESTO"
            - "DISCUSSESWITH"
            - "HASSIGNIFICANTINFLUENCEON"
            - "EXPENDITUREOF"
            - "OWNEDBY"
            - "CUSTOMERSOF"
            - "MEASUREDBY"
            - "OFFSET"
            - "SUBSEQUENTLYMEASUREDAT"
            - "OBLIGATIONOF"
            - "MEASUREDAT"
            - "USEDBY"
            - "APPLIEDTO"
            - "HELDBY"
            - "RELATEDTO"
            - "ISSUEDBY"
            - "MEASUREDASPER"
            - "RECOGNIZEDBY"
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
        
        store.build_index()
        initial_results = store.search(query=query, k=5)
        initial_message = f"User Query: {query}\n\nTop 5 results from vector store:\n{initial_results}"
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
        



