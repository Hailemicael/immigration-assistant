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

import helpers
from vector_database import VectorDatabase


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

        inputs = self.tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=512
        ).to(self.model.device)
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
        print("Populating Legislation tables...")
        path = list(self.data_dir.glob("INA.json"))[0]
        await self.process_immigration_and_nationality_act(pool, path)
        print("Legislation tables build complete.")

    async def process_immigration_and_nationality_act(self, pool: asyncpg.Pool, path: Path) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            async with pool.acquire() as conn:
                async with conn.transaction():
                    await self._insert_title_and_chapters(conn, data)

            print("✔ Finished importing INA content into legislation tables.")
        except Exception as e:
            print(f"❌ Error processing INA JSON: {e}")

    async def generate_embeddings_async(self, original: str, laymen: str | None) -> tuple:
        async with self.semaphore:
            emb_task = asyncio.to_thread(helpers.generate_embeddings, self.model, original, self.insert_embedding_prefix)
            if laymen is not None:
                laymen_emb_task = asyncio.to_thread(helpers.generate_embeddings, self.model, laymen, self.insert_embedding_prefix)
                return await asyncio.gather(emb_task, laymen_emb_task)
            else:
                embedding = await emb_task
                return embedding, None

    async def _insert_title_and_chapters(self, conn, data):
        title_label = data["label"]["level"]
        title_desc = data["label"]["description"]
        print(f"→ Processing Title {title_label}: {title_desc}")

        title_id = await conn.fetchval("""
            INSERT INTO legislation.titles (title_code, description)
            VALUES ($1, $2)
            ON CONFLICT (title_code) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, title_label, title_desc)

        for chapter in data["chapters"].values():
            await self._insert_chapter(conn, title_id, chapter)

    async def _insert_chapter(self, conn, title_id, chapter):
        print(f"  → Chapter {chapter['id']}: {chapter['label']['description']}")

        chapter_id = await conn.fetchval("""
            INSERT INTO legislation.chapters (title_id, chapter_code, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (title_id, chapter_code) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, title_id, chapter["id"], chapter["label"]["description"])

        for subchapter in chapter["sub_chapters"].values():
            await self._insert_subchapter(conn, chapter_id, subchapter)

    async def _insert_subchapter(self, conn, chapter_id, subchapter):
        print(f"    → Subchapter {subchapter['id']}: {subchapter['label']['description']}")

        subchapter_id = await conn.fetchval("""
            INSERT INTO legislation.subchapters (chapter_id, subchapter_code, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (chapter_id, subchapter_code) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, chapter_id, subchapter["id"], subchapter["label"]["description"])

        for part in subchapter["parts"].values():
            await self._insert_part(conn, subchapter_id, part)

    async def _insert_part(self, conn, subchapter_id, part):
        print(f"      → Part {part['id']}: {part['label']['description']}")

        part_id = await conn.fetchval("""
            INSERT INTO legislation.parts (subchapter_id, part_code, description)
            VALUES ($1, $2, $3)
            ON CONFLICT (subchapter_id, part_code) DO UPDATE SET description = EXCLUDED.description
            RETURNING id
        """, subchapter_id, part["id"], part["label"]["description"])

        if "subject_groups" in part:
            for subject_group in part["subject_groups"].values():
                await self._insert_subject_group(conn, part_id, subject_group)
        if "sub_parts" in part:
            for subpart in part["sub_parts"].values():
                await self._insert_subpart(conn, part_id, subpart)
        if "sections" in part:
            for section in part["sections"].values():
                await self._insert_section(conn, part_id, section)

    async def _insert_subpart(self, conn, part_id, subpart):
        print(f"        → Subpart {subpart['id']}: {subpart['label']['description']}")
        for section in subpart["sections"].values():
            await self._insert_section(conn, part_id, section)

    async def _insert_subject_group(self, conn, part_id, group):
        print(f"        → Subject Group {group['id']}: {group['label']['description']}")
        for section in group["sections"].values():
            await self._insert_section(conn, part_id, section)

    async def _insert_section(self, conn, part_id, section):
        text = section.get("text", "").strip()
        if not text:
            return
        print(f"        → Section {section['id']}")

        laymen = None
        if not self.translator.disabled:
            laymen = await asyncio.to_thread(self.translator.translate, text)

        embedding = helpers.generate_embeddings(self.model, text)

        section_id = await conn.fetchval("""
            INSERT INTO legislation.sections (
                part_id, section_code, description, text, chunk_embedding
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (part_id, section_code) DO NOTHING
            RETURNING id
        """, part_id, section["id"], section["label"]["description"], text, embedding)

        if not section_id:
            return

        for subsec in (section.get("subsections") or {}).values():
            await self._insert_subsection(conn, section_id, subsec)

    async def _insert_subsection(self, conn, section_id, subsec):
        text = subsec.get("text", "").strip()
        if not text:
            return
        print(f"          → Subsection {subsec['id']}")

        laymen = None
        if not self.translator.disabled:
            laymen = await asyncio.to_thread(self.translator.translate, text)

        embedding = helpers.generate_embeddings(self.model, text)

        subsection_id = await conn.fetchval("""
            INSERT INTO legislation.subsections (
                section_id, subsection_code, title, text, chunk_embedding
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (section_id, subsection_code) DO NOTHING
            RETURNING id
        """, section_id, subsec["id"], subsec.get("title"), text, embedding)

        if not subsection_id:
            return

        for sss in (subsec.get("sub_subsection") or {}).values():
            await self._insert_sub_subsection(conn, subsection_id, sss)

    async def _insert_sub_subsection(self, conn, subsection_id, sss):
        text = sss.get("text", "").strip()
        if not text:
            return
        print(f"            → Sub-subsection {sss['id']}")

        laymen = None
        if not self.translator.disabled:
            laymen = await asyncio.to_thread(self.translator.translate, text)

        embedding = helpers.generate_embeddings(self.model, text)

        await conn.execute("""
            INSERT INTO legislation.sub_subsections (
                subsection_id, sub_subsection_code, title, text, chunk_embedding
            )
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (subsection_id, sub_subsection_code) DO NOTHING
        """, subsection_id, sss["id"], sss.get("title"), text, embedding)

    async def search(self, pool: asyncpg.Pool, search_query: str, limit: int = 10, verbose: bool = False):
        if verbose:
            print(f"🔍 Searching legislation for: {search_query}")

        embedding_vector = helpers.generate_embeddings(
            self.model, search_query, prefix=self.query_embedding_prefix
        )

        rows = await pool.fetch(
            "SELECT * FROM legislation.search_legislation_chunks($1, $2)",
            embedding_vector,
            limit
        )

        results = []
        for row in rows:
            results.append({
                'match_id': row['match_id'],
                'title': row['title'],
                'chapter': row['chapter'],
                'subchapter': row['subchapter'],
                'chunk': row['chunk'],
                'chunk_similarity': row['chunk_similarity']
            })

        results.sort(key=lambda x: x['chunk_similarity'])

        if verbose:
            print(f"\n🔹 Found {len(results)} matching chunks")

        return results

    @staticmethod
    async def clear(pool: asyncpg.Pool) -> None:
        async with pool.acquire() as conn:
            print("Clearing legislation tables...")
            await conn.execute('''CALL truncate_legislation_tables()''')
        return None
