import os
import sys
import asyncio
import jwt
import datetime
import bcrypt
from functools import wraps
from pathlib import Path
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash

# Import necessary machine learning libraries
from sentence_transformers import SentenceTransformer
from transformers import pipeline

# Import your existing system components
from immigration_assistant.config import database
from immigration_assistant.orchestration.conductor import RMAIA
from immigration_assistant.rag.agent import RAGAgent
from immigration_assistant.rag.config import RAGConfig
from immigration_assistant.reasoning.agent import ReasoningAgent
from immigration_assistant.relevance.agent import RelevanceAgent
from immigration_assistant.summarization.agent import SummaryAgent
from immigration_assistant.timeline.agent import TimelineAgent

# Get the current working directory
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
print(f"Base directory: {base_dir}")

# Initialize Flask app
app = Flask(__name__, template_folder=os.path.join(base_dir, 'immigration_assistant/templates'))
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-in-production')

# Session Configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)

# User database (replace with a real database in production)
USER_DB = {}

# Initialize the immigration assistant system
print("Loading models and initializing system...", flush=True)

# Use proper paths for resources
embedding_model = SentenceTransformer(RAGAgent.model_name)

db_config = database.Config(
    dsn="postgresql://postgres:12345@localhost:5432",
    database="maia",
    pool_size=(10, 10)
)

# Adjust paths to be relative to the base directory
user_reg_sql_path = os.path.join(base_dir, "immigration_assistant/user-registration/sql")
rag_sql_path = os.path.join(base_dir, "immigration_assistant/rag/sql")
faqs_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json")
forms_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/forms")
legislation_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/legislation")

summary_agent = SummaryAgent(
    db_config=db_config.copy(user_reg_sql_path),
    model=pipeline("summarization", model="facebook/bart-large-cnn"),
    verbose=True
)

relevance_agent = RelevanceAgent(
    model=embedding_model,
    baseline_path=faqs_path,
    relevance_threshold=0.65,
    verbose=True
)

reasoning_agent = ReasoningAgent(
    endpoint_url="https://apc68c0a4ml2min4.us-east-1.aws.endpoints.huggingface.cloud",
    api_token="",
    verbose=True
)

rag_agent = RAGAgent(
    db_config=db_config.copy(schema_dir=rag_sql_path),
    rag_config=RAGConfig(
        forms_path=forms_path,
        legislation_path=legislation_path,
    ),
    embedding_model=embedding_model,
    verbose=True
)

timeline_agent = TimelineAgent(
    verbose=True
)

# Cache for system instances per user
system_cache = {}

def get_system_for_user(user_email):
    """Get or create a system instance for a specific user"""
    if user_email not in system_cache:
        system_cache[user_email] = RMAIA(
            user=user_email,
            summary_agent=summary_agent,
            relevance_agent=relevance_agent,
            reasoning_agent=reasoning_agent,
            rag_agent=rag_agent,
            timeline_agent=timeline_agent,
            verbose=True
        )
    return system_cache[user_email]

# Password hashing
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def check_password(hashed_password, password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not email or not password:
            error = "Email and password are required"
        else:
            user = USER_DB.get(email)
            
            if not user or not check_password(user['password'], password):
                error = "Invalid email or password"
            else:
                # Store user in session
                session['user'] = {
                    'email': email,
                    'first_name': user.get('first_name', ''),
                    'last_name': user.get('last_name', '')
                }
                return redirect(url_for('chat'))
    
    return render_template('login.html', error=error)

@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    first_name = request.form.get('first_name', '')
    last_name = request.form.get('last_name', '')
    
    if not email or not password:
        flash('Email and password are required')
        return redirect(url_for('login'))
    
    if password != confirm_password:
        flash('Passwords do not match')
        return redirect(url_for('login'))
    
    if email in USER_DB:
        flash('User already exists')
        return redirect(url_for('login'))
    
    # Create new user
    user = {
        'email': email,
        'password': hash_password(password),
        'first_name': first_name,
        'last_name': last_name
    }
    
    USER_DB[email] = user
    
    # Store user in session
    session['user'] = {
        'email': email,
        'first_name': first_name,
        'last_name': last_name
    }
    
    return redirect(url_for('chat'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        # Handle API request for new message
        data = request.json
        question = data.get('question')
        
        if not question:
            return jsonify({'error': 'Question is required'}), 400
        
        # Get user from session
        user = session.get('user')
        user_email = user['email']
        
        # Get system for this user
        system = get_system_for_user(user_email)
        
        # Process the question
        try:
            # getting inout from the user
            #check the user input question 
            #gOOGLE api

            # Run the async function in the event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(system.ainvoke(question))
            loop.close()
            
            # Store the conversation history in session
            if 'messages' not in session:
                session['messages'] = []
            
            session['messages'].append({
                'role': 'user',
                'content': question
            })
            
            session['messages'].append({
                'role': 'assistant',
                'content': result.get('initial_response', '')
            })
            
            session.modified = True
            
            return jsonify(result), 200
            
        except Exception as e:
            print(f"Error processing question: {str(e)}", flush=True)
            return jsonify({
                'error': 'Error processing question',
                'message': str(e),
                'initial_response': 'I encountered an error while processing your question. Please try again later.'
            }), 500
    
    # Render chat page
    return render_template(
        'chat.html', 
        user=session.get('user'), 
        messages=session.get('messages', [])
    )

if __name__ == '__main__':
    print("Starting Immigration Assistant web application...")
    app.run(host='0.0.0.0', port=5011, debug=True)
