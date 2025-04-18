import json
from pathlib import Path
from typing import Dict, Any

import pydantic_core
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer


def read_file_to_string(file_path):
    try:
        with open(file_path, 'r') as file:
            file_content = file.read()
            return file_content
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
        return None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

def read_and_chunk_pdf(pdf_path:str | Path, password: str = "", chunk_size=500):
    reader = PdfReader(pdf_path)
    # Check if the PDF is encrypted
    if reader.is_encrypted:
        # Decrypt the PDF using the password
        try:
            reader.decrypt(password)  # PyCryptodome is required for AES decryption
            print("PDF decrypted successfully!")
        except Exception as e:
            print(f"Failed to decrypt PDF: {e}")
            return
    full_text = ""
    match chunk_size:
        case None:
            for page in reader.pages:
                full_text += page.extract_text()
            return [full_text]
        case "Pages":
            return [page.extract_text() for page in reader.pages]
        case _ :
            for page in reader.pages:
                full_text += page.extract_text()
            return  [full_text[i:i + chunk_size] for i in range(0, len(full_text), chunk_size)]

def chunk_html_content(content: str, features: str, chunk_size: int = 512) -> list[str]:
    """
    Splits HTML content into smaller chunks.
    :param features:
    :param content: The raw HTML content.
    :param chunk_size: Maximum number of characters per chunk.
    :return: List of text chunks.
    """
    soup = BeautifulSoup(content, features)
    text_content = soup.get_text(separator=" ", strip=True)  # Strips tags, keeps readable text

    # Create chunks
    chunks = []
    current_chunk = []

    for word in text_content.split():
        if len(" ".join(current_chunk)) + len(word) < chunk_size:
            current_chunk.append(word)
        else:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def generate_embeddings(model: SentenceTransformer, content: str, prefix: str = None) -> str:
    # if context is None:
    #     context = {}
    #
    # context[content] = content
    # Use sentence-transformers to generate the embedding
    if content is not None:
        content = f"{prefix}: {content}"
    embedding_vector = model.encode(content)

    # Convert numpy array to list for JSON serialization
    embedding_list = embedding_vector.tolist()
    return pydantic_core.to_json(embedding_list).decode()