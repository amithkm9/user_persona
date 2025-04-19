# main.py (updated)
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import openai
from config import MISTRAL_API_KEY, OPENAI_API_KEY

# Import functionality only when needed
# from cv_extract import extract_cv_to_markdown
# from neo4j_integration import upload_persona_to_neo4j

app = FastAPI(title="CV Persona Builder")

# ========== Models ==========

class PersonaRequest(BaseModel):
    document_url: str
    answers: dict
    openai_api_key: str = None
    mistral_api_key: str = None

class PersonaResponse(BaseModel):
    persona: str
    neo4j_status: str = "pending"
    nodes_created: int = 0
    relationships_created: int = 0

class CVExtractionRequest(BaseModel):
    document_url: str
    mistral_api_key: str = None

class PersonaGenerationRequest(BaseModel):
    cv_content: str
    answers: dict
    openai_api_key: str = None

class Neo4jUploadRequest(BaseModel):
    persona_text: str

# ========== Prompt Generator ==========

def generate_prompt(cv_content: str, answers: dict) -> str:
    # Existing prompt generator code
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

    Keep the language natural and easy to understand. Return the persona as json.
    """

# ========== Split Endpoints ==========

@app.post("/extract_cv")
async def extract_cv(request: CVExtractionRequest):
    """Separate endpoint for CV extraction"""
    try:
        from cv_extract import extract_cv_to_markdown
        
        # Use API key from request or environment variable
        mistral_key = request.mistral_api_key or MISTRAL_API_KEY
        
        if not mistral_key:
            raise HTTPException(status_code=400, detail="Mistral API key is required")
        
        cv_content = extract_cv_to_markdown(request.document_url, mistral_key)
        return {"cv_content": cv_content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CV extraction failed: {str(e)}")

@app.post("/generate_persona_text")
async def generate_persona_text(request: PersonaGenerationRequest):
    """Separate endpoint for persona generation"""
    try:
        # Use API key from request or environment variable
        openai_key = request.openai_api_key or OPENAI_API_KEY
        
        if not openai_key:
            raise HTTPException(status_code=400, detail="OpenAI API key is required")
        
        # Build OpenAI prompt
        prompt = generate_prompt(request.cv_content, request.answers)
        
        # OpenAI call
        openai.api_key = openai_key
        
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI that generates structured user personas."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=700
        )
        
        persona_text = response.choices[0].message.content.strip()
        return {"persona_text": persona_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Persona generation failed: {str(e)}")

@app.post("/upload_to_neo4j")
async def upload_to_neo4j(request: Neo4jUploadRequest):
    """Separate endpoint for Neo4j upload"""
    try:
        from neo4j_integration import upload_persona_to_neo4j
        
        neo4j_result = upload_persona_to_neo4j(request.persona_text)
        return neo4j_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Neo4j upload failed: {str(e)}")

# ========== Main Endpoint ==========

@app.post("/generate_persona", response_model=PersonaResponse)
async def generate_persona(request: PersonaRequest):
    """Complete pipeline endpoint (may timeout on Vercel)"""
    try:
        # Extract CV Content
        cv_extraction = await extract_cv(CVExtractionRequest(
            document_url=request.document_url,
            mistral_api_key=request.mistral_api_key
        ))
        cv_content = cv_extraction["cv_content"]
        
        # Generate Persona
        persona_generation = await generate_persona_text(PersonaGenerationRequest(
            cv_content=cv_content,
            answers=request.answers,
            openai_api_key=request.openai_api_key
        ))
        persona_text = persona_generation["persona_text"]
        
        # Upload to Neo4j
        try:
            neo4j_result = await upload_to_neo4j(Neo4jUploadRequest(
                persona_text=persona_text
            ))
            
            return PersonaResponse(
                persona=persona_text,
                neo4j_status=neo4j_result["message"],
                nodes_created=neo4j_result["nodes_created"],
                relationships_created=neo4j_result["relationships_created"]
            )
        except Exception as e:
            # Return partial results if Neo4j upload fails
            return PersonaResponse(
                persona=persona_text,
                neo4j_status=f"Failed: {str(e)}",
                nodes_created=0,
                relationships_created=0
            )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")