from __future__ import annotations as _annotations

import json
from dataclasses import dataclass
from pathlib import Path
import asyncio

import asyncpg
import torch
from sentence_transformers import SentenceTransformer
from pydantic import BaseModel, TypeAdapter
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

from . import helpers
from ..rag.vector_database import VectorDatabase


class LegaleseTranslator:
    def __init__(self, model_path: str, disabled: bool = False):
        self.disabled = disabled
        if not disabled:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path).to(
                "cuda" if torch.cuda.is_available() else "cpu"
            )

    def translate(self, text: str) -> str:
        if self.disabled:
            return ''
        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.model.device)
        outputs = self.model.generate(**inputs, max_new_tokens=512)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)


@dataclass
class Deps:
    model: SentenceTransformer
    translator: LegaleseTranslator
    pool: asyncpg.Pool


class LegislationMetadata(BaseModel):
    act: str
    code: str
    link: str
    description: str


legislation_metadata_adapter = TypeAdapter(LegislationMetadata)


class LegislationDatabase(VectorDatabase):
    def __init__(self,
                 model: SentenceTransformer,
                 translator: LegaleseTranslator,
                 data_dir: Path,
                 insert_embedding_prefix: str = None,
                 query_embedding_prefix: str = None) -> None:
        super().__init__(model, data_dir, insert_embedding_prefix, query_embedding_prefix)
        self.translator = translator
        self.semaphore = asyncio.Semaphore(5)

    async def populate(self, pool: asyncpg.Pool) -> None:
        print("Populating legislation.sections and legislation.paragraphs...")
        json_files = list(self.data_dir.glob("*.json"))

        for file_path in json_files:
            print(f"📄 Processing file: {file_path.name}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await self._insert_from_flat_hierarchy(conn, data)
            except Exception as e:
                print(f"❌ Failed to process {file_path.name}: {e}")

        print("✔ Legislation import complete.")

    async def _insert_from_flat_hierarchy(self, conn, data: dict):
        for chapter in data.get("chapters", {}).values():
            for subchapter in chapter.get("sub_chapters", {}).values():
                for part in subchapter.get("parts", {}).values():
                    for section in part.get("sections", {}).values():
                        await self._insert_section_and_paragraphs(conn, section)

    async def _insert_section_and_paragraphs(self, conn, section: dict):
        text = section.get("text", "").strip()
        if not text:
            return

        print(f"→ Section {section['id']}")
        title = section.get("label", {}).get("description") or section.get("title", "")
        title_embedding = helpers.generate_embeddings(self.model, title)
        text_embedding = helpers.generate_embeddings(self.model, text)

        await conn.execute("""
            INSERT INTO legislation.sections (id, title, text, text_embedding, title_embedding)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT DO NOTHING 
        """, section["id"], title, text, text_embedding, title_embedding)

        for para in section.get("paragraphs", []):
            await self._insert_paragraph(conn, para, section["id"])

    async def _insert_paragraph(self, conn, paragraph: dict, section_id: str):
        text = paragraph.get("text", "").strip()
        if not text:
            return

        print(f"  → Paragraph {paragraph['id']}")
        title = paragraph.get("title", "")
        title_embedding = helpers.generate_embeddings(self.model, title)
        text_embedding = helpers.generate_embeddings(self.model, text)

        await conn.execute("""
            INSERT INTO legislation.paragraphs (id, section_id, title, text, text_embedding, title_embedding)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT DO NOTHING 
           
        """, paragraph["id"], section_id, title, text, text_embedding, title_embedding)

    async def search(self, pool: asyncpg.Pool, search_query: str, limit: int = 10, verbose: bool = False):
        if verbose:
            print(f"🔍 Searching legislation for: {search_query}")

        embedding = helpers.generate_embeddings(self.model, search_query, prefix=self.query_embedding_prefix)

        rows = await pool.fetch("""
            SELECT * FROM legislation.search_legislation_chunks($1, $2)
        """, embedding, limit)

        results = []
        for row in rows:
            results.append({
                'match_id': row['match_id'],
                'source': row['source'],
                'title': row['title'],
                'chunk': row['chunk'],
                'text_similarity': row['text_similarity'],
                'title_similarity': row['title_similarity'],
                'combined_score': row['combined_score'],
            })

        if verbose:
            print(f"\n🔹 Found {len(results)} results")

        return results

    @staticmethod
    async def clear(pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            print("Clearing legislation tables...")
            await conn.execute("TRUNCATE TABLE legislation.paragraphs, legislation.sections RESTART IDENTITY CASCADE")
