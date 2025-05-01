import os
import sys
import asyncio
import datetime
import bcrypt
import argparse
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash

from sentence_transformers import SentenceTransformer
from transformers import pipeline

from immigration_assistant.config import database
from immigration_assistant.orchestration.conductor import RMAIA
from immigration_assistant.rag.agent import RAGAgent
from immigration_assistant.rag.config import RAGConfig
from immigration_assistant.reasoning.agent import ReasoningAgent
from immigration_assistant.relevance.agent import RelevanceAgent
from immigration_assistant.summarization.agent import SummaryAgent
from immigration_assistant.timeline.agent import TimelineAgent
from immigration_assistant.translator.agent import TranslatorAgent
from immigration_assistant.user_registration.agent import UserRegistration

# --- Parse arguments ---
parser = argparse.ArgumentParser(description="Run the Immigration Assistant web application")
parser.add_argument('--config', type=str, default='config.yaml', help='Path to config file')
parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the Flask server')
parser.add_argument('--port', type=int, default=5011, help='Port to run the Flask server')
parser.add_argument('--debug', action='store_true', help='Enable Flask debug mode')
parser.add_argument('--init-database', action='store_true', help='Initialize schemas for database')
parser.add_argument('--clear-database', action='store_true', help='Truncate and repopulate the database')
parser.add_argument('--populate-database', action='store_true', help='Populate all tables in the RAG database')
args = parser.parse_args()

# --- Load YAML config ---
config = database.load_config(args.config)
base_dir = config['base_dir']

# --- Flask setup ---
app = Flask(__name__, template_folder=os.path.join(base_dir, config['paths']['templates']))
app.secret_key = config['secret_key']
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=config['session_lifetime_days'])

# --- Embedding model ---
embedding_model = SentenceTransformer(RAGAgent.model_name)

# --- Database config ---
db_config = database.Config(
    dsn=config['database']['dsn'],
    database=config['database']['database'],
    pool_size=tuple(config['database']['pool_size']),
    schema_dir=""  # default fallback
)

# --- Agents ---
user_registar = UserRegistration(
    db_config=db_config.copy(schema_dir=os.path.join(base_dir, config['paths']['user_reg_sql']))
)

translator_agent = TranslatorAgent(verbose=True)

summary_agent = SummaryAgent(
    db_config=db_config.copy(schema_dir=os.path.join(base_dir, config['paths']['user_reg_sql'])),
    model=pipeline("summarization", model="facebook/bart-large-cnn"),
    verbose=True
)

relevance_agent = RelevanceAgent(
    model=embedding_model,
    baseline_path=os.path.join(base_dir, config['paths']['faqs']),
    relevance_threshold=config['relevance']['threshold'],
    verbose=True
)

reasoning_agent = ReasoningAgent(
    endpoint_url=config['reasoning']['endpoint'],
    api_token=config['reasoning']['api_token'],
    verbose=True
)

rag_agent = RAGAgent(
    db_config=db_config.copy(schema_dir=os.path.join(base_dir, config['paths']['rag_sql'])),
    rag_config=RAGConfig(
        forms_path=os.path.join(base_dir, config['paths']['forms']),
        legislation_path=os.path.join(base_dir, config['paths']['legislation']),
    ),
    embedding_model=embedding_model,
    verbose=True
)

timeline_agent = TimelineAgent(verbose=True)

# --- System cache ---
system_cache = {}

def get_system_for_user(user_email):
    if user_email not in system_cache:
        system_cache[user_email] = RMAIA(
            user=user_email,
            translator_agent=translator_agent,
            summary_agent=summary_agent,
            relevance_agent=relevance_agent,
            reasoning_agent=reasoning_agent,
            rag_agent=rag_agent,
            timeline_agent=timeline_agent,
            verbose=True
        )
    return system_cache[user_email]

# --- Auth helpers ---
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def check_password(hashed_password, password):
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        error, user = asyncio.run(user_registar.login())
        if error == "success":
            session['user'] = user
            return redirect(url_for('chat'))
    return render_template('login.html', error=error)

@app.route('/register', methods=['POST'])
def register():
    return asyncio.run(user_registar.register())

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.clear()
    return redirect(url_for('login'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        data = request.json
        question = data.get('question')
        if not question:
            return jsonify({'error': 'Question is required'}), 400

        user = session.get('user')
        user_email = user['email']
        system = get_system_for_user(user_email)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(system.ainvoke(question))
            loop.close()

            session.setdefault('messages', []).extend([
                {'role': 'user', 'content': question},
                {'role': 'assistant', 'content': result.get('final_response', result.get('initial_response', ''))}
            ])
            session.modified = True
            return jsonify(result), 200

        except Exception as e:
            print(f"Error processing question: {str(e)}", flush=True)
            return jsonify({
                'error': 'Error processing question',
                'message': str(e),
                'initial_response': 'I encountered an error while processing your question.'
            }), 500

    return render_template('chat.html', user=session.get('user'), messages=session.get('messages', []))

# --- Async tasks ---
async def main():
    if args.init_database:
        print(f"Initializing database...")
        await user_registar.init_database()
        await rag_agent.init_database()
    if args.populate_database:
        if args.clear_database:
            print(f"Clearing database...")
        print(f"Populating database...")
        await rag_agent.populate_database(clear=args.clear_database)

# --- Entrypoint ---
if __name__ == '__main__':
    if args.init_database or args.populate_database:
        asyncio.run(main())

    print(f"Starting Immigration Assistant web application on port {args.port}...")
    app.run(host=args.host, port=args.port, debug=args.debug)
