from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from cv_extract import extract_cv_to_markdown
from neo4j_integration import upload_persona_to_neo4j
import openai
from config import MISTRAL_API_KEY, OPENAI_API_KEY

app = FastAPI(title="CV Persona Builder")

# ========== Models ==========

class PersonaRequest(BaseModel):
    document_url: str
    answers: dict
    openai_api_key: str = None
    mistral_api_key: str = None

class PersonaResponse(BaseModel):
    persona: str
    neo4j_status: str
    nodes_created: int
    relationships_created: int

# ========== Prompt Generator ==========

def generate_prompt(cv_content: str, answers: dict) -> str:
    skills = answers.get("skills", {})
    interests = answers.get("interests", {})
    values = answers.get("values", {})
    
    # Format the data for the prompt
    user_data = {
        "CV Content": cv_content,
        "Skills": {
            "Selected": skills.get("selected", []),
            "Additional Info": skills.get("additional_info", "")
        },
        "Interests": {
            "Selected": interests.get("selected", []),
            "Additional Info": interests.get("additional_info", "")
        },
        "Values": {
            "Selected": values.get("selected", []),
            "Additional Info": values.get("additional_info", "")
        }
    }

    return f"""
    Generate a user persona in simple English while making sure it includes all key elements needed for a knowledge graph.

    The persona should include:
    - **Name, Age, Location, Job Title, Years of Experience**
    - **Education** (Degree, University, Graduation Year)
    - **Current Company** (Name, Industry, Size, Work Culture)
    - **Skills** (Using the provided skills: {user_data["Skills"]["Selected"]} and additional info: {user_data["Skills"]["Additional Info"]})
    - **Interests** (Using the provided interests: {user_data["Interests"]["Selected"]} and additional info: {user_data["Interests"]["Additional Info"]})
    - **Values** (Using the provided values: {user_data["Values"]["Selected"]} and additional info: {user_data["Values"]["Additional Info"]})
    - **Clear relationships** between these elements, making it easy for an LLM to extract and structure the data.

    Keep the language natural and easy to understand.

    Example Format:

    ----

    John Doe is a 30-year-old Senior Software Engineer living in New York, USA. He has 8 years of experience in software development.

    He studied at MIT and completed his Bachelor's degree in Computer Science in 2015.

    Currently, he works at XYZ Corp, a large company in the Software Development industry with over 5000 employees. The company has an innovative and fast-paced work environment.

    John is skilled in Python Programming at an expert level and has intermediate experience in Project Management.

    He is passionate about AI Research and contributes to Open Source projects in his free time.

    ----

    Now generate a similar persona using the following data: {user_data}
    and convert in json format.
    """

# ========== Main Endpoint ==========

@app.post("/generate_persona", response_model=PersonaResponse)
async def generate_persona(request: PersonaRequest):
    try:
        # Use API keys from request or environment variables
        mistral_key = request.mistral_api_key or MISTRAL_API_KEY
        openai_key = request.openai_api_key or OPENAI_API_KEY
        
        # Validate API keys
        if not mistral_key:
            raise HTTPException(status_code=400, detail="Mistral API key is required")
        
        if not openai_key:
            raise HTTPException(status_code=400, detail="OpenAI API key is required")
        
        # Extract CV Content
        try:
            cv_content = extract_cv_to_markdown(request.document_url, mistral_key)
            print("CV extraction successful")
        except Exception as e:
            print(f"CV extraction failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"CV extraction failed: {str(e)}")

        # Build OpenAI prompt
        prompt = generate_prompt(cv_content, request.answers)
        print("Prompt generated successfully")

        # OpenAI call
        try:
            openai.api_key = openai_key
            
            response = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an AI that generates structured user personas."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700
            )
            print("OpenAI API call successful")
            
            persona_text = response.choices[0].message.content.strip()
        except Exception as e:
            print(f"OpenAI API call failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"OpenAI API call failed: {str(e)}")

        # Upload to Neo4j
        try:
            neo4j_result = upload_persona_to_neo4j(persona_text)
            print("Neo4j upload successful")
        except Exception as e:
            print(f"Neo4j upload failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Neo4j upload failed: {str(e)}")

        return PersonaResponse(
            persona=persona_text,
            neo4j_status=neo4j_result["message"],
            nodes_created=neo4j_result["nodes_created"],
            relationships_created=neo4j_result["relationships_created"]
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")