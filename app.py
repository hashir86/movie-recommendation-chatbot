import streamlit as st
import requests
import os
import json
import random
import re
import google.generativeai as genai

# Load API keys from JSON file
#def load_api_keys():
#    with open("api_keys.json", "r") as f:
#        return json.load(f)

# API keys
TMDB_API_KEY = st.secrets["tmdb_api_key"]
GENAI_API_KEY = st.secrets["genai_api_key"]

# Configure Google Generative AI
genai.configure(api_key=GENAI_API_KEY)

# Fetch genres from TMDB API
@st.cache_data
def get_genres():
    try:
        url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}&language=en-US"
        response = requests.get(url).json()
        genres = {genre["name"].lower(): genre["id"] for genre in response.get("genres", [])}
        genres.update({
            "animated": genres.get("animation"),
            "cartoon": genres.get("animation"),
            "sci-fi": genres.get("science fiction"),
        })
        return genres
    except Exception:
        return {}

def get_movie_recommendations(genre=None, actor=None, similar_to=None, director=None):
    try:
        url = f"https://api.themoviedb.org/3/discover/movie?api_key={TMDB_API_KEY}&language=en-US&sort_by=vote_average.desc&vote_count.gte=1000"
        
        if genre:
            genres = get_genres()
            genre_ids = [str(genres.get(g.lower())) for g in genre if genres.get(g.lower())]
            if genre_ids:
                url += f"&with_genres={','.join(genre_ids)}"
            else:
                return f"I couldn't find the genres '{', '.join(genre)}'. Please try different ones."
        
        elif actor:
            actor_ids = [get_actor_id(a) for a in actor if get_actor_id(a)]
            if actor_ids:
                url += f"&with_cast={','.join(map(str, actor_ids))}"
            else:
                return f"I couldn't find the actors '{', '.join(actor)}'. Please try different ones."
        
        elif similar_to:
            movie_id = get_movie_id(similar_to)
            if movie_id:
                url = f"https://api.themoviedb.org/3/movie/{movie_id}/similar?api_key={TMDB_API_KEY}&language=en-US"
        
        elif director:
            director_id = get_director_id(director)
            if director_id:
                url += f"&with_crew={director_id}"
        
        response = requests.get(url).json()
        results = response.get("results") or response.get("cast", [])
        
        if results:
            random.shuffle(results)  # Shuffle results for variety
            movies = results[:5]  # Take the first 5 movies
            return "\n".join([
                f"- {movie['title']} ({movie.get('release_date', 'N/A')[:4]}) - Rating: {movie['vote_average']}" 
                for movie in movies
            ])
        return "No recommendations found."
    except Exception as e:
        return f"Error fetching recommendations: {e}"


# Get actor ID from TMDB API
def get_actor_id(actor_name):
    try:
        url = f"https://api.themoviedb.org/3/search/person?api_key={TMDB_API_KEY}&query={actor_name}&language=en-US"
        response = requests.get(url).json()
        return response.get("results", [{}])[0].get("id")
    except Exception:
        return None

# Get movie ID by title
def get_movie_id(movie_title):
    try:
        url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_title}&language=en-US"
        response = requests.get(url).json()
        results = response.get("results", [])
        return results[0]["id"] if results else None
    except Exception:
        return None
# Get director ID from TMDB API
def get_director_id(director_name):
    try:
        url = f"https://api.themoviedb.org/3/search/person?api_key={TMDB_API_KEY}&query={director_name}&language=en-US"
        response = requests.get(url).json()
        return response.get("results", [{}])[0].get("id")
    except Exception:
        return None

def detect_intent_and_entity(user_prompt):
    genres = get_genres()
    prompt_lower = user_prompt.lower()
    
    # Detect multiple genres
    detected_genres = [
        genre for genre in genres.keys() if re.search(rf"\b{genre}\b", prompt_lower)
    ]
    if detected_genres:
        return "genre", detected_genres  # Return a list of genres
    
    # Detect multiple actors (e.g., "starring Brad Pitt and Leonardo DiCaprio")
    match = re.search(r"(starring|featuring|with)\s+([a-zA-Z\s,]+)", prompt_lower)
    if match:
        actors = [actor.strip() for actor in re.split(r"and|,", match.group(2)) if actor.strip()]
        return "actor", actors  # Return a list of actors
    
    if "similar to" in prompt_lower or "like" in prompt_lower:
        match = re.search(r"(similar to|like)\s+([a-zA-Z\s]+)", prompt_lower)
        if match:
            return "similar", match.group(2).strip()
    
    if "directed by" in prompt_lower or "by director" in prompt_lower:
        match = re.search(r"(directed by|by director)\s+([a-zA-Z\s]+)", prompt_lower)
        if match:
            return "director", match.group(2).strip()
    
    return None, None

# Generate chatbot response
def chatbot_response(user_prompt, history):
    # Combine history into a single conversation string for context
    conversation_context = "\n".join(
        [f"{msg['role']}: {msg['content']}" for msg in history]
    )
    full_prompt = f"{conversation_context}\nUser: {user_prompt}\nAssistant:"
    
    # Detect intent and entity
    intent, entity = detect_intent_and_entity(user_prompt)
    if intent == "genre":
        return get_movie_recommendations(genre=entity)
    elif intent == "actor":
        return get_movie_recommendations(actor=entity)
    elif intent == "similar":
        return get_movie_recommendations(similar_to=entity)
    elif intent == "director":
        return get_movie_recommendations(director=entity)
    else:
        # Generate response using AI model
        try:
            model = genai.GenerativeModel("gemini-2.5-flash-latest")
            response = model.generate_content(full_prompt).text.strip()
            return response
        except Exception as e:
            return f"I couldn't fully understand your request. Error: {e}"


# Streamlit App Configuration
st.set_page_config(page_title="Entertainment Chatbot", page_icon="🎥", layout="wide")

# Manage sessions
SESSION_FILE = "sessions.json"

def load_sessions():
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    return {"Default Session": {"topic": "General Chat", "history": []}}

def save_sessions():
    with open(SESSION_FILE, "w") as f:
        json.dump(st.session_state.sessions, f)

# Initialize session state
if "sessions" not in st.session_state:
    st.session_state.sessions = load_sessions()
    st.session_state.current_session = list(st.session_state.sessions.keys())[0]

# Sidebar: Manage Sessions
st.sidebar.title("Session Manager")

# Create a new session
if st.sidebar.button("New Session ➕"):
    new_session = f"Session {len(st.session_state.sessions) + 1}"
    st.session_state.sessions[new_session] = {"topic": "New Session", "history": []}
    st.session_state.current_session = new_session  # Switch to the newly created session
    save_sessions()

# Delete the selected session
if st.sidebar.button("Delete Session ❌"):
    if st.session_state.current_session != "Default Session":
        del st.session_state.sessions[st.session_state.current_session]
        if not st.session_state.sessions:
            # Recreate Default Session if all are deleted
            st.session_state.sessions = {"Default Session": {"topic": "General Chat", "history": []}}
            st.session_state.current_session = "Default Session"
        else:
            # Switch to the first available session
            st.session_state.current_session = list(st.session_state.sessions.keys())[-1]
        save_sessions()

# Dropdown for session selection
session_names = list(st.session_state.sessions.keys())
current_session = st.sidebar.selectbox(
    "Select a session", 
    session_names, 
    index=session_names.index(st.session_state.current_session)  # Set default to current session
)

if current_session != st.session_state.current_session:
    st.session_state.current_session = current_session

# Retrieve current session data
current_data = st.session_state.sessions[st.session_state.current_session]

# Main Chat Interface
st.title(f"Entertainment Chatbot - {current_data['topic']} 🎭")

# Display previous conversation history
for message in current_data["history"]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input field for user prompt
user_prompt = st.chat_input("Ask the chatbot something...")
if user_prompt:
    # Rename the session based on the first user input if not renamed yet
    if not current_data.get("is_renamed", False):
        new_name = user_prompt.strip()[:50]  # Limit session name to 50 characters
        if new_name in st.session_state.sessions:
            new_name = f"{new_name} ({len(st.session_state.sessions)})"
        st.session_state.sessions[new_name] = st.session_state.sessions.pop(st.session_state.current_session)
        st.session_state.current_session = new_name
        current_data = st.session_state.sessions[st.session_state.current_session]
        current_data["is_renamed"] = True

    # Append the user's message to the session history
    st.chat_message("user").markdown(user_prompt)
    current_data["history"].append({"role": "user", "content": user_prompt})

    # Get chatbot response using the full conversation history
    chatbot_reply = chatbot_response(user_prompt, current_data["history"])
    st.chat_message("assistant").markdown(chatbot_reply)
    current_data["history"].append({"role": "assistant", "content": chatbot_reply})

    # Save the updated session data
    save_sessions()

