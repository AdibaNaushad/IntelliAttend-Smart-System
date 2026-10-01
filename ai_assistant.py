import requests

# Default Ollama local API endpoint
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma2:2b"

def get_ai_explanation(data, action_type):
    # Structure the facts so Gemma cannot invent data
    base_info = (
        f"Student '{data.get('student')}' has an attendance of {data.get('attendance')}%. "
        f"They were present for {data.get('present')} out of {data.get('total')} total classes. "
        f"The required attendance threshold is {data.get('required')}%."
    )
    
    # Assign specific prompts based on the button clicked
    if action_type == "explain":
        prompt = f"{base_info} Briefly explain this current attendance status in one short paragraph, stating clearly if they are below or above the requirement."
    elif action_type == "improve":
        prompt = f"{base_info} Give a short, practical, and encouraging 2-sentence advice on how to improve or maintain this attendance."
    elif action_type == "summary":
        prompt = f"{base_info} Provide a very concise 1-sentence summary of this student's attendance."
    else:
        prompt = f"{base_info} Summarize this attendance."

    # Strict grounding instructions
    prompt += " Do not invent any numbers. Do not output markdown or code, just plain text."

    try:
        # Send the request to local Ollama
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False
        }, timeout=15)

        if response.status_code == 200:
            return True, response.json().get("response", "").strip()
        else:
            return False, "AI service returned an error."
            
    except requests.exceptions.RequestException:
        return False, "AI service is currently unavailable."