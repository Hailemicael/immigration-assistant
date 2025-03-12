import json
import numpy as np
import os
from tqdm import tqdm
import logging
from sentence_transformers import SentenceTransformer
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    def __init__(self, input_file, output_dir, model_name="all-MiniLM-L6-v2"):
        self.input_file = input_file
        self.output_dir = output_dir
        self.model_name = model_name
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Load model
        logger.info(f"Loading model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
    def generate_embeddings(self, chunk_size=512, overlap=50):
        """Generate embeddings for all documents"""
        logger.info(f"Generating embeddings from {self.input_file}")
        
        # Load documents
        with open(self.input_file, 'r', encoding='utf8') as f:
            documents = json.load(f)
        
        logger.info(f"Loaded {len(documents)} documents")
        
        # Process each document
        all_chunks = []
        for doc_idx, doc in enumerate(tqdm(documents, desc="Processing documents")):
            # Create chunks from the document
            chunks = self._create_chunks(doc, chunk_size, overlap)
            all_chunks.extend(chunks)
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(documents)} documents")
        
        # Generate embeddings in batches
        batch_size = 16  # Smaller batch size for less memory usage
        all_embeddings = []
        
        for i in tqdm(range(0, len(all_chunks), batch_size), desc="Generating embeddings"):
            batch = all_chunks[i:i+batch_size]
            texts = [chunk['text'] for chunk in batch]
            
            # Generate embeddings
            with torch.no_grad():
                embeddings = self.model.encode(texts)
            
            # Add embeddings to chunks
            for j, embedding in enumerate(embeddings):
                all_chunks[i+j]['embedding'] = embedding.tolist()
                all_embeddings.append({
                    'id': all_chunks[i+j]['id'],
                    'embedding': embedding.tolist(),
                    'metadata': all_chunks[i+j]['metadata']
                })
        
        # Save embeddings and chunks
        embeddings_file = os.path.join(self.output_dir, 'embeddings.json')
        chunks_file = os.path.join(self.output_dir, 'chunks.json')
        
        with open(embeddings_file, 'w', encoding='utf8') as f:
            json.dump(all_embeddings, f)
        
        with open(chunks_file, 'w', encoding='utf8') as f:
            json.dump(all_chunks, f)
        
        logger.info(f"Saved {len(all_embeddings)} embeddings to {embeddings_file}")
        logger.info(f"Saved {len(all_chunks)} chunks to {chunks_file}")
        
        return all_chunks, all_embeddings
    
    def _create_chunks(self, document, chunk_size, overlap):
        """Split document into chunks for embedding"""
        content = document['content']
        
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        paragraphs = [p for p in paragraphs if p.strip()]
        
        chunks = []
        doc_id = document['url'].split('/')[-1]
        if not doc_id:
            doc_id = "doc_" + str(hash(document['url']) % 10000)
        
        # For very short documents, keep as one chunk
        if len(content) < chunk_size:
            chunks.append({
                'id': f"{doc_id}_0",
                'text': content,
                'metadata': {
                    'url': document['url'],
                    'title': document['title'],
                    'document_type': document['document_type'],
                    'categories': document['categories'],
                    'forms_mentioned': document['forms_mentioned'],
                    'chunk_index': 0,
                    'total_chunks': 1
                }
            })
            return chunks
        
        # Process paragraphs into chunks
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            # If adding this paragraph exceeds chunk size and we already have content
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append({
                    'id': f"{doc_id}_{chunk_index}",
                    'text': current_chunk,
                    'metadata': {
                        'url': document['url'],
                        'title': document['title'],
                        'document_type': document['document_type'],
                        'categories': document['categories'],
                        'forms_mentioned': document['forms_mentioned'],
                        'chunk_index': chunk_index
                    }
                })
                # Start new chunk with overlap
                words = current_chunk.split()
                overlap_text = ' '.join(words[-overlap:]) if len(words) > overlap else ''
                current_chunk = overlap_text + ' ' + para
                chunk_index += 1
            else:
                # Add to current chunk
                if current_chunk:
                    current_chunk += ' ' + para
                else:
                    current_chunk = para
        
        # Add the last chunk if there's anything left
        if current_chunk:
            chunks.append({
                'id': f"{doc_id}_{chunk_index}",
                'text': current_chunk,
                'metadata': {
                    'url': document['url'],
                    'title': document['title'],
                    'document_type': document['document_type'],
                    'categories': document['categories'],
                    'forms_mentioned': document['forms_mentioned'],
                    'chunk_index': chunk_index
                }
            })
        
        # Update total chunks
        for chunk in chunks:
            chunk['metadata']['total_chunks'] = len(chunks)
            
        return chunks

# Simple test function
def generate_test():
    generator = EmbeddingGenerator(
        input_file='/home/hailemicaelyimer/Desktop/immigration-assistant/data/processed/immigration_data.json',
        output_dir='/home/hailemicaelyimer/Desktop/immigration-assistant/data/embeddings'
    )
    chunks, embeddings = generator.generate_embeddings()
    
    print(f"Generated {len(embeddings)} embeddings from {len(chunks)} chunks")
    
    # Print a sample embedding to verify
    if embeddings:
        sample = embeddings[0]
        print(f"\nSample embedding for document {sample['id']}:")
        print(f"Embedding dimension: {len(sample['embedding'])}")
        print(f"First 5 values: {sample['embedding'][:5]}")

if __name__ == "__main__":
    generate_test()