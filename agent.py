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
            You are a search agent that uses graph database to find relevant information.
            You will be provided with a cypher query tool to execute on the graph database and search in vector database tool to get chunk summary.
            Intially you will be provided with user query and top 5 results of user query from vector database.
            - Your task - 
            - Understand user query and results. Get the context of what user is looking for.
            - The provided top 5 results containes chunk ids and their summaries from vector DB that are related to user query. These ids are helpful to traverse the graph database.
            - Use the chuck ids to get nodes related to that chuck. From these nodes you can get the relations and properties of the nodes.
            - If you need more summary, the nodes also contain chunk ids. You can use these chunk ids to get more summaries from vector database.
            - You can use the cypher query tool to get the nodes and relations from the graph database.
            - You can perform the above hybrid search in whatever order you like.
            Note 1 - Always provide detiled answer to the user.
            Note 2 - You have to provide an answer to user by using the tools provided to you with user query. If you dont get any semantic results intially, use tool to get one.
            Note 3 - Use emojis to make the response more engaging.
            - Below is the schema of the graph database:
            1. key_properties - "name", "id", "size", "central_node", "community_id", "entity_description","entity_id", "relationship_strength","relationship_id","chunk_id"
            Note - chunk_id is type *int*.
            2. labels - "Entity", "EntityType", "Community"
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
    
    def QAgent(self, query):
        
        store.build_index()
        model_responses = []
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
        



