import re
import json
from langchain_neo4j import Neo4jGraph
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

NEO4J_URI = "neo4j+s://e78401af.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "uP2wXbd9Aa2a6WxbpgT_3DuZZscQ4yn52nGYrmJjseU"
GROQ_API_KEY = "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"
MODEL_NAME = "llama-3.3-70b-versatile"

graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)
llm = ChatGroq(groq_api_key=GROQ_API_KEY, model_name=MODEL_NAME)

def upload_persona_to_neo4j(persona_text: str) -> dict:
    prompt_template = """
    I need you to create a knowledge graph from the following persona data:

    {text}

    Your task is to extract nodes and relationships according to these specifications:

    Node types: Person, Skill, Company, Interest, Education, Project, Achievement, Extracurricular
    Relationship types: WORKS_AT, HAS_SKILL, INTERESTED_IN, EDUCATED_AT, WORKED_ON, ACHIEVED, ENGAGED_IN

    Return ONLY a COMPLETE JSON object with the following structure:
    {{
      "nodes": [
        {{
          "id": "unique_id_1",
          "type": "Person",
          "properties": [
            {{"key": "name", "value": "John Doe"}},
            {{"key": "age", "value": 30}}
          ]
        }},
        ...
      ],
      "relationships": [
        {{
          "source_node_id": "unique_id_1",
          "target_node_id": "unique_id_2",
          "type": "WORKS_AT"
        }},
        ...
      ]
    }}

    IMPORTANT INSTRUCTIONS:
    1. DO NOT use placeholders or ellipses (...) - provide the complete JSON
    2. DO NOT include any explanation text before or after the JSON
    3. Always use ONLY "key" (never "name") for property keys
    4. Ensure all IDs are unique and contain no spaces (use underscores)
    5. For relationships, ALWAYS use the exact field names "source_node_id" and "target_node_id"
    6. Your response must be valid, parseable JSON and nothing else
    """

    prompt = PromptTemplate.from_template(prompt_template).format(text=persona_text)
    response = llm.invoke(prompt)
    response_text = response.content

    match = re.search(r'(\{[\s\S]*\})', response_text)
    if not match:
        raise ValueError("No valid JSON found in LLM response")

    try:
        graph_data = json.loads(match.group(1))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {str(e)}")

    if "nodes" not in graph_data:
        raise ValueError("No 'nodes' found in graph data")
    if "relationships" not in graph_data:
        raise ValueError("No 'relationships' found in graph data")
    nodes_created = 0
    nodes_reused = 0
    relationships_created = 0
    # Process nodes - For non-Person nodes, MERGE on name to prevent duplicates
    for node in graph_data["nodes"]:
        if "id" not in node or "type" not in node:
            continue
        
        node_id = node["id"]
        node_type = node["type"]
        props = {prop["key"]: prop["value"] for prop in node.get("properties", [])}
        props["id"] = node_id
        
        if node_type == "Person":
            # Always create new Person nodes
            graph.query(f"CREATE (n:`{node_type}`) SET n = $props", {"props": props})
            nodes_created += 1
        else:
            # For non-Person nodes like Skills, merge on name
            name_value = props.get("name")
            if name_value:
                graph.query(
                    f"""
                    MERGE (n:`{node_type}` {{name: $name}})
                    ON CREATE SET n = $props
                    """, 
                    {"name": name_value, "props": props}
                )
                nodes_reused += 1
            else:
                # If no name, just create the node
                graph.query(f"CREATE (n:`{node_type}`) SET n = $props", {"props": props})
                nodes_created += 1

    # Process relationships
    for rel in graph_data["relationships"]:
        if "source_node_id" not in rel or "target_node_id" not in rel or "type" not in rel:
            continue
        
        source_id = rel["source_node_id"]
        target_id = rel["target_node_id"]
        rel_type = rel["type"]
        
        # Get node information
        source_type = next((n["type"] for n in graph_data["nodes"] if n["id"] == source_id), None)
        target_type = next((n["type"] for n in graph_data["nodes"] if n["id"] == target_id), None)
        
        source_name = next((prop["value"] for n in graph_data["nodes"] 
                           if n["id"] == source_id 
                           for prop in n.get("properties", [])
                           if prop["key"] == "name"), None)
        
        target_name = next((prop["value"] for n in graph_data["nodes"] 
                           if n["id"] == target_id 
                           for prop in n.get("properties", [])
                           if prop["key"] == "name"), None)
        
        # Create relationship based on node types
        if source_type == "Person" and target_name and target_type != "Person":
            # Person to non-Person (like Person HAS_SKILL Skill)
            graph.query(
                f"""
                MATCH (a:`{source_type}` {{id: $source_id}}), (b:`{target_type}` {{name: $target_name}})
                CREATE (a)-[r:`{rel_type}`]->(b)
                """,
                {"source_id": source_id, "target_name": target_name}
            )
        elif source_name and source_type != "Person" and target_type == "Person":
            # Non-Person to Person
            graph.query(
                f"""
                MATCH (a:`{source_type}` {{name: $source_name}}), (b:`{target_type}` {{id: $target_id}})
                CREATE (a)-[r:`{rel_type}`]->(b)
                """,
                {"source_name": source_name, "target_id": target_id}
            )
        elif source_type != "Person" and target_type != "Person" and source_name and target_name:
            # Non-Person to Non-Person
            graph.query(
                f"""
                MATCH (a:`{source_type}` {{name: $source_name}}), (b:`{target_type}` {{name: $target_name}})
                CREATE (a)-[r:`{rel_type}`]->(b)
                """,
                {"source_name": source_name, "target_name": target_name}
            )
        else:
            # Default case: match by ID
            graph.query(
                f"""
                MATCH (a {{id: $source_id}}), (b {{id: $target_id}})
                CREATE (a)-[r:`{rel_type}`]->(b)
                """,
                {"source_id": source_id, "target_id": target_id}
            )
        relationships_created += 1

    node_count = graph.query("MATCH (n) RETURN count(n) AS count")[0]["count"]
    rel_count = graph.query("MATCH ()-[r]->() RETURN count(r) AS count")[0]["count"]

    return {
        "message": "Graph uploaded successfully",
        "nodes_created": nodes_created,  # This was missing
        "nodes_reused": nodes_reused,
        "relationships_created": relationships_created,
        "total_nodes_in_db": node_count,
        "total_relationships_in_db": rel_count
    }