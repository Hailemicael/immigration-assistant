# # from flask import Flask, render_template, request, jsonify
# # import os
# # from rag_system_mock import RAGSystemMock, QueryRequest, RAGResponse
import json
# # # Initialize Flask app
# # app = Flask(__name__)

# # # Create static directory if it doesn't exist
# # os.makedirs("static", exist_ok=True)
# # os.makedirs("templates", exist_ok=True)

# # # Create RAG system instance
# # rag_system = RAGSystemMock()

# # # Create a simple HTML template
# # html_content = """
# # <!DOCTYPE html>
# # <html lang="en">
# # <head>
# #     <meta charset="UTF-8">
# #     <meta name="viewport" content="width=device-width, initial-scale=1.0">
# #     <title>Immigration Assistant</title>
# #     <style>
# #         body {
# #             font-family: Arial, sans-serif;
# #             line-height: 1.6;
# #             margin: 0;
# #             padding: 20px;
# #             max-width: 900px;
# #             margin: 0 auto;
# #         }
# #         h1 {
# #             color: #2c3e50;
# #             text-align: center;
# #             margin-bottom: 30px;
# #         }
# #         .query-form {
# #             background-color: #f8f9fa;
# #             padding: 20px;
# #             border-radius: 8px;
# #             margin-bottom: 20px;
# #             box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
# #         }
# #         .form-group {
# #             margin-bottom: 15px;
# #         }
# #         label {
# #             display: block;
# #             margin-bottom: 5px;
# #             font-weight: bold;
# #         }
# #         input[type="text"] {
# #             width: 100%;
# #             padding: 10px;
# #             border: 1px solid #ddd;
# #             border-radius: 4px;
# #             font-size: 16px;
# #         }
# #         button {
# #             background-color: #3498db;
# #             color: white;
# #             border: none;
# #             padding: 10px 15px;
# #             border-radius: 4px;
# #             cursor: pointer;
# #             font-size: 16px;
# #         }
# #         button:hover {
# #             background-color: #2980b9;
# #         }
# #         .response {
# #             background-color: #f8f9fa;
# #             padding: 20px;
# #             border-radius: 8px;
# #             margin-top: 20px;
# #             display: none;
# #             box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
# #         }
# #         .answer {
# #             margin-bottom: 20px;
# #             padding-bottom: 20px;
# #             border-bottom: 1px solid #eee;
# #         }
# #         .sources, .forms, .next-steps {
# #             margin-top: 20px;
# #         }
# #         .loading {
# #             text-align: center;
# #             display: none;
# #             margin: 20px 0;
# #         }
# #         .error {
# #             color: #e74c3c;
# #             background-color: #fdeded;
# #             padding: 10px;
# #             border-radius: 4px;
# #             margin-top: 10px;
# #             display: none;
# #         }
# #     </style>
# # </head>
# # <body>
# #     <h1>Immigration Assistant</h1>
    
# #     <div class="query-form">
# #         <div class="form-group">
# #             <label for="query">Ask a question about US immigration:</label>
# #             <input type="text" id="query" placeholder="e.g., How do I apply for a green card?">
# #         </div>
# #         <button onclick="submitQuery()">Ask Question</button>
# #         <div class="error" id="error"></div>
# #     </div>
    
# #     <div class="loading" id="loading">
# #         <p>Processing your question...</p>
# #     </div>
    
# #     <div class="response" id="response">
# #         <div class="answer">
# #             <h2>Answer</h2>
# #             <p id="answer-text"></p>
# #         </div>
        
# #         <div class="sources">
# #             <h3>Sources</h3>
# #             <ul id="sources-list"></ul>
# #         </div>
        
# #         <div class="forms">
# #             <h3>Related Forms</h3>
# #             <ul id="forms-list"></ul>
# #         </div>
        
# #         <div class="next-steps">
# #             <h3>Suggested Next Steps</h3>
# #             <ul id="steps-list"></ul>
# #         </div>
# #     </div>
    
# #     <script>
# #         async function submitQuery() {
# #             const query = document.getElementById('query').value.trim();
            
# #             if (!query) {
# #                 showError("Please enter a question");
# #                 return;
# #             }
            
# #             // Show loading, hide previous response and errors
# #             document.getElementById('loading').style.display = 'block';
# #             document.getElementById('response').style.display = 'none';
# #             document.getElementById('error').style.display = 'none';
            
# #             try {
# #                 const response = await fetch('/api/query', {
# #                     method: 'POST',
# #                     headers: {
# #                         'Content-Type': 'application/json'
# #                     },
# #                     body: JSON.stringify({
# #                         query: query,
# #                         max_results: 3
# #                     })
# #                 });
                
# #                 if (!response.ok) {
# #                     throw new Error('Failed to get a response from the server');
# #                 }
                
# #                 const data = await response.json();
# #                 displayResponse(data);
# #             } catch (error) {
# #                 showError(error.message);
# #             } finally {
# #                 document.getElementById('loading').style.display = 'none';
# #             }
# #         }
        
# #         function displayResponse(data) {
# #             // Set answer text
# #             document.getElementById('answer-text').textContent = data.answer;
            
# #             // Clear previous lists
# #             document.getElementById('sources-list').innerHTML = '';
# #             document.getElementById('forms-list').innerHTML = '';
# #             document.getElementById('steps-list').innerHTML = '';
            
# #             // Add sources
# #             const sourcesList = document.getElementById('sources-list');
# #             if (data.sources && data.sources.length > 0) {
# #                 data.sources.forEach(source => {
# #                     const li = document.createElement('li');
# #                     const a = document.createElement('a');
# #                     a.href = source.url;
# #                     a.textContent = source.title;
# #                     a.target = '_blank';
# #                     li.appendChild(a);
                    
# #                     if (source.snippet) {
# #                         const snippet = document.createElement('p');
# #                         snippet.textContent = source.snippet;
# #                         snippet.style.color = '#666';
# #                         snippet.style.fontSize = '0.9em';
# #                         li.appendChild(snippet);
# #                     }
                    
# #                     sourcesList.appendChild(li);
# #                 });
# #             } else {
# #                 sourcesList.innerHTML = '<li>No sources available</li>';
# #             }
            
# #             // Add forms
# #             const formsList = document.getElementById('forms-list');
# #             if (data.related_forms && data.related_forms.length > 0) {
# #                 data.related_forms.forEach(form => {
# #                     const li = document.createElement('li');
# #                     li.textContent = form;
# #                     formsList.appendChild(li);
# #                 });
# #             } else {
# #                 formsList.innerHTML = '<li>No related forms</li>';
# #             }
            
# #             // Add next steps
# #             const stepsList = document.getElementById('steps-list');
# #             if (data.suggested_next_steps && data.suggested_next_steps.length > 0) {
# #                 data.suggested_next_steps.forEach(step => {
# #                     const li = document.createElement('li');
# #                     li.textContent = step;
# #                     stepsList.appendChild(li);
# #                 });
# #             } else {
# #                 stepsList.innerHTML = '<li>No suggested next steps</li>';
# #             }
            
# #             // Show the response
# #             document.getElementById('response').style.display = 'block';
# #         }
        
# #         function showError(message) {
# #             const errorElement = document.getElementById('error');
# #             errorElement.textContent = message;
# #             errorElement.style.display = 'block';
# #             document.getElementById('loading').style.display = 'none';
# #         }
        
# #         // Allow pressing Enter to submit
# #         document.getElementById('query').addEventListener('keypress', function(e) {
# #             if (e.key === 'Enter') {
# #                 submitQuery();
# #             }
# #         });
# #     </script>
# # </body>
# # </html>
# # """

# # # Write the HTML template
# # with open("templates/index.html", "w") as f:
# #     f.write(html_content)

# # # Define routes
# # @app.route('/')
# # def home():
# #     return render_template('index.html')

# # @app.route('/api/query', methods=['POST'])
# # def query():
# #     try:
# #         data = request.get_json()
        
# #         # Convert to the internal QueryRequest model
# #         internal_request = QueryRequest(
# #             query=data['query'],
# #             max_results=data.get('max_results', 3),
# #             categories=data.get('categories', []),
# #             form_number=data.get('form_number', None)
# #         )
        
# #         # Process the query
# #         response = rag_system.process_query(internal_request)
        
# #         # Convert Pydantic model to dict for JSON response
# #         return jsonify({
# #             'answer': response.answer,
# #             'sources': [source.dict() for source in response.sources],
# #             'related_forms': response.related_forms,
# #             'suggested_next_steps': response.suggested_next_steps
# #         })
# #     except Exception as e:
# #         return jsonify({'error': str(e)}), 500

# # # Run the app
# # if __name__ == "__main__":
# #     app.run(host='0.0.0.0', port=8000, debug=True)

# from flask import Flask, render_template, request, jsonify
# import os
# import torch
# from transformers import AutoModelForCausalLM, AutoTokenizer
# from rag_system_mock import RAGSystemMock, QueryRequest, RAGResponse
# import logging

# # Set up logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Initialize Flask app
# app = Flask(__name__)

# # Create static directory if it doesn't exist
# os.makedirs("static", exist_ok=True)
# os.makedirs("templates", exist_ok=True)

# # Create a class that extends RAGSystemMock to use the fine-tuned model
# class FineTunedRAGSystem(RAGSystemMock):
#     def __init__(self):
#         super().__init__()  # Initialize the base class
        
#         # Load the fine-tuned model
#         model_path = "models/fine-tuned-immigration"
#         logger.info(f"Loading fine-tuned model from {model_path}")
#         try:
#             self.tokenizer = AutoTokenizer.from_pretrained(model_path)
#             self.model = AutoModelForCausalLM.from_pretrained(model_path)
#             self.use_fine_tuned = True
#             logger.info("Fine-tuned model loaded successfully")
#         except Exception as e:
#             logger.error(f"Failed to load fine-tuned model: {e}")
#             logger.info("Falling back to mock answer generator")
#             self.use_fine_tuned = False
    
#     def process_query(self, query_request: QueryRequest) -> RAGResponse:
#         """Override the process_query method to use the fine-tuned model"""
#         logger.info(f"Processing query: {query_request.query}")
        
#         # Step 1: Retrieve relevant context (same as original)
#         context_chunks = self._retrieve_context(query_request)
        
#         if not context_chunks:
#             logger.warning("No context found for query")
#             return RAGResponse(
#                 answer="I couldn't find specific information about this topic in my knowledge base. Please try rephrasing your question or ask about a different immigration topic.",
#                 sources=[],
#                 related_forms=[],
#                 suggested_next_steps=["Try asking about a specific immigration form", "Ask about eligibility requirements", "Ask about green card application processes"]
#             )
        
#         # Step 2: Extract form numbers (same as original)
#         related_forms = self._extract_forms(context_chunks)
        
#         # Step 3: Generate answer using fine-tuned model if available
#         if hasattr(self, 'use_fine_tuned') and self.use_fine_tuned:
#             answer = self._generate_answer_with_model(query_request.query, context_chunks)
#         else:
#             # Otherwise use the mock generator (fallback)
#             answer = self._mock_answer_generator(query_request.query, context_chunks)
        
#         # Rest is the same as original
#         next_steps = self._generate_next_steps(query_request.query, answer, related_forms)
#         formatted_sources = self._format_sources(context_chunks)
        
#         return RAGResponse(
#             answer=answer,
#             sources=formatted_sources,
#             related_forms=related_forms[:5],
#             suggested_next_steps=next_steps
#         )
    
#     def _generate_answer_with_model(self, query, context_chunks):
#         """Generate an answer using the fine-tuned model"""
#         try:
#             # Prepare context from top chunks
#             context = "\n".join([
#                 f"Source: {chunk['metadata']['title']}\n{chunk['text'][:300]}..."
#                 for chunk in context_chunks[:3]
#             ])
            
#             # Create prompt
#             prompt = f"""### Question: {query}

# ### Context:
# {context}

# ### Answer:"""
            
#             # Generate the answer
#             inputs = self.tokenizer(prompt, return_tensors="pt")
            
#             with torch.no_grad():
#                 outputs = self.model.generate(
#                     inputs["input_ids"],
#                     max_new_tokens=150,
#                     temperature=0.7,
#                     top_p=0.9,
#                     do_sample=True,
#                     pad_token_id=self.tokenizer.eos_token_id
#                 )
            
#             # Decode the generated text
#             generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
#             # Extract only the answer part
#             answer_start = generated_text.find("### Answer:")
#             if answer_start != -1:
#                 answer = generated_text[answer_start + len("### Answer:"):].strip()
#             else:
#                 answer = generated_text[len(prompt):].strip()
            
#             # If the answer is too short, fall back to mock generator
#             if len(answer) < 20:
#                 return self._mock_answer_generator(query, context_chunks)
                
#             return answer
            
#         except Exception as e:
#             logger.error(f"Error generating answer with model: {e}")
#             return self._mock_answer_generator(query, context_chunks)

# # Create RAG system instance (uses the enhanced version)
# try:
#     rag_system = FineTunedRAGSystem()
#     logger.info("Using fine-tuned model for answers")
# except Exception as e:
#     logger.error(f"Failed to initialize fine-tuned system: {e}")
#     rag_system = RAGSystemMock()
#     logger.info("Using mock system for answers")

# # The complete HTML template
# html_content = """
# <!DOCTYPE html>
# <html lang="en">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0">
#     <title>Immigration Assistant</title>
#     <style>
#         body {
#             font-family: Arial, sans-serif;
#             line-height: 1.6;
#             margin: 0;
#             padding: 20px;
#             max-width: 900px;
#             margin: 0 auto;
#         }
#         h1 {
#             color: #2c3e50;
#             text-align: center;
#             margin-bottom: 30px;
#         }
#         .query-form {
#             background-color: #f8f9fa;
#             padding: 20px;
#             border-radius: 8px;
#             margin-bottom: 20px;
#             box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
#         }
#         .form-group {
#             margin-bottom: 15px;
#         }
#         label {
#             display: block;
#             margin-bottom: 5px;
#             font-weight: bold;
#         }
#         input[type="text"] {
#             width: 100%;
#             padding: 10px;
#             border: 1px solid #ddd;
#             border-radius: 4px;
#             font-size: 16px;
#         }
#         button {
#             background-color: #3498db;
#             color: white;
#             border: none;
#             padding: 10px 15px;
#             border-radius: 4px;
#             cursor: pointer;
#             font-size: 16px;
#         }
#         button:hover {
#             background-color: #2980b9;
#         }
#         .response {
#             background-color: #f8f9fa;
#             padding: 20px;
#             border-radius: 8px;
#             margin-top: 20px;
#             display: none;
#             box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
#         }
#         .answer {
#             margin-bottom: 20px;
#             padding-bottom: 20px;
#             border-bottom: 1px solid #eee;
#         }
#         .sources, .forms, .next-steps {
#             margin-top: 20px;
#         }
#         .loading {
#             text-align: center;
#             display: none;
#             margin: 20px 0;
#         }
#         .error {
#             color: #e74c3c;
#             background-color: #fdeded;
#             padding: 10px;
#             border-radius: 4px;
#             margin-top: 10px;
#             display: none;
#         }
#     </style>
# </head>
# <body>
#     <h1>Immigration Assistant</h1>
    
#     <div class="query-form">
#         <div class="form-group">
#             <label for="query">Ask a question about US immigration:</label>
#             <input type="text" id="query" placeholder="e.g., How do I apply for a green card?">
#         </div>
#         <button onclick="submitQuery()">Ask Question</button>
#         <div class="error" id="error"></div>
#     </div>
    
#     <div class="loading" id="loading">
#         <p>Processing your question...</p>
#     </div>
    
#     <div class="response" id="response">
#         <div class="answer">
#             <h2>Answer</h2>
#             <p id="answer-text"></p>
#         </div>
        
#         <div class="sources">
#             <h3>Sources</h3>
#             <ul id="sources-list"></ul>
#         </div>
        
#         <div class="forms">
#             <h3>Related Forms</h3>
#             <ul id="forms-list"></ul>
#         </div>
        
#         <div class="next-steps">
#             <h3>Suggested Next Steps</h3>
#             <ul id="steps-list"></ul>
#         </div>
#     </div>
    
#     <script>
#         async function submitQuery() {
#             const query = document.getElementById('query').value.trim();
            
#             if (!query) {
#                 showError("Please enter a question");
#                 return;
#             }
            
#             // Show loading, hide previous response and errors
#             document.getElementById('loading').style.display = 'block';
#             document.getElementById('response').style.display = 'none';
#             document.getElementById('error').style.display = 'none';
            
#             try {
#                 const response = await fetch('/api/query', {
#                     method: 'POST',
#                     headers: {
#                         'Content-Type': 'application/json'
#                     },
#                     body: JSON.stringify({
#                         query: query,
#                         max_results: 3
#                     })
#                 });
                
#                 if (!response.ok) {
#                     throw new Error('Failed to get a response from the server');
#                 }
                
#                 const data = await response.json();
#                 displayResponse(data);
#             } catch (error) {
#                 showError(error.message);
#             } finally {
#                 document.getElementById('loading').style.display = 'none';
#             }
#         }
        
#         function displayResponse(data) {
#             // Set answer text
#             document.getElementById('answer-text').textContent = data.answer;
            
#             // Clear previous lists
#             document.getElementById('sources-list').innerHTML = '';
#             document.getElementById('forms-list').innerHTML = '';
#             document.getElementById('steps-list').innerHTML = '';
            
#             // Add sources
#             const sourcesList = document.getElementById('sources-list');
#             if (data.sources && data.sources.length > 0) {
#                 data.sources.forEach(source => {
#                     const li = document.createElement('li');
#                     const a = document.createElement('a');
#                     a.href = source.url;
#                     a.textContent = source.title;
#                     a.target = '_blank';
#                     li.appendChild(a);
                    
#                     if (source.snippet) {
#                         const snippet = document.createElement('p');
#                         snippet.textContent = source.snippet;
#                         snippet.style.color = '#666';
#                         snippet.style.fontSize = '0.9em';
#                         li.appendChild(snippet);
#                     }
                    
#                     sourcesList.appendChild(li);
#                 });
#             } else {
#                 sourcesList.innerHTML = '<li>No sources available</li>';
#             }
            
#             // Add forms
#             const formsList = document.getElementById('forms-list');
#             if (data.related_forms && data.related_forms.length > 0) {
#                 data.related_forms.forEach(form => {
#                     const li = document.createElement('li');
#                     li.textContent = form;
#                     formsList.appendChild(li);
#                 });
#             } else {
#                 formsList.innerHTML = '<li>No related forms</li>';
#             }
            
#             // Add next steps
#             const stepsList = document.getElementById('steps-list');
#             if (data.suggested_next_steps && data.suggested_next_steps.length > 0) {
#                 data.suggested_next_steps.forEach(step => {
#                     const li = document.createElement('li');
#                     li.textContent = step;
#                     stepsList.appendChild(li);
#                 });
#             } else {
#                 stepsList.innerHTML = '<li>No suggested next steps</li>';
#             }
            
#             // Show the response
#             document.getElementById('response').style.display = 'block';
#         }
        
#         function showError(message) {
#             const errorElement = document.getElementById('error');
#             errorElement.textContent = message;
#             errorElement.style.display = 'block';
#             document.getElementById('loading').style.display = 'none';
#         }
        
#         // Allow pressing Enter to submit
#         document.getElementById('query').addEventListener('keypress', function(e) {
#             if (e.key === 'Enter') {
#                 submitQuery();
#             }
#         });
#     </script>
# </body>
# </html>
# """

# # Write the HTML template
# with open("templates/index.html", "w") as f:
#     f.write(html_content)

# # Define routes
# @app.route('/')
# def home():
#     return render_template('index.html')

# @app.route('/api/query', methods=['POST'])
# def query():
#     try:
#         data = request.get_json()
        
#         # Convert to the internal QueryRequest model
#         internal_request = QueryRequest(
#             query=data['query'],
#             max_results=data.get('max_results', 3),
#             categories=data.get('categories', []),
#             form_number=data.get('form_number', None)
#         )
        
#         # Process the query
#         response = rag_system.process_query(internal_request)
        
#         # Convert Pydantic model to dict for JSON response
#         return jsonify({
#             'answer': response.answer,
#             'sources': [source.dict() for source in response.sources],
#             'related_forms': response.related_forms,
#             'suggested_next_steps': response.suggested_next_steps
#         })
#     except Exception as e:
#         logger.error(f"Error processing query: {e}")
#         return jsonify({'error': str(e)}), 500

# # Run the app
# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=8006, debug=True)
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
from immigration_assistant.translator.agent import TranslatorAgent

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
    dsn="postgresql://@localhost:5432",
    database="maia",
    pool_size=(10, 10)
)

# Adjust paths to be relative to the base directory
user_reg_sql_path = os.path.join(base_dir, "immigration_assistant/user-registration/sql")
rag_sql_path = os.path.join(base_dir, "immigration_assistant/rag/sql")
faqs_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json")
forms_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/forms")
legislation_path = os.path.join(base_dir, "immigration_assistant/rag/uscis-crawler/documents/legislation")
translator_agent = TranslatorAgent(verbose=True)

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
    api_token=,
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
            translator_agent=translator_agent,
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
                'content': result.get('final_response', result.get('initial_response', ''))
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