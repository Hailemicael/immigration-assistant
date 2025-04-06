from __future__ import annotations as _annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path


import asyncpg
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, TypeAdapter

import helpers


@dataclass
class Deps:
    model: SentenceTransformer
    pool: asyncpg.Pool

class LegislationMetadata(BaseModel):
    act: str
    code: str
    link: str
    description: str

legislation_metadata_adapter = TypeAdapter(LegislationMetadata)

async def populate_db(model:SentenceTransformer, pool: asyncpg.Pool, forms_dir: Path) -> None:
    """Build the forms database from JSON files."""
    print("Populating Legislation tables...")
    # If no JSON files exist yet, create a sample file
    metadata_paths = list(forms_dir.rglob("*.json"))

    print(f"Found {len(metadata_paths)} forms to process.")

    print("Processing legislation data files...")
    sem = asyncio.Semaphore(5)  # Limit concurrent processing

    async with asyncio.TaskGroup() as tg:
        for path in metadata_paths:
            tg.create_task(process_legislation_files(sem, model, pool, path))

    print("Legislation tables build complete.")

async def process_legislation_files(
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

            metadata = legislation_metadata_adapter.validate_python(json_data)
            await process_legislation_xhtml(model, pool, metadata_path, metadata)
        except Exception as e:
            print(f"Error processing {metadata_path}: {e}")

async def process_legislation_xhtml(
        model: SentenceTransformer,
        pool: asyncpg.Pool,
        metadata_path: Path,
        metadata: LegislationMetadata) -> None:

    html_paths = metadata_path.parent.glob("*.html")
    for html_path in html_paths:
        # Step 1: Read the HTML content
        html_content = helpers.read_file_to_string(html_path)
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    exists = await conn.fetchval(
                        'SELECT 1 FROM legislation_html WHERE act = $1 AND code = $2' ,
                        metadata.act, metadata.code,
                    )
                    if exists:
                        print(f"Skipping existing entry: {metadata.act} - {metadata.code} - chunk: {i}")
                        continue

                    context = {
                        "act": metadata.act,
                        "code": metadata.code,
                        "description": metadata.description,
                    }
                    embedding_json = helpers.generate_embeddings(model, metadata.description, context)
                    # Insert into database
                    await conn.execute(
                        '''
                        INSERT INTO legislation_html (act, code, description, link, description_embedding)
                        VALUES ($1, $2, $3)
                        ''',
                        metadata.act,
                        metadata.code,
                        metadata.description,
                        metadata.link,
                        embedding_json,
                    )
                    # Step 2: Chunk the HTML content
                    for i, chunk in enumerate(helpers.chunk_html_content(html_content, "lxml-xml")):
                        # Check if this pdf already exists
                        exists = await conn.fetchval(
                            'SELECT 1 FROM legislation_html_chunks WHERE act = $1 AND code = $2 AND content_chunk = $3',
                            metadata.act, metadata.code, chunk
                        )

                        if exists:
                            print(f"Skipping existing entry: {metadata.act} - {metadata.code} - chunk: {i}")
                            continue

                        # Generate embedding for the category text
                        print(f"Generating embedding for: {metadata.act} - {metadata.code} - chunk: {i}")

                        embedding_json = helpers.generate_embeddings(model, chunk)
                        # Insert into database
                        await conn.execute(
                            '''
                            INSERT INTO legislation_html_chunks (act, code, content_chunk, chunk_embedding)
                            VALUES ($1, $2, $3, $4)
                            ''',
                            metadata.act,
                            metadata.code,
                            chunk,
                            embedding_json,
                        )
                        print(f"Inserted: {metadata.id} - {html_path.name} - chunk: {i}")
                except Exception as e:
                    print("An error occurred, rolling back the transaction:", e)
                    raise

async def search(model: SentenceTransformer, pool: asyncpg.Pool, search_query: str, limit: int = 10):
    """
    Search for immigration legislation based on query similarity.
    Returns legislation objects with act, code, description, relevant chunks, and links.
    Searches both legislation descriptions and content chunks.

    Args:
        model: SentenceTransformer model for encoding the search query
        pool: Database connection pool
        search_query: Query string to search for
        limit: Maximum number of results to return

    Returns:
        List of legislation objects with relevant content and metadata
    """
    print(f"Searching legislation for: {search_query}")

    # Generate embedding for the search query
    embedding_json = helpers.generate_embeddings(model, search_query)

    # Execute the query that fetches legislation, chunks, and links
    rows = await pool.fetch(
        helpers.read_file_to_string("./sql/search-legislation.sql"),
        embedding_json,
        limit
    )

    # Process and organize the results
    legislation_dict = {}

    for row in rows:
        key = f"{row['act']}:{row['code']}"

        # Create a new legislation object if it doesn't exist
        if key not in legislation_dict:
            legislation_dict[key] = {
                'act': row['act'],
                'code': row['code'],
                'description': row['description'],
                'link': row['link'],
                'chunks': [],
                'description_similarity': row['description_similarity'],
                'combined_score': row['combined_score'],
                'match_source': row['match_source']
            }

        # Add the chunk to the legislation (if not NULL)
        if row['content_chunk']:
            legislation_dict[key]['chunks'].append({
                'content': row['content_chunk'],
                'similarity_score': row['content_similarity']
            })

    # Convert the dictionary to a list of legislation objects
    results = list(legislation_dict.values())

    # Sort by the legislation's combined similarity score
    results.sort(key=lambda x: x['combined_score'])

    print(f"\nFound {len(results)} matching legislation items")

    return results