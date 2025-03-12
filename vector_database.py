import json
import os
import numpy as np
from typing import List, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleVectorDB:
    def __init__(self, embeddings_file=None, chunks_file=None):
        self.embeddings = []
        self.chunks = []
        self.embedding_matrix = None
        
        if embeddings_file and chunks_file:
            self.load_data(embeddings_file, chunks_file)
    
    def load_data(self, embeddings_file, chunks_file):
        """Load embeddings and chunks from files"""
        logger.info(f"Loading embeddings from {embeddings_file}")
        
        # Load embeddings
        with open(embeddings_file, 'r', encoding='utf8') as f:
            self.embeddings = json.load(f)
        
        # Load chunks
        with open(chunks_file, 'r', encoding='utf8') as f:
            self.chunks = json.load(f)
        
        # Create embedding matrix for faster similarity search
        self.embedding_matrix = np.array([emb['embedding'] for emb in self.embeddings])
        
        # Create a mapping from ID to chunk for fast lookup
        self.id_to_chunk = {chunk['id']: chunk for chunk in self.chunks}
        
        logger.info(f"Loaded {len(self.embeddings)} embeddings and {len(self.chunks)} chunks")
        logger.info(f"Embedding dimension: {len(self.embeddings[0]['embedding'])}")
    
    def similarity_search(self, query_embedding, top_k=5):
        """Find the most similar documents to the query embedding"""
        if self.embedding_matrix is None:
            logger.error("No embeddings loaded. Call load_data first.")
            return []
        
        # Convert query to numpy array
        query_embedding = np.array(query_embedding)
        
        # Normalize query embedding
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm
        
        # Normalize document embeddings (if not already normalized)
        norms = np.linalg.norm(self.embedding_matrix, axis=1, keepdims=True)
        normalized_embeddings = self.embedding_matrix / np.maximum(norms, 1e-10)
        
        # Compute dot product (cosine similarity for normalized vectors)
        similarities = np.dot(normalized_embeddings, query_embedding)
        
        # Get top-k indices
        top_indices = np.argsort(-similarities)[:top_k]
        
        # Collect results
        results = []
        for idx in top_indices:
            embedding_id = self.embeddings[idx]['id']
            chunk = self.id_to_chunk.get(embedding_id)
            
            if chunk:
                results.append({
                    'id': embedding_id,
                    'text': chunk['text'],
                    'metadata': chunk['metadata'],
                    'similarity': float(similarities[idx])
                })
        
        return results
    
    def search_by_text(self, query_text, model, top_k=5):
        """Search using a text query"""
        # Generate embedding for the query
        query_embedding = model.encode(query_text)
        
        # Perform search
        return self.similarity_search(query_embedding, top_k)
    
    def filter_by_form(self, form_number, top_k=10):
        """Find chunks that mention a specific form"""
        form_number = form_number.upper()
        results = []
        
        for chunk in self.chunks:
            if 'metadata' in chunk and 'forms_mentioned' in chunk['metadata']:
                if form_number in chunk['metadata']['forms_mentioned']:
                    results.append({
                        'id': chunk['id'],
                        'text': chunk['text'],
                        'metadata': chunk['metadata']
                    })
                    
                    if len(results) >= top_k:
                        break
        
        return results

# Simple test function
def test_vector_db():
    from sentence_transformers import SentenceTransformer
    
    # Load data
    db = SimpleVectorDB(
        embeddings_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/embeddings/embeddings.json',
        chunks_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/embeddings/chunks.json'
    )
    
    # Load model for encoding queries
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    # Test search
    query = "How do I apply for a green card?"
    print(f"\nSearching for: \"{query}\"")
    
    results = db.search_by_text(query, model, top_k=2)
    
    for i, result in enumerate(results):
        print(f"\nResult {i+1} (similarity: {result['similarity']:.4f}):")
        print(f"Title: {result['metadata']['title']}")
        print(f"URL: {result['metadata']['url']}")
        print(f"Text snippet: {result['text'][:150]}...")

if __name__ == "__main__":
    test_vector_db()