import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
from vector_database import SimpleVectorDB

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QueryRequest(BaseModel):
    query: str
    max_results: int = Field(5, description="Maximum number of results to return")
    categories: List[str] = Field([], description="Filter by categories")
    form_number: Optional[str] = Field(None, description="Filter by form number")

class Source(BaseModel):
    title: str
    url: str
    snippet: str

class RAGResponse(BaseModel):
    answer: str
    sources: List[Source] = []
    related_forms: List[str] = []
    suggested_next_steps: List[str] = []

class RAGSystem:
    def __init__(self):
        # Load API key
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            logger.warning("OPENAI_API_KEY not found in environment variables")
        
        # Initialize the model
        logger.info("Loading embedding model")
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # Initialize vector database
        logger.info("Loading vector database")
        self.vector_db = SimpleVectorDB(
            embeddings_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/embeddings/embeddings.json',
            chunks_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/embeddings/chunks.json'
        )
    
    def process_query(self, query_request: QueryRequest) -> RAGResponse:
        """Process a user query using RAG"""
        logger.info(f"Processing query: {query_request.query}")
        
        # Step 1: Retrieve relevant context
        context_chunks = self._retrieve_context(query_request)
        
        if not context_chunks:
            logger.warning("No context found for query")
            return RAGResponse(
                answer="I couldn't find specific information about this topic in my knowledge base. Please try rephrasing your question or ask about a different immigration topic.",
                sources=[],
                related_forms=[],
                suggested_next_steps=["Try asking about a specific immigration form", "Ask about eligibility requirements", "Ask about green card application processes"]
            )
        
        # Step 2: Extract form numbers and other metadata
        related_forms = self._extract_forms(context_chunks)
        
        # Step 3: Generate answer using LLM
        prompt = self._create_prompt(query_request.query, context_chunks)
        answer = self._query_llm(prompt)
        
        # Step 4: Generate suggested next steps
        next_steps = self._generate_next_steps(query_request.query, answer, related_forms)
        
        # Step 5: Format sources for citation
        formatted_sources = self._format_sources(context_chunks)
        
        # Create response
        response = RAGResponse(
            answer=answer,
            sources=formatted_sources,
            related_forms=related_forms,
            suggested_next_steps=next_steps
        )
        
        return response
    
    def _retrieve_context(self, query_request: QueryRequest) -> List[Dict[str, Any]]:
        """Retrieve relevant context for the query"""
        chunks = []
        
        # First, try to get form-specific information if a form number is provided
        if query_request.form_number:
            form_chunks = self.vector_db.filter_by_form(query_request.form_number, top_k=3)
            chunks.extend(form_chunks)
        
        # Do a semantic search based on the query
        semantic_chunks = self.vector_db.search_by_text(
            query_request.query, 
            self.embedding_model, 
            top_k=query_request.max_results
        )
        chunks.extend(semantic_chunks)
        
        # Remove duplicates by URL
        unique_chunks = []
        seen_urls = set()
        
        for chunk in chunks:
            if chunk['metadata']['url'] not in seen_urls:
                unique_chunks.append(chunk)
                seen_urls.add(chunk['metadata']['url'])
                
                # Limit to max_results
                if len(unique_chunks) >= query_request.max_results:
                    break
        
        return unique_chunks
    
    def _extract_forms(self, context_chunks: List[Dict[str, Any]]) -> List[str]:
        """Extract form numbers from context chunks"""
        all_forms = set()
        
        for chunk in context_chunks:
            if 'metadata' in chunk and 'forms_mentioned' in chunk['metadata']:
                for form in chunk['metadata']['forms_mentioned']:
                    all_forms.add(form)
        
        return list(all_forms)
    
    def _create_prompt(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Create prompt for the LLM"""
        # Combine context into a single text
        context_text = "\n\n".join([
            f"Source: {chunk['metadata']['title']} ({chunk['metadata']['url']})\n{chunk['text'][:1000]}"  # Limit text length
            for chunk in context_chunks
        ])
        
        # Create the prompt
        prompt = f"""You are an expert immigration assistant. Answer the following question based on the information provided. 
If you don't know the answer based on the provided information, say so clearly - do not make up information.

QUESTION: {query}

CONTEXT INFORMATION:
{context_text}

When referring to forms, always include the form number (e.g., Form I-485). 
If you mention costs or timelines, be clear about when the information was last updated.
Provide a clear, concise answer that directly addresses the question.

ANSWER:"""
        
        return prompt
    
    def _query_llm(self, prompt: str) -> str:
        """Query the LLM with the prompt"""
        try:
            if not self.openai_api_key:
                return "API key not configured. Please add your OpenAI API key to the .env file."
                
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_api_key}"
            }
            
            payload = {
                "model": "gpt-3.5-turbo",  # You can use a different model if preferred
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant specializing in US immigration."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 500
            }
            
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            
            response_data = response.json()
            
            if "choices" in response_data and len(response_data["choices"]) > 0:
                return response_data["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"Unexpected response format: {response_data}")
                return "I'm sorry, I encountered an error processing your question."
                
        except Exception as e:
            logger.error(f"Error querying LLM: {e}")
            return "I'm sorry, I encountered an error processing your question."
    
    def _generate_next_steps(self, query: str, answer: str, related_forms: List[str]) -> List[str]:
        """Generate suggested next steps based on the query and answer"""
        next_steps = []
        
        # Add form-related next steps
        for form in related_forms:
            next_steps.append(f"Learn more about {form} requirements")
            next_steps.append(f"Check processing time for {form}")
            
        # Add generic next steps based on common immigration questions
        if "eligibility" in query.lower() or "qualify" in query.lower():
            next_steps.append("Check specific eligibility requirements")
            
        if "cost" in query.lower() or "fee" in query.lower():
            next_steps.append("Get a detailed breakdown of all fees")
            
        if "time" in query.lower() or "processing" in query.lower() or "wait" in query.lower():
            next_steps.append("View current processing times by service center")
            
        if "status" in query.lower() or "check" in query.lower():
            next_steps.append("Check your case status online")
        
        # Limit to 5 suggestions
        return next_steps[:5]
    
    def _format_sources(self, context_chunks: List[Dict[str, Any]]) -> List[Source]:
        """Format sources for citation"""
        sources = []
        
        for chunk in context_chunks:
            sources.append(Source(
                title=chunk["metadata"]["title"],
                url=chunk["metadata"]["url"],
                snippet=chunk["text"][:150] + "..." if len(chunk["text"]) > 150 else chunk["text"]
            ))
            
        return sources

# Simple test function
def test_rag():
    # Initialize the RAG system
    rag = RAGSystem()
    
    # Test with a sample query
    query_request = QueryRequest(
        query="How do I apply for a green card based on marriage?",
        max_results=3
    )
    
    print(f"Processing query: {query_request.query}")
    response = rag.process_query(query_request)
    
    # Print the response
    print("\nAnswer:")
    print(response.answer)
    
    print("\nSources:")
    for source in response.sources:
        print(f"- {source.title} ({source.url})")
    
    print("\nRelated Forms:")
    for form in response.related_forms:
        print(f"- {form}")
    
    print("\nSuggested Next Steps:")
    for step in response.suggested_next_steps:
        print(f"- {step}")

if __name__ == "__main__":
    test_rag()