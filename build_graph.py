import networkx as ntx
from extraction import Generate_ER
import community as community_louvain
from neo4j import GraphDatabase

class GraphBuilder:
    def __init__(self, entity_file="./data/entities.json", relationship_file="./data/relationships.json"):
        self.G = ntx.DiGraph()
        self.entity_file = entity_file
        self.relationship_file = relationship_file
        self.communities = {}  

    def create_node(self):
        data = Generate_ER.load_json(self.entity_file)

        for ent in data:
            self.G.add_node(
                ent["entity_name"],
                chunk_id=ent["chunk_id"],
                entity_id=ent["entity_id"],
                entity_description=ent["entity_description"],
                node_type="entity" 
            )

    def create_edge(self):
        data = Generate_ER.load_json(self.relationship_file)
        for rel in data:
            self.G.add_edge(
                rel["source"],
                rel["target"],
                relationship_id=rel["relationship_id"],
                relationship_description=rel["relationship_description"],
                relationship_strength=int(rel["relationship_strength"])
            )

    def build_community(self):
        G_undirected = self.G.to_undirected()
        partition = community_louvain.best_partition(G_undirected, weight='relationship_strength')
        
        ntx.set_node_attributes(self.G, partition, name='community')
        community_counts = {}
        for node, comm_id in partition.items():
            if comm_id not in community_counts:
                community_counts[comm_id] = 0
            community_counts[comm_id] += 1
        
        self.communities = {}
        for comm_id in set(partition.values()):
            comm_nodes = [node for node, c_id in partition.items() if c_id == comm_id]
            subgraph = G_undirected.subgraph(comm_nodes)
            try:
                centrality = ntx.eigenvector_centrality(subgraph)
                central_node = max(centrality, key=centrality.get)
            except:
                centrality = ntx.degree_centrality(subgraph)
                central_node = max(centrality, key=centrality.get)
            
            self.communities[comm_id] = {
                "name": central_node,
                "size": community_counts[comm_id],
                "members": comm_nodes
            }
    
    def add_entity_types(self):
        data = Generate_ER.load_json(self.entity_file)
        
        for ent in data:
            self.G.add_node(
                    ent["entity_type"],
                    node_type="entity_type"  
                )
        for ent in data:
            self.G.add_edge(
                ent["entity_name"],
                ent["entity_type"],
                relationship_description="is_a",
                relationship_strength=1
            )
    
    def get_community_name(self, community_id):
        if community_id not in self.communities:
            return f"Community {community_id}"
        
        return f"Community {community_id}: {self.communities[community_id]['name']}"

    def push_to_auradb(self, uri, username, password, database=None):
        try:
            if not hasattr(self, 'communities') or not self.communities:
                self.build_community()
        
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            with driver.session(database=database) as session:
                session.run("MATCH (n) DETACH DELETE n")
                
                try:
                    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Entity) REQUIRE n.name IS UNIQUE")
                    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:EntityType) REQUIRE n.name IS UNIQUE")
                    session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (n:Community) REQUIRE n.id IS UNIQUE")
                except Exception as e:
                    print(f"Warning: Could not create constraints: {e}")
                
                for comm_id, comm_data in self.communities.items():
                    session.run("""
                        CREATE (c:Community {
                            id: $id,
                            name: $name,
                            size: $size,
                            central_node: $central_node
                        })
                    """, {
                        "id": comm_id,
                        "name": self.get_community_name(comm_id),
                        "size": comm_data["size"],
                        "central_node": comm_data["name"]
                    })
                
                node_count = 0
                for node, attrs in self.G.nodes(data=True):
                    node_type = attrs.get('node_type', 'Unknown')
                    community_id = attrs.get('community')
                    properties = {
                        "name": node,
                        "community_id": community_id
                    }
                    
                    for key, value in attrs.items():
                        if key not in ['node_type', 'community']:
                            properties[key] = value
                    
                    if node_type == "entity_type":
                        query = """
                            MERGE (n:EntityType {name: $name})
                            SET n += $properties
                        """
                    else:
                        query = """
                            MERGE (n:Entity {name: $name})
                            SET n += $properties
                        """
                    
                    session.run(query, {
                        "name": node,
                        "properties": properties
                    })
                    
                    if community_id is not None:
                        session.run("""
                            MATCH (n), (c:Community {id: $community_id})
                            WHERE n.name = $node_name
                            CREATE (n)-[:BELONGS_TO]->(c)
                        """, {
                            "node_name": node,
                            "community_id": community_id
                        })
                    
                    node_count += 1
                    if node_count % 100 == 0:
                        print(f"Processed {node_count} nodes")
                
                # Add all edges
                edge_count = 0
                for source, target, attrs in self.G.edges(data=True):
                    rel_desc = attrs.get('relationship_description', 'RELATED_TO')
                    rel_type = ''.join(c for c in rel_desc.upper() if c.isalnum() or c == '_')
                    if not rel_type:
                        rel_type = "RELATED_TO"
                    
                    properties = {}
                    for key, value in attrs.items():
                        if key != 'relationship_description':
                            properties[key] = value
                    
                    session.run("""
                        MATCH (a), (b)
                        WHERE a.name = $source AND b.name = $target
                        CREATE (a)-[r:%s $properties]->(b)
                    """ % rel_type, {
                        "source": source,
                        "target": target,
                        "properties": properties
                    })
                    
                    edge_count += 1
                    if edge_count % 500 == 0:
                        print(f"Processed {edge_count} relationships")
                
                print(f"Successfully pushed graph to Neo4j AuraDB: {node_count} nodes and {edge_count} relationships")
            
            driver.close()
            return True
            
        except Exception as e:
            print(f"Error pushing to Neo4j AuraDB: {e}")
            return False
    
    def execute_query(self, query, uri, username, password, database=None):
        try:
            driver = GraphDatabase.driver(uri, auth=(username, password))
            
            with driver.session(database=database) as session:
                result = session.run(query)
                return [record.data() for record in result]
        
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
