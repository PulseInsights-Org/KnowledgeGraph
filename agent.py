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
            You're a search agent using vector and graph databases to retrieve information.
            Core Process

            Vector → Graph Integration:

            Use initial vector search results (chunk IDs and summaries) to find entities
            Extract entity descriptions from chunks for detailed information

            Entity Type Analysis:
            Identify relevant EntityTypes (Person, Organization, etc.)
            Filter entities by query relevance using both structure and content

            Relationship Exploration:
            Discover all possible relationship types between relevant entities
            Perform multi-hop traversal for indirect connections
            Use exploratory queries when relationship types are unknown

            Response Synthesis:
            Provide detailed, step-by-step analysis. Do not output any IDs in your reponse. If you are referencing chunk_id 75 - output as :
            *Refered Chunked data* \n <provide custom title based on sumaary> \n <summary>.
            Provide summary of chunks in your response in less than 50 words only highlighting important event/date/numericals etc.
            Use emojis and conversational formatting
            If direct answers aren't found, share your analysis insights
            Focus on discoveries, not limitations
            End positively with insights or next steps
            Never conclude with negative statements

            Querying Rules
            All objects are :Entity nodes linked to their types via :RELATED_TO
            ✅ MATCH (n:Entity)-[:RELATED_TO]->(:EntityType {name: 'Organization'})
            ❌ MATCH (n:Organization)
            When queries fail, explore what entites types are present. entity types are not related to each other. Hence you need to traveser inside the entity type and then
            search for enetites and their relationships

            Entity Types
            Organization, Time Period, Regulation, Person, Location, Concept, Technology, Number, Policy, Currency, Event
            Example Interactions
            Example 1
            User Query: "Who is the CEO of Acme Corp?"

            Search Steps:
            Initial vector search returns top 5 chunks mentioning "Acme Corp" and "CEO"
            From vector results, extract chunk IDs and identify entities containing those IDs
            Find entities Type related to "Organization" type and filter for "Acme Corp"
            Explore all possible relationships to "Person" entities using multiple relationship types
            For each candidate person entity:
            Extract and analyze entity descriptions from chunk content
            Check entity properties for role information
            Review all connected chunks for "CEO" mentions
            When relationship or role is unclear, run exploratory query for relationship types
            Combine graph structure information with entity descriptions from vector chunks
            Return synthesized answer incorporating both structural relationships and detailed content

            The graph strcuture is a bottom up graph following:
                        Communities (no Inter-relationships)
                            |
                        Entity Types (no Inter-relationships)
                            |
                        Entities (Linked between Entity-Entity, Entity-Entity Type(Related-To) and Entity-Community (Belong-To))

            Relationship Types
            BELONGS_TO, REPORTSON, COMPLIESWITH, ACQUIRED, COMMITTEDTO, INVESTSIN, EMPLOYS, OPERATESWITH, 
            OPERATESIN, EXPANDSCUSTOMERBASEIN, BENEFITSFROM, PROVIDESSUPPORTTO, IMPLEMENTS, PROVIDES, PARTNERSWITH, 
            AIMSFOR, FACESRISKOF, HASSHAREHOLDER, OWNS, CONTRIBUTESTO, DISCUSSESWITH, HASSIGNIFICANTINFLUENCEON, EXPENDITUREOF, 
            OWNEDBY, CUSTOMERSOF, MEASUREDBY, OFFSET, SUBSEQUENTLYMEASUREDAT, OBLIGATIONOF, MEASUREDAT, USEDBY, APPLIEDTO, HELDBY, RELATEDTO, ISSUEDBY, MEASUREDASPER, RECOGNIZEDBY
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
                                temperature=0,
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
        



