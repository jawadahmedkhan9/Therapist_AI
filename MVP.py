from flask import Flask, request, jsonify, redirect, url_for, send_from_directory
import os
from groq import Groq
from datetime import datetime
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure app for production
app.config['PROPAGATE_EXCEPTIONS'] = True
app.config['JSON_SORT_KEYS'] = False

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

def get_conversation_context(username):
    """Build conversation context from previous exchanges."""
    session = users[username].get("session", [])
    context = ""
    for exchange in session:
        context += f"User: {exchange['user']}\nM: {exchange['bot']}\n"
    return context

def get_empathy_response(username, user_message):
    """Generate a context-aware response including user profile data."""
    # Retrieve conversation history
    conversation_context = get_conversation_context(username)
    
    # Retrieve user profile details from login data
    user_profile = users[username]
    pronouns = user_profile.get("pronouns", "not specified")
    identity_goals = user_profile.get("identity_goals", "not specified")
    focus_areas = user_profile.get("focus_areas", "not specified")
    
    # Build user profile context
    user_info = (
        f"User Profile:\n"
        f"Username: {username}\n"
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

# ------------------ API Endpoints ------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    """Handle user login and profile creation."""
    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    pronouns = data.get("pronouns")
    identity_goals = data.get("identity_goals")
    focus_areas = data.get("focus_areas")
    
    if not username:
        if request.is_json:
            return jsonify({"error": "username is required"}), 400
        else:
            return "Username is required", 400
    
    # Save or update the user profile
    users[username] = {
        "pronouns": pronouns,
        "identity_goals": identity_goals,
        "focus_areas": focus_areas,
        "session": []
    }
    
    if request.is_json:
        return jsonify({"message": f"Welcome, {username}! Your preferences have been saved."}), 200
    else:
        return redirect(url_for("chat_form", username=username))

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """Handle chat messages and generate context-aware responses."""
    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    message = data.get("message")
    
    if not username or not message:
        return jsonify({"error": "username and message are required"}), 400
    
    if username not in users:
        return jsonify({"error": "User not found. Please log in first."}), 404
    
    # Generate a response with conversation context and user profile data
    response_text = get_empathy_response(username, message)
    current_time = datetime.now().strftime("%I:%M %p")
    
    # Store the exchange in the user's session history
    users[username]["session"].append({
        "user": message,
        "bot": response_text,
        "time": current_time
    })
    
    return jsonify({"response": response_text}), 200

@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Handle user feedback."""
    data = request.get_json() if request.is_json else request.form
    username = data.get("username")
    feedback_message = data.get("feedback")
    
    if not username or not feedback_message:
        return jsonify({"error": "username and feedback are required"}), 400
    
    if username not in users:
        return jsonify({"error": "User not found."}), 404
    
    print(f"Feedback from {username}: {feedback_message}")
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
                <i class="fas fa-user-plus"></i> Get Started
            </a>
            <a href="/chat" class="btn" style="background-color: var(--success-color);">
                <i class="fas fa-comments"></i> Continue Chat
            </a>
        </div>
    </div>
    '''
    return get_base_template().format(content=content)

@app.route("/login", methods=["GET"])
def login_form():
    """Display the login form."""
    content = '''
    <div class="container">
        <img src="/static/images/logo.png" alt="M Logo" class="logo">
        <h1>Begin Your Journey</h1>
        <p class="subtitle">Share a bit about yourself so I can better support you</p>
        <form action="/api/login" method="post">
            <div class="form-group">
                <label for="username">Choose a Username</label>
                <input type="text" id="username" name="username" placeholder="A name you'd like to be called" required>
            </div>
            <div class="form-group">
                <label for="pronouns">Your Pronouns</label>
                <input type="text" id="pronouns" name="pronouns" placeholder="e.g., they/them, she/her, he/him">
            </div>
            <div class="form-group">
                <label for="identity_goals">What brings you here today?</label>
                <textarea id="identity_goals" name="identity_goals" placeholder="Share your goals or what you'd like to work on..."></textarea>
            </div>
            <div class="form-group">
                <label for="focus_areas">Areas you'd like to focus on</label>
                <input type="text" id="focus_areas" name="focus_areas" placeholder="e.g., Anxiety, Self-Discovery, Personal Growth">
            </div>
            <button type="submit" class="btn" style="width: 100%;">
                <i class="fas fa-heart"></i> Begin Your Journey
            </button>
        </form>
        <div class="nav-links">
            Already have a session? <a href="/chat">Continue Chat</a>
        </div>
    </div>
    '''
    return get_base_template().format(content=content)

@app.route("/chat", methods=["GET"])
def chat_form():
    """Display the chat form with conversation history."""
    username = request.args.get("username", "")
    
    # Get conversation history if user exists
    chat_history = ""
    if username and username in users:
        for message in users[username]["session"]:
            chat_history += f'''
            <div class="message-container">
                <div class="message user">
                    <div class="message-header">
                        <i class="fas fa-user-circle"></i> You
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
                    <a href="/" class="header-link" title="Home">
                        <i class="fas fa-home"></i>
                    </a>
                    <a href="/login" class="header-link" title="Switch User">
                        <i class="fas fa-user"></i>
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
                    <input type="hidden" name="username" value="{username}">
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
                                <i class="fas fa-user-circle"></i> You
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
