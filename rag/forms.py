from __future__ import annotations as _annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

import asyncpg
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, TypeAdapter

from . import helpers
from Project.immigration_assistant.rag.vector_database import VectorDatabase


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
        print("Populating Forms tables...")
        metadata_paths = list(self.data_dir.rglob("*.json"))
        print(f"Found {len(metadata_paths)} forms to process.")

        sem = asyncio.Semaphore(5)

        async with asyncio.TaskGroup() as tg:
            for path in metadata_paths:
                tg.create_task(self.process_form_files(sem, pool, path))

        print("\u2714 Forms table build complete.")

    async def process_form_files(self, sem: asyncio.Semaphore, pool: asyncpg.Pool, metadata_path: Path) -> None:
        async with sem:
            try:
                print(f"\u2192 Processing Form File: {metadata_path.name}")
                with open(metadata_path, 'r') as f:
                    json_data = dict(json.load(f))

                metadata = form_metadata_adapter.validate_python(json_data)
                print(f"  \u2192 Form ID: {metadata.id}")
                await self.process_form_pdf(pool, metadata)
                await self.process_form_documents(pool, metadata_path ,metadata)
                await self.process_form_instructions(pool, metadata_path, metadata)
                await self.process_form_filings(pool, metadata)
                await self.process_form_html(pool, metadata_path, metadata)

            except Exception as e:
                print(f"❌ Error processing {metadata_path.name}: {e}")

    async def process_form_pdf(self, pool, metadata: FormMetadata) -> None:
        exists = await pool.fetchval(
            'SELECT 1 FROM forms.pdfs WHERE form_id = $1',
            metadata.id,
        )
        if exists:
            print(f"      → Skipping existing PDF: {metadata.id}")
            return
        async with pool.acquire() as conn:
            async with conn.transaction():
                try:
                    print(f"    → Generating description embedding for {metadata.id}")
                    description_embedding_json = helpers.generate_embeddings(self.model, metadata.description, prefix=self.insert_embedding_prefix)

                    await conn.execute(
                        '''
                        INSERT INTO forms.pdfs (form_id, description, description_embedding)
                        VALUES ($1, $2, $3)
                        ''',
                        metadata.id,
                        metadata.description,
                        description_embedding_json,
                        )

                    print(f"✔ Processed {metadata.id}")
                except Exception as e:
                    print(f"❌ Failed to process PDF {metadata.id}: {e}")
                    raise

    async def process_form_documents(self, pool, metadata_path: Path, metadata: FormMetadata) -> None:
        for form in metadata.forms:
            if "Instructions" in form.title or "instr" in form.id:
                continue

            exists = await pool.fetchval(
                'SELECT 1 FROM forms.documents WHERE form_id = $1 AND file_name = $2',
                metadata.id, form.id
            )
            if exists:
                print(f"      → Skipping existing PDF: {form.id}")
                continue

            async with pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        print(f"    → Generating title embedding for {form.id}")
                        title_embedding_json = helpers.generate_embeddings(self.model, form.title, prefix=self.insert_embedding_prefix)

                        await conn.execute(
                            '''
                            INSERT INTO forms.documents (form_id, file_name, file_url, title, metadata, title_embedding)
                            VALUES ($1, $2, $3, $4, $5, $6)
                            ''',
                            metadata.id,
                            form.id,
                            form.link,
                            form.title,
                            form.description,
                            title_embedding_json,
                            )

                        chunks = helpers.read_and_chunk_pdf(f"{metadata_path.parent}/{form.id}", chunk_size="Pages")
                        for i, chunk in enumerate(chunks):
                            exists = await conn.fetchval(
                                'SELECT 1 FROM forms.document_chunks WHERE form_name = $1 AND content_chunk = $2',
                                form.id, chunk
                            )
                            if exists:
                                print(f"        → Chunk {i}: Skipped (already exists)")
                                continue

                            print(f"        → Chunk {i}: Embedding and inserting")
                            embedding_json = helpers.generate_embeddings(self.model, chunk, prefix=self.insert_embedding_prefix)

                            await conn.execute(
                                '''
                                INSERT INTO forms.document_chunks (form_id, form_name, content_chunk, chunk_embedding)
                                VALUES ($1, $2, $3, $4)
                                ''',
                                metadata.id,
                                form.id,
                                chunk,
                                embedding_json,
                            )
                        print(f"      ✔ Processed {form.id} ({len(chunks)} chunks)")
                    except Exception as e:
                        print(f"❌ Failed to process PDF {form.id}: {e}")
                        raise

    async def process_form_instructions(self, pool, metadata_path: Path, metadata: FormMetadata) -> None:
        for form in metadata.forms:
            if not ("Instructions" in form.title or "instr" in form.id):
                continue

            print(f"    → Inserting instruction entry for {form.id}")
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        '''
                        INSERT INTO forms.instructions (form_id, file_name, file_url, title, description, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT DO NOTHING
                        ''',
                        metadata.id,
                        form.id,
                        form.link,
                        form.title,
                        form.description,
                        metadata.description,
                    )

                    chunks = helpers.read_and_chunk_pdf(f"{metadata_path.parent}/{form.id}", chunk_size="Pages")
                    for i, chunk in enumerate(chunks):
                        exists = await conn.fetchval(
                            'SELECT 1 FROM forms.instructions_chunks WHERE form_name = $1 AND content_chunk = $2',
                            form.id, chunk
                        )
                        if exists:
                            print(f"        → Instruction Chunk {i}: Skipped (already exists)")
                            continue

                        print(f"        → Instruction Chunk {i}: Embedding and inserting")
                        embedding_json = helpers.generate_embeddings(self.model, chunk, prefix=self.insert_embedding_prefix)

                        await conn.execute(
                            '''
                            INSERT INTO forms.instructions_chunks (form_id, form_name, content_chunk, chunk_embedding)
                            VALUES ($1, $2, $3, $4)
                            ''',
                            metadata.id,
                            form.id,
                            chunk,
                            embedding_json,
                        )

    async def process_form_filings(self, pool: asyncpg.Pool, metadata: FormMetadata) -> None:
        for fee in metadata.fees.values():
            exists = await pool.fetchval(
                'SELECT 1 FROM forms.fees WHERE form_id = $1 AND topic_id = $2',
                metadata.id, fee.topic_id
            )
            if exists:
                print(f"    → Skipping existing fee entry: {fee.topic_id}")
                continue

            async with pool.acquire() as conn:
                async with conn.transaction():
                    try:
                        await conn.execute(
                            '''
                            INSERT INTO forms.fees (form_id, topic_id, fee_link)
                            VALUES ($1, $2, $3)
                            ''',
                            metadata.id,
                            fee.topic_id,
                            fee.link,
                        )
                        for filing in fee.filings or []:
                            exists = await conn.fetchval(
                                'SELECT 1 FROM forms.filings WHERE form_id = $1 AND topic_id = $2 AND category = $3',
                                metadata.id,
                                fee.topic_id,
                                filing.category
                            )
                            if exists:
                                print(f"        → Skipping filing: {filing.category}")
                                continue

                            print(f"        → Inserting filing: {filing.category}")
                            embedding_json = helpers.generate_embeddings(self.model, filing.category, prefix=self.insert_embedding_prefix)

                            await conn.execute(
                                '''
                                INSERT INTO forms.filings (form_id, topic_id, category, paper_fee, online_fee, category_embedding)
                                VALUES ($1, $2, $3, $4, $5, $6)
                                ''',
                                metadata.id,
                                fee.topic_id,
                                filing.category,
                                filing.paper_fee,
                                filing.online_fee,
                                embedding_json,
                            )
                        print(f"      ✔ Processed fee topic {fee.topic_id}")
                    except Exception as e:
                        print(f"❌ Error inserting filings for topic {fee.topic_id}: {e}")
                        raise

    async def process_form_html(self, pool: asyncpg.Pool, metadata_path: Path, metadata: FormMetadata) -> None:
        html_paths = metadata_path.parent.glob("*.html")
        for html_path in html_paths:
            html_content = html_path.read_text()
            for i, chunk in enumerate(helpers.chunk_html_content(html_content, "html.parser")):
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        try:
                            exists = await conn.fetchval(
                                'SELECT 1 FROM forms.html_chunks WHERE form_id = $1 AND file_name = $2 AND content_chunk = $3',
                                metadata.id, html_path.name, chunk
                            )
                            if exists:
                                print(f"      → HTML Chunk {i}: Skipped")
                                continue

                            embedding_json = helpers.generate_embeddings(self.model, chunk, prefix=self.insert_embedding_prefix)

                            await conn.execute(
                                '''
                                INSERT INTO forms.html_chunks (form_id, file_name, content_chunk, chunk_embedding)
                                VALUES ($1, $2, $3, $4)
                                ''',
                                metadata.id,
                                html_path.name,
                                chunk,
                                embedding_json,
                            )
                            print(f"      → HTML Chunk {i}: Inserted")
                        except Exception as e:
                            print(f"❌ Error processing HTML chunk {i}: {e}")
                            raise

    async def search(self, pool: asyncpg.Pool, search_query: str, limit: int = 10, verbose: bool = False):
        if verbose:
            print(f"🔍 Searching for: {search_query}")

        embedding_json = helpers.generate_embeddings(
            self.model, search_query, prefix=self.query_embedding_prefix
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM forms.find_related_immigration_documentation($1, $2)",
                embedding_json,
                limit
            )

        forms_dict = {}

        for row in rows:
            form_id = row['form_id']

            if form_id not in forms_dict:
                forms_dict[form_id] = {
                    'form_id': form_id,
                    'form_title': row['title'],
                    'form_url': row['pdf_url'],
                    'instructions_url': row['instructions_url'],
                    'description': row['description'],
                    'fee_category': row['related_filing_category'],
                    'paper_fee': row['related_filing_paper_fee'],
                    'online_fee': row['related_filing_online_fee'],
                    'topic_id': row['related_filing_topic_id'],
                    'chunks': [],
                    'similarity_score': row['similarity_score']
                }

            if row['content_chunk']:
                forms_dict[form_id]['chunks'].append({
                    'content': row['content_chunk'],
                    'similarity_score': row['chunk_similarity'],
                    'source': row['chunk_source']
                })

        results = list(forms_dict.values())
        results.sort(key=lambda x: x['similarity_score'])

        if verbose:
            print(f"\u2705 Found {len(results)} matching forms")

        return results

    @staticmethod
    async def clear(pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            print("Clearing immigration form tables...")
            await conn.execute('''CALL truncate_forms_tables()''')
        return None
