import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, Field
from vector_database import SimpleVectorDB

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

class RAGSystemMock:
    def __init__(self):
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
        """Process a user query using RAG with a mock LLM"""
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
        
        # Step 3: Generate answer using mock LLM
        answer = self._mock_answer_generator(query_request.query, context_chunks)
        
        # Step 4: Generate suggested next steps
        next_steps = self._generate_next_steps(query_request.query, answer, related_forms)
        
        # Step 5: Format sources for citation
        formatted_sources = self._format_sources(context_chunks)
        
        # Create response
        response = RAGResponse(
            answer=answer,
            sources=formatted_sources,
            related_forms=related_forms[:5],  # Limit to top 5 forms
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
    
    def _mock_answer_generator(self, query: str, context_chunks: List[Dict[str, Any]]) -> str:
        """Generate a mock answer based on the context chunks"""
        # Extract the most relevant chunk (first one)
        if not context_chunks:
            return "I don't have enough information to answer this question."
        
        most_relevant = context_chunks[0]
        text = most_relevant['text']
        title = most_relevant['metadata']['title']
        
        # Simple keyword-based response generation
        query_lower = query.lower()
        
        # Green card related query
        if "green card" in query_lower:
            if "marriage" in query_lower:
                return f"Based on information from {title}, to apply for a green card through marriage to a U.S. citizen, you need to file Form I-130 (Petition for Alien Relative) and Form I-485 (Application to Register Permanent Residence or Adjust Status) if you're already in the U.S. Your spouse must file the I-130 petition on your behalf, and you'll need to provide evidence of a bona fide marriage. The process typically involves submitting documentation, attending a biometrics appointment, and participating in an interview."
            
            return f"According to {title}, to apply for a green card (permanent residence), you generally need to be sponsored by a family member or employer in the United States, or through refugee or asylee status. The specific process depends on your situation and whether you're applying from within the U.S. or from abroad. Various forms may be required, with Form I-485 being the primary application for adjustment of status if you're already in the U.S."
        
        # Citizenship related query
        elif "citizen" in query_lower or "citizenship" in query_lower or "naturalization" in query_lower:
            return f"Based on {title}, to become a U.S. citizen through naturalization, you must be at least 18 years old, be a permanent resident (have a green card) for at least 5 years (or 3 years if married to a U.S. citizen), demonstrate continuous residence, show good moral character, pass an English test and a civics test, and demonstrate an attachment to the principles of the U.S. Constitution. You'll need to file Form N-400, Application for Naturalization."
        
        # Form-related query
        elif "form" in query_lower:
            forms = self._extract_forms(context_chunks)
            if forms:
                form_list = ", ".join(forms[:3])
                return f"According to the USCIS information, relevant forms for your query include {form_list}. You can find these forms on the USCIS website, along with instructions for completing and submitting them. Make sure to use the most current version of each form."
        
        # General immigration query - extract relevant sentences
        sentences = text.split('. ')
        relevant_sentences = []
        
        query_words = set(query_lower.split())
        for sentence in sentences[:10]:  # Look at first 10 sentences
            sentence_lower = sentence.lower()
            if any(word in sentence_lower for word in query_words if len(word) > 3):
                relevant_sentences.append(sentence)
        
        if relevant_sentences:
            answer = ". ".join(relevant_sentences[:3]) + "."
            return f"Based on information from {title}, {answer}"
        
        # Default response
        return f"I found some information about immigration on {title}, but it doesn't directly answer your specific question. You might want to check the USCIS website for more detailed information relevant to your situation."
    
    def _generate_next_steps(self, query: str, answer: str, related_forms: List[str]) -> List[str]:
        """Generate suggested next steps based on the query and answer"""
        next_steps = []
        
        # Add form-related next steps (limit to 2 forms max)
        for form in related_forms[:2]:
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
            
        if "green card" in query.lower() and "marriage" in query.lower():
            next_steps.append("Learn about required documentation for marriage-based petitions")
            
        if "citizen" in query.lower():
            next_steps.append("Learn about the naturalization interview and test")
        
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
def test_rag_mock():
    # Initialize the RAG system
    rag = RAGSystemMock()
    
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
    for form in response.related_forms[:5]:  # Limit to 5 for display
        print(f"- {form}")
    
    print("\nSuggested Next Steps:")
    for step in response.suggested_next_steps:
        print(f"- {step}")
    
    # Test another query
    print("\n" + "-"*50 + "\n")
    query_request = QueryRequest(
        query="What are the requirements for citizenship?",
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

if __name__ == "__main__":
    test_rag_mock()