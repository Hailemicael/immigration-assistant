from __future__ import annotations as _annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

import asyncpg
import pydantic_core
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, TypeAdapter
import helpers


@dataclass
class Deps:
    model: SentenceTransformer
    pool: asyncpg.Pool


class FormFiling(BaseModel):
    category: str
    paper_fee: Optional[str] = None
    online_fee: Optional[str] = None

class FormFee(BaseModel):
    id: str
    topic_id: str
    link: Optional[str] = None
    filings: Optional[List[FormFiling]] = None

class FormData(BaseModel):
    id: str
    title: str
    link: str
    description: str
    file_online: bool

class FormMetadata(BaseModel):
    id: str
    title: str
    link: str
    description: str
    file_online: bool
    forms: List[FormData]
    fees: Dict[str, FormFee]


form_metadata_adapter = TypeAdapter(FormMetadata)

async def populate_db(forms_dir: Path, pool: asyncpg.Pool, model: SentenceTransformer) -> None:
    """Build the forms database from JSON files."""
    print("Populating Forms tables...")
    # If no JSON files exist yet, create a sample file
    metadata_paths = list(forms_dir.rglob("*.json"))

    print(f"Found {len(metadata_paths)} forms to process.")

    print("Processing form data files...")
    sem = asyncio.Semaphore(5)  # Limit concurrent processing

    async with asyncio.TaskGroup() as tg:
        for path in metadata_paths:
            tg.create_task(process_form_files(sem, model, pool, path))
    
    print("Database build complete.")

async def process_form_files(
    sem: asyncio.Semaphore,
    model: SentenceTransformer,
    pool: asyncpg.Pool,
    metadata_path: Path,
) -> None:
    """Process a single form JSON file and insert its data into the database."""
    async with sem:
        try:
            print(f"Processing {metadata_path}...")

            # Load and validate the JSON data
            with open(metadata_path, 'r') as f:
                json_data = dict(json.load(f))

            metadata = form_metadata_adapter.validate_python(json_data)
            await process_form_filings(model, pool, metadata)
            await process_form_pdfs(model, pool, metadata_path, metadata)
            await process_form_html(model, pool, metadata_path, metadata)


        except Exception as e:
            print(f"Error processing {metadata_path}: {e}")

async  def process_form_pdfs(
        model: SentenceTransformer,
        pool: asyncpg.Pool,
        metadata_path: Path,
        metadata: FormMetadata,
) -> None:
    for form in metadata.forms:

        # Check if this pdf already exists
        exists = await pool.fetchval(
            'SELECT 1 FROM form_pdfs WHERE form_id = $1 AND file_name = $2',
            metadata.id, form.id
        )

        if exists:
            print(f"Skipping existing entry: {metadata.id} - {form.id}")
            continue

        async with pool.acquire() as conn:
           async with conn.transaction():
                try:
                    await conn.execute(
                        '''
                        INSERT INTO form_pdfs (form_id, file_name, file_url, title, metadata, is_instructions)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ''',
                                    metadata.id,
                                    form.id,
                                    form.link,
                                    form.title,
                                    form.description,
                                    "Instructions" in form.title or "instr" in form.id
                                )

                    print(f"Inserted: {metadata.id} - {form.id}")
                    try:
                        chunks = helpers.read_and_chunk_pdf(f"{metadata_path.parent}/{form.id}")
                    except Exception as e:
                        print(f"An error occurred reading PDF, {metadata.id} - {form.id}", e)
                        raise

                    # Process each chunk in the pdf
                    for i, chunk in enumerate(chunks):
                        # Check if this filing already exists
                        exists = await conn.fetchval(
                            'SELECT 1 FROM form_chunks WHERE form_name = $1 AND content_chunk = $2',
                            form.id, chunk
                        )

                        if exists:
                            print(f"Skipping existing entry: {metadata.id} - {form.id} - chunk: {i}")
                            continue

                        # Generate embedding for the category text
                        print(f"Generating embedding for: {metadata.id} - {form.id} - chunk: {i}")

                        # Use sentence-transformers to generate the embedding
                        embedding_vector = model.encode(chunk)

                        # Convert numpy array to list for JSON serialization
                        embedding_list = embedding_vector.tolist()
                        embedding_json = pydantic_core.to_json(embedding_list).decode()
                        # Insert into database
                        await conn.execute(
                            '''
                            INSERT INTO form_chunks (form_id, form_name, content_chunk, chunk_embedding)
                            VALUES ($1, $2, $3, $4)
                            ''',
                            metadata.id,
                            form.id,
                            chunk,
                            embedding_json,
                        )
                        print(f"Inserted: {metadata.id} - {form.id} - chunk: {i}")
                    print(f"Processed {metadata.id} - {form.id} ({len(chunks)} chunks)")
                except Exception as e:
                    print("An error occurred, rolling back the transaction:", e)
                    raise


async def process_form_filings(
    model: SentenceTransformer,
    pool: asyncpg.Pool,
    metadata: FormMetadata,
) -> None:
    # Process each filing in the form
    for fee in metadata.fees.values():
        # Check if this filing already exists
        exists = await pool.fetchval(
            'SELECT 1 FROM form_fees WHERE form_id = $1 AND topic_id = $2',
            metadata.id, fee.topic_id
        )

        if exists:
            print(f"Skipping existing entry: {metadata.id} - {fee.topic_id}")
            continue
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        '''
                          INSERT INTO form_fees (form_id, topic_id, fee_link)
                          VALUES ($1, $2, $3)
                          ''',
                                metadata.id,
                                fee.topic_id,
                                fee.link,
                    )
                    for filing in fee.filings:
                        # Check if this filing already exists
                        exists = await conn.fetchval(
                            'SELECT 1 FROM form_filings WHERE form_id = $1 AND topic_id = $2 AND category = $3',
                            metadata.id,
                            fee.topic_id,
                            filing.category
                        )

                        if exists:
                            print(f"Skipping existing entry: {metadata.id} - {filing.category}")
                            continue

                        # Generate embedding for the category text
                        print(f"Generating embedding for: {filing.category}")

                        # Use sentence-transformers to generate the embedding
                        embedding_vector = model.encode(filing.category)

                        # Convert numpy array to list for JSON serialization
                        embedding_list = embedding_vector.tolist()
                        embedding_json = pydantic_core.to_json(embedding_list).decode()
                        # Insert into database
                        await conn.execute(
                            '''
                            INSERT INTO form_filings (form_id, topic_id, category, paper_fee, online_fee, category_embedding)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ''',
                            metadata.id,
                            fee.topic_id,
                            filing.category,
                            filing.paper_fee,
                            filing.online_fee,
                            embedding_json,
                        )

                        print(f"Inserted: {metadata.id} - {filing.category}")
                    print(
                        f"Processed {metadata.id} - {metadata.title} ({len(fee.filings)} filings)")
                except Exception as e:
                    print("An error occurred, rolling back the transaction:", e)
                    raise


async def process_form_html(
        model: SentenceTransformer,
        pool: asyncpg.Pool,
        metadata_path: Path,
        metadata: FormMetadata) -> None:

    html_paths = metadata_path.parent.glob("*.html")
    for html_path in html_paths:
        # Step 1: Read the HTML content
        html_content = helpers.read_file_to_string(html_path)

        # Step 2: Chunk the HTML content
        for i, chunk in enumerate(helpers.chunk_html_content(html_content, "html.parser")):
            async with pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        # Check if this pdf already exists
                        exists = await conn.fetchval(
                            'SELECT 1 FROM form_html_chunks WHERE form_id = $1 AND file_name = $2 AND content_chunk = $3',
                            metadata.id, html_path.name, ""
                        )

                        if exists:
                            print(f"Skipping existing entry: {metadata.id} - {html_path.name} - chunk: {i}")
                            continue

                        # Generate embedding for the category text
                        print(f"Generating embedding for: {metadata.id} - {html_path.name} - chunk: {i}")

                        # Use sentence-transformers to generate the embedding
                        embedding_vector = model.encode(chunk)

                        # Convert numpy array to list for JSON serialization
                        embedding_list = embedding_vector.tolist()
                        embedding_json = pydantic_core.to_json(embedding_list).decode()
                        # Insert into database
                        await conn.execute(
                            '''
                            INSERT INTO form_html_chunks (form_id, file_name, content_chunk, chunk_embedding)
                            VALUES ($1, $2, $3, $4)
                            ''',
                            metadata.id,
                            html_path.name,
                            chunk,
                            embedding_json,
                        )
                        print(f"Inserted: {metadata.id} - {html_path.name} - chunk: {i}")
                    except Exception as e:
                        print("An error occurred, rolling back the transaction:", e)
                        raise

# async def search_forms(search_query: str):
#     """Search for forms based on category similarity."""
#     print(f"Searching for: {search_query}")
#
#     # Load the same model used for encoding
#     model = SentenceTransformer('all-MiniLM-L6-v2')
#
#     # Generate embedding for the search query
#     embedding_vector = model.encode(search_query)
#
#     # Convert numpy array to list for JSON serialization
#     embedding_list = embedding_vector.tolist()
#     embedding_json = pydantic_core.to_json(embedding_list).decode()
#     # print(len(embedding_json))
#     async with database_connect(False) as pool:
#         # Search for similar categories
#         rows = await pool.fetch(
#             '''
#             SELECT form_id, category, paper_fee, online_fee,
#                    1 - (category_embedding <=> $1) AS similarity
#             FROM form_filings
#             ORDER BY similarity DESC
#             LIMIT 10
#             ''',
#             embedding_json,
#         )
#
#         print("\nSearch results:")
#         print("=" * 80)
#
#         for row in rows:
#             print(f"Form ID: {row['form_id']}")
#             print(f"Category: {row['category']}")
#             print(f"Paper Fee: {row['paper_fee']}")
#             print(f"Online Fee: {row['online_fee']}")
#             print(f"Similarity Score: {row['similarity']:.4f}")
#             print("-" * 80)