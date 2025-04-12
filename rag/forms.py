from __future__ import annotations as _annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

import asyncpg
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, TypeAdapter

import helpers
from vector_database import VectorDatabase


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


class FormsDatabase(VectorDatabase):
    def __init__(self, model: SentenceTransformer, data_dir: Path, insert_embedding_prefix: str = None, query_embedding_prefix: str = None) -> None:
        super().__init__(model, data_dir, insert_embedding_prefix, query_embedding_prefix)

    async def populate(self, pool: asyncpg.Pool) -> None:
        """Build the forms database from JSON files."""
        print("Populating Forms tables...")
        # If no JSON files exist yet, create a sample file
        metadata_paths = list(self.data_dir.rglob("*.json"))

        print(f"Found {len(metadata_paths)} forms to process.")

        print("Processing form data files...")
        sem = asyncio.Semaphore(5)  # Limit concurrent processing

        async with asyncio.TaskGroup() as tg:
            for path in metadata_paths:
                tg.create_task(self.process_form_files(sem, pool, path))

        print("Database build complete.")

    async def process_form_files(self,
                                 sem: asyncio.Semaphore,
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
                await self.process_form_filings(pool, metadata)
                await self.process_form_pdfs(pool, metadata_path, metadata)
                await self.process_form_html(pool, metadata_path, metadata)

            except Exception as e:
                print(f"Error processing {metadata_path}: {e}")

    async def process_form_pdfs(self,
                                pool: asyncpg.Pool,
                                metadata_path: Path,
                                metadata: FormMetadata,
                                ) -> None:

        print(f"Generating description embedding for: {metadata.id}")
        description_embedding_json = helpers.generate_embeddings(self.model, metadata.description,
                                                                 prefix=self.insert_embedding_prefix)
        for form in metadata.forms:
            print(f"Generating title embedding for: {metadata.id} - {form.id}")
            title_embedding_json = helpers.generate_embeddings(self.model, form.title, prefix=self.insert_embedding_prefix)
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
                            INSERT INTO form_pdfs (form_id, file_name, file_url, title, description, metadata, is_instructions, title_embedding, description_embedding)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                            ''',
                            metadata.id,
                            form.id,
                            form.link,
                            form.title,
                            metadata.description,
                            form.description,
                            "Instructions" in form.title or "instr" in form.id,
                            title_embedding_json,
                            description_embedding_json,
                            )

                        print(f"Inserted: {metadata.id} - {form.id}")
                        try:
                            chunks = helpers.read_and_chunk_pdf(f"{metadata_path.parent}/{form.id}", chunk_size="Pages")
                        except Exception as e:
                            print(f"An error occurred reading PDF, {metadata.id} - {form.id}", e)
                            raise

                        # Process each chunk in the pdf
                        for i, chunk in enumerate(chunks):
                            # Check if this filing already exists
                            exists = await conn.fetchval(
                                'SELECT 1 FROM form_pdf_chunks WHERE form_name = $1 AND content_chunk = $2',
                                form.id, chunk
                            )

                            if exists:
                                print(f"Skipping existing entry: {metadata.id} - {form.id} - chunk: {i}")
                                continue

                            # Generate embedding for the category text
                            print(f"Generating embedding for: {metadata.id} - {form.id} - chunk: {i}")

                            context = {
                                "form_id": [metadata.id, form.id],
                                "form_title": [metadata.title, form.title],
                                "description": metadata.description,

                            }
                            embedding_json = helpers.generate_embeddings(self.model, chunk, prefix=self.insert_embedding_prefix)

                            # Insert into database
                            await conn.execute(
                                '''
                                INSERT INTO form_pdf_chunks (form_id, form_name, content_chunk, chunk_embedding)
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

    async def process_form_filings(self,
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
                        for filing in fee.filings or []:
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
                            context = {
                                "form_id": metadata.id,
                                "form_title": metadata.title,
                                "description": metadata.description,
                            }
                            embedding_json = helpers.generate_embeddings(self.model, filing.category,
                                                                         prefix=self.insert_embedding_prefix)

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
                            f"Processed {metadata.id} - {metadata.title} ({len(fee.filings or [])} filings)")
                    except Exception as e:
                        print("An error occurred, rolling back the transaction:", e)
                        raise

    async def process_form_html(self,
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
                                metadata.id, html_path.name, chunk
                            )

                            if exists:
                                print(f"Skipping existing entry: {metadata.id} - {html_path.name} - chunk: {i}")
                                continue

                            # Generate embedding for the category text
                            print(f"Generating embedding for: {metadata.id} - {html_path.name} - chunk: {i}")

                            context = {
                                "form_id": metadata.id,
                                "form_title": metadata.title,
                                "description": metadata.description,
                            }
                            embedding_json = helpers.generate_embeddings(self.model, chunk, prefix=self.insert_embedding_prefix)

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

    async def search(self, pool: asyncpg.Pool, search_query: str, limit: int = 10, verbose: bool = False):
        """
        Search for immigration forms based on query similarity.
        Returns form objects with form ID, links, relevant chunks, and appropriate fees.

        Args:
            pool: Database connection pool
            search_query: Query string to search for
            limit: Maximum number of results to return
            verbose:

        Returns:
            List of form objects with relevant content and metadata
        """
        if verbose:
            print(f"Searching for: {search_query}")

        # Generate embedding for the search query
        embedding_json = helpers.generate_embeddings(self.model, search_query, prefix=self.query_embedding_prefix)

        async with pool.acquire() as conn:
            # Execute the stored procedure instead of the SQL file
            rows = await conn.fetch(
                "SELECT * FROM find_related_immigration_documentation($1, $2)",
                embedding_json,
                limit
            )

            forms_dict = {}

            for row in rows:
                form_id = row['form_id']

                # Create a new form object if it doesn't exist
                if form_id not in forms_dict:
                    forms_dict[form_id] = {
                        'form_id': form_id,
                        'form_title': row['title'],  # Changed from form_title to title
                        'form_url': row['pdf_url'],  # Changed from form_url to pdf_url
                        'instructions_url': row['instructions_url'],
                        'description': row['description'],
                        'fee_category': row['related_filing_category'],  # Changed from category
                        'paper_fee': row['related_filing_paper_fee'],  # Changed from paper_fee
                        'online_fee': row['related_filing_online_fee'],  # Changed from online_fee
                        'topic_id': row['related_filing_topic_id'],  # Changed from topic_id
                        'chunks': [],
                        'similarity_score': row['similarity_score'],  # Primary similarity score
                    }

                # Add the chunk to the form (if not NULL)
                if row['content_chunk']:
                    # print(row['content_chunk'])
                    # print("---------------------")
                    forms_dict[form_id]['chunks'].append({
                        'content': row['content_chunk'],
                        'similarity_score': row['chunk_similarity'],  # Changed from content_similarity
                        'source': row['chunk_source']  # New field to indicate pdf or html source
                    })

            # Convert the dictionary to a list of form objects
            results = list(forms_dict.values())

            if verbose:
                print(f"\nFound {len(results)} matching forms")

            return results

    @staticmethod
    async def clear(pool: asyncpg.Pool) -> None:
        """Clear all forms tables in the database."""
        async with pool.acquire() as conn:
            print("Clearing immigration form tables...")
            await conn.execute(
                '''CALL truncate_forms_tables()'''
            )
        return None