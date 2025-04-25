from abc import ABC

from langchain_core.runnables import Runnable


import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Tuple, AsyncGenerator, Optional
import asyncio
import asyncpg
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END
from sentence_transformers import SentenceTransformer

from Project.immigration_assistant.rag import helpers
from Project.immigration_assistant.rag import forms
from Project.immigration_assistant.rag import legislation
from Project.immigration_assistant.rag.config import RAGConfig
from Project.immigration_assistant.config import database
from Project.immigration_assistant.rag.query_results import QueryResult
from Project.immigration_assistant.orchestration.state import AgentState

model_name = "BAAI/bge-m3"

class SingletonInstance:
    _instances = {}
    def __new__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cls._instances[cls]

def _merge_and_sort_results(form_results, legislation_results):
    combined = []
    for form in form_results:
        combined.append({
            "source_type": "form",
            "item_id": form["form_id"],
            "title": form["form_title"],
            "description": form.get("form_description", ""),
            "url": form["form_url"],
            "score": form["combined_score"],
            "details": form
        })
    for law in legislation_results:
        combined.append({
            "source_type": "legislation",
            "item_id": f"{law['act']}:{law['code']}",
            "title": f"{law['act']} - {law['code']}",
            "description": law["description"],
            "url": law["link"],
            "score": law["combined_score"],
            "details": law
        })
    return sorted(combined, key=lambda x: x["score"])


class RAGAgent(Runnable, SingletonInstance):
    def __init__(self, db_config: database.Config, rag_config: RAGConfig, embedding_model: SentenceTransformer, legalese_model: Optional[legislation.LegaleseTranslator] = None, verbose=False):
        self.db_config = db_config
        self.rag_config = rag_config
        self.db_init = False
        self.forms_db = forms.FormsDatabase(embedding_model, rag_config.forms_path)
        self.legislation_db = legislation.LegislationDatabase(embedding_model, legalese_model, rag_config.legislation_path)
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[📦 RAGAgent] {message}", flush=True)

    async def init_database(self):
        if not self.db_init:
            server_dsn = self.db_config.dsn
            database = self.db_config.database
            self._log(f"Connecting to server to check if database '{database}' exists...")
            conn = await asyncpg.connect(server_dsn, database=database)
            try:
                async with conn.transaction():
                    db_exists = await conn.fetchval('SELECT 1 FROM pg_database WHERE datname = $1', database)
                    if not db_exists:
                        self._log(f"Creating database '{database}'...")
                        await conn.execute(f'CREATE DATABASE {database}')
                        self._log(f"Database '{database}' created successfully.")
                    else:
                        self._log(f"Database '{database}' already exists.")
                    self._log("Setting up database schema...")
                    for schema_file in self.db_config.schema_dir.rglob("*.sql"):
                        self._log(f"Executing schema file: {schema_file}")
                        await conn.execute(helpers.read_file_to_string(schema_file))
                    self.db_init = True
            except Exception as e:
                self._log(f"❌ Error initializing database: {e}")
                raise e
            finally:
                await conn.close()

    @asynccontextmanager
    async def db_pool(self) -> AsyncGenerator[asyncpg.Pool, None]:
        server_dsn = self.db_config.dsn
        database = self.db_config.database
        self._log(f"🔌 Connecting to database '{database}'...")
        pool = await asyncpg.create_pool(f'{server_dsn}/{database}')
        try:
            yield pool
        finally:
            await pool.close()

    async def populate_database(self, clear: bool = True):
        self._log("🗄️ Populating the database with form and legislation data...")
        async with self.db_pool() as pool:
            if clear:
                await self.forms_db.clear(pool)
                await self.legislation_db.clear(pool)
            await self.forms_db.populate(pool)
            await self.legislation_db.populate(pool)
        self._log("✅ Database population complete.")





