from flask import Flask, request, jsonify, redirect, url_for, send_from_directory, session
import os
from groq import Groq
from datetime import datetime, timedelta
from dotenv import load_dotenv
import logging
from authlib.integrations.flask_client import OAuth
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = '9fd7f05d817e0bfe6a1662f004f0cbd0' # Required for sessions
app.config['SESSION_COOKIE_SECURE'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Configure app for production
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['JSON_SORT_KEYS'] = False

# OAuth Configuration
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id='651880928848-iuvuu88h93ulv3o7rlvtsr6u0slfsrj5.apps.googleusercontent.com',
    client_secret='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',
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs'  # Explicitly add JWKS URI
)

# Ensure static folders exist
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/images', exist_ok=True)

# In-memory store for user data (for MVP/demo purposes only)
users = {}

# Use environment variable for API key
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY environment variable is not set")
    raise ValueError("GROQ_API_KEY environment variable is not set")

# Specify the model name
MODEL_NAME = "llama-3.3-70b-versatile"

# Initialize the Groq client
client = Groq(api_key=GROQ_API_KEY)

# Add static file handling
@app.route('/static/<path:path>')
def serve_static(path):
    try:
        return send_from_directory('static', path)
    except Exception as e:
        logger.error(f"Error serving static file {path}: {str(e)}")
        return str(e), 500

@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 error: {error}")
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {error}")
    return jsonify({"error": "Internal server error"}), 500

def generate_response(prompt):
    """Generate a response using the Groq API."""
    try:
        print(f"Calling Groq API with prompt: {prompt}")
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.7,
            top_p=0.9
        )
        print(f"Received response: {response}")
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm sorry, I'm having trouble generating a response right now."

def get_conversation_context(user_id):
    """Build conversation context from previous exchanges."""
    session = users[user_id].get("session", [])
    context = ""
    for exchange in session:
        context += f"User: {exchange['user']}\nM: {exchange['bot']}\n"
    return context

def get_empathy_response(user_id, user_message):
    """Generate a context-aware response including user profile data."""
    # Retrieve conversation history
    conversation_context = get_conversation_context(user_id)
    
    # Retrieve user profile details from login data
    user_profile = users[user_id]
    display_name = user_profile.get("display_name", "user")
    pronouns = user_profile.get("pronouns", "not specified")
    identity_goals = user_profile.get("identity_goals", "not specified")
    focus_areas = user_profile.get("focus_areas", "not specified")
    
    # Build user profile context
    user_info = (
        f"User Profile:\n"
        f"Name: {display_name}\n"
        f"Pronouns: {pronouns}\n"
        f"Identity Goals: {identity_goals}\n"
        f"Focus Areas: {focus_areas}\n\n"
    )
    
    # Build the complete prompt for the LLM
    prompt = (
        "You are M, a compassionate and empathetic mentor chatbot designed to support users on their journey "
        "of identity affirmation and personal growth. Use the provided user profile information to personalize your responses. "
        "When a user expresses their feelings, respond with warmth, practical advice, and thoughtful empathy. "
        "Keep the tone friendly, respectful, and encouraging.\n\n"
        f"{user_info}"
        f"{conversation_context}"
        f"User: {user_message}\n"
        "M:"
    )
    return generate_response(prompt)

# ------------------ Authentication routes ------------------

@app.route('/login')
def login():
    """Redirect to Google OAuth login."""
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    """Handle the OAuth callback."""
    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()
    
    # Store user info in session
    session['user_id'] = user_info['id']
    session['user_email'] = user_info['email']
    session['user_name'] = user_info.get('name', '')
    session['profile_picture'] = user_info.get('picture', '')
    
    # Create or update user in our system
    if user_info['id'] not in users:
        users[user_info['id']] = {
            "email": user_info['email'],
            "display_name": user_info.get('name', user_info['email'].split('@')[0]),
            "profile_picture": user_info.get('picture', ''),
            "pronouns": "",
            "identity_goals": "",
            "focus_areas": "",
            "session": []
        }
    
    # Redirect to profile completion or chat based on whether user has completed profile
    if not users[user_info['id']].get("pronouns") and not users[user_info['id']].get("identity_goals"):
        return redirect(url_for('profile_form'))
    else:
        return redirect(url_for('chat_form'))

@app.route('/logout')
def logout():
    """Log the user out and clear session."""
    session.pop('user_id', None)
    session.pop('user_email', None)
    session.pop('user_name', None)
    session.pop('profile_picture', None)
    return redirect(url_for('index'))

# ------------------ New profile route ------------------

@app.route("/profile", methods=["GET"])
def profile_form():
    """Display the profile completion form."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = users.get(user_id, {})
    
    content = f'''
    <div class="container">
        <img src="/static/images/logo.png" alt="M Logo" class="logo">
        <h1>Complete Your Profile</h1>
        <p class="subtitle">Share a bit about yourself so I can better support you</p>
        <div class="user-profile-header">
            <img src="{session.get('profile_picture', '/static/images/default-avatar.png')}" alt="Profile Picture" class="profile-picture">
            <div class="user-info">
                <h3>{session.get('user_name', 'User')}</h3>
                <p>{session.get('user_email', '')}</p>
            </div>
        </div>
        <form action="/api/update_profile" method="post">
            <input type="hidden" name="user_id" value="{user_id}">
            <div class="form-group">
                <label for="pronouns">Your Pronouns</label>
                <input type="text" id="pronouns" name="pronouns" value="{user.get('pronouns', '')}" placeholder="e.g., they/them, she/her, he/him">
            </div>
            <div class="form-group">
                <label for="identity_goals">What brings you here today?</label>
                <textarea id="identity_goals" name="identity_goals" placeholder="Share your goals or what you'd like to work on...">{user.get('identity_goals', '')}</textarea>
            </div>
            <div class="form-group">
                <label for="focus_areas">Areas you'd like to focus on</label>
                <input type="text" id="focus_areas" name="focus_areas" value="{user.get('focus_areas', '')}" placeholder="e.g., Anxiety, Self-Discovery, Personal Growth">
            </div>
            <button type="submit" class="btn" style="width: 100%;">
                <i class="fas fa-heart"></i> Save Profile & Continue
            </button>
        </form>
    </div>
    '''
    return get_base_template().format(content=content)

# ------------------ API Endpoints ------------------

@app.route("/api/update_profile", methods=["POST"])
def api_update_profile():
    """Handle profile updates."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    data = request.form
    
    # Update user profile
    users[user_id]["pronouns"] = data.get("pronouns", "")
    users[user_id]["identity_goals"] = data.get("identity_goals", "")
    users[user_id]["focus_areas"] = data.get("focus_areas", "")
    
    return redirect(url_for("chat_form"))

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Handle chat messages and generate context-aware responses."""
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form
    message = data.get("message")
    
    if not message:
        return jsonify({"error": "Message is required"}), 400
    
    # Generate a response with conversation context and user profile data
    response_text = get_empathy_response(user_id, message)
    current_time = datetime.now().strftime("%I:%M %p")
    
    # Store the exchange in the user's session history
    users[user_id]["session"].append({
        "user": message,
        "bot": response_text,
        "time": current_time
    })
    
    return jsonify({"response": response_text}), 200

@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Handle user feedback."""
    if 'user_id' not in session:
        return jsonify({"error": "Not authenticated"}), 401
    
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form
    feedback_message = data.get("feedback")
    
    if not feedback_message:
        return jsonify({"error": "Feedback is required"}), 400
    
    print(f"Feedback from {user_id}: {feedback_message}")
    return jsonify({"message": "Thank you for your feedback!"}), 200

# ------------------ Simple Web Interface ------------------

def get_base_template():
    """Return the base HTML template with common head elements."""
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>M - Your Therapeutic AI Companion</title>
        <link rel="stylesheet" href="/static/css/styles.css">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <link rel="icon" type="image/png" href="/static/images/logo.png">
    </head>
    <body>
        {content}
    </body>
    </html>
    '''

@app.route("/", methods=["GET"])
def index():
    """Display the home page."""
    content = '''
    <div class="container">
        <img src="/static/images/logo.png" alt="M Logo" class="logo">
        <h1>Welcome to M</h1>
        <p class="subtitle">
            Your safe space for personal growth and emotional well-being.<br>
            Let's navigate life's journey together.
        </p>
        <div style="display: flex; justify-content: center; gap: 1.5rem;">
            <a href="/login" class="btn" style="background-color: var(--primary-color);">
                <i class="fas fa-sign-in-alt"></i> Sign in with Google
            </a>
            <a href="/chat" class="btn" style="background-color: var(--success-color);">
                <i class="fas fa-comments"></i> Continue Chat
            </a>
        </div>
    </div>
    '''
    return get_base_template().format(content=content)

@app.route("/chat", methods=["GET"])
def chat_form():
    """Display the chat form with conversation history."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = users.get(user_id, {})
    
    if not user:
        return redirect(url_for('login'))
    
    # Get conversation history
    chat_history = ""
    for message in user.get("session", []):
        chat_history += f'''
        <div class="message-container">
            <div class="message user">
                <div class="message-header">
                    <img src="{session.get('profile_picture', '/static/images/default-avatar.png')}" class="avatar" alt="You"> You
                </div>
                {message["user"]}
                <div class="message-time">{message.get("time", "")}</div>
            </div>
        </div>
        <div class="message-container">
            <div class="message bot">
                <div class="message-header">
                    <i class="fas fa-robot"></i> M
                </div>
                {message["bot"]}
                <div class="message-time">{message.get("time", "")}</div>
            </div>
        </div>
        '''

    content = f'''
    <div class="chat-container">
        <div class="chat-header">
            <div class="header-content">
                <img src="/static/images/logo.png" alt="M Logo" class="header-logo">
                <h1>Chat with M</h1>
                <div class="header-actions">
                    <div class="user-dropdown">
                        <img src="{session.get('profile_picture', '/static/images/default-avatar.png')}" class="header-avatar" alt="{session.get('user_name', 'User')}">
                        <div class="dropdown-content">
                            <a href="/profile"><i class="fas fa-user-edit"></i> Edit Profile</a>
                            <a href="/logout"><i class="fas fa-sign-out-alt"></i> Logout</a>
                        </div>
                    </div>
                    <a href="/" class="header-link" title="Home">
                        <i class="fas fa-home"></i>
                    </a>
                </div>
            </div>
        </div>
        
        <div class="chat-messages" id="chatMessages">
            {chat_history}
            <div class="message-container">
                <div class="typing-indicator" id="typingIndicator">
                    <i class="fas fa-circle-notch fa-spin"></i> M is thinking...
                </div>
            </div>
        </div>
        
        <div class="chat-input-container">
            <div class="chat-input-wrapper">
                <form action="/api/chat" method="post" id="chatForm">
                    <textarea 
                        class="chat-input" 
                        id="message" 
                        name="message" 
                        placeholder="Share your thoughts..." 
                        rows="1" 
                        required
                    ></textarea>
                    <button type="submit" class="send-button">
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </form>
                
                <div class="suggestions-container">
                    <div class="suggestion-tab" onclick="setMessage('How can I manage my anxiety better?')">
                        <i class="fas fa-brain"></i> Managing Anxiety
                    </div>
                    <div class="suggestion-tab" onclick="setMessage('I need help with self-acceptance.')">
                        <i class="fas fa-heart"></i> Self-Acceptance
                    </div>
                    <div class="suggestion-tab" onclick="setMessage('Can you help me develop better coping strategies?')">
                        <i class="fas fa-shield-alt"></i> Coping Strategies
                    </div>
                    <div class="suggestion-tab" onclick="setMessage('I want to work on my self-confidence.')">
                        <i class="fas fa-star"></i> Building Confidence
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Auto-resize textarea
        const textarea = document.getElementById('message');
        textarea.addEventListener('input', function() {{
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        }});

        // Set message from suggestion tabs
        function setMessage(text) {{
            const textarea = document.getElementById('message');
            textarea.value = text;
            textarea.focus();
            textarea.style.height = 'auto';
            textarea.style.height = (textarea.scrollHeight) + 'px';
        }}

        // Scroll to bottom of chat
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Handle form submission
        document.getElementById('chatForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            const form = e.target;
            const typingIndicator = document.getElementById('typingIndicator');
            const textarea = form.querySelector('textarea');
            
            if (!textarea.value.trim()) return;
            
            // Show typing indicator
            typingIndicator.classList.add('active');
            
            try {{
                const response = await fetch('/api/chat', {{
                    method: 'POST',
                    body: new FormData(form)
                }});
                
                const data = await response.json();
                const currentTime = new Date().toLocaleTimeString();
                
                chatMessages.innerHTML += `
                    <div class="message-container">
                        <div class="message user">
                            <div class="message-header">
                                <img src="{session.get('profile_picture', '/static/images/default-avatar.png')}" class="avatar" alt="You"> You
                            </div>
                            ${{textarea.value}}
                            <div class="message-time">${{currentTime}}</div>
                        </div>
                    </div>
                    <div class="message-container">
                        <div class="message bot">
                            <div class="message-header">
                                <i class="fas fa-robot"></i> M
                            </div>
                            ${{data.response}}
                            <div class="message-time">${{currentTime}}</div>
                        </div>
                    </div>
                `;
                
                textarea.value = '';
                textarea.style.height = 'auto';
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }} catch (error) {{
                console.error('Error:', error);
            }} finally {{
                // Hide typing indicator
                typingIndicator.classList.remove('active');
            }}
        }});
    </script>
    '''
    return get_base_template().format(content=content)

if __name__ == "__main__":
    # Get port from environment variable or use 5000 as default
    port = int(os.getenv('PORT', 5000))
    # In production, you might want to use 0.0.0.0 to listen on all interfaces
    host = '0.0.0.0' if os.getenv('FLASK_ENV') == 'production' else 'localhost'
    app.run(host=host, port=port)
