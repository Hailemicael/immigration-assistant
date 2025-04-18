import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Tuple, AsyncGenerator, Optional
import asyncio
import asyncpg
from langchain_core.runnables import Runnable, RunnableConfig
from sentence_transformers import SentenceTransformer

import helpers
import forms
import legislation
from query_results import QueryResult
from ..orchestration.state import AgentState


class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config:
    def __init__(self, forms_path: str, legislation_path: str, chunk_size: int = 512, input_embedding_prefix: str = "None", query_embedding_prefix: str = "None"):
        self.forms_path = Path(forms_path)
        self.legislation_path = Path(legislation_path)
        self.chunk_size = chunk_size
        self.input_embedding_prefix = input_embedding_prefix
        self.query_embedding_prefix = query_embedding_prefix


class DBConfig:
    def __init__(self, schema_dir: str, dsn: str = "postgresql://@localhost:5432", database: str = "maia", pool_size: Tuple[int, int] = (1, 10) ):
        self.schema_dir = Path(schema_dir)
        self.dsn = dsn
        self.database = database
        self.min_pool_size = pool_size[0]
        self.max_pool_size = pool_size[1]


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


class RAGAgent(Runnable, metaclass=Singleton):
    def __init__(self, db_config: DBConfig, rag_config: Config, embedding_model: SentenceTransformer, legalese_model: legislation.LegaleseTranslator):
        self.db_config = db_config
        self.rag_config = rag_config
        self.db_init = False
        self.forms_db =  forms.FormsDatabase(embedding_model, rag_config.forms_path)
        self.legislation_db = legislation.LegislationDatabase(embedding_model, legalese_model, rag_config.legislation_path)

    def _log(self, message: str):
        if hasattr(self, "verbose") and self.verbose:
            print(f"[📦 RAGAgent] {message}")

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

    async def query(self, query_text: str, top_k: int = 5, verbose: bool = False) -> QueryResult:
        self.verbose = verbose
        async with (self.db_pool() as pool):
            form_task = asyncio.create_task(
                self.forms_db.search(pool, query_text, top_k, verbose)
            )
            legislation_task = asyncio.create_task(
                self.legislation_db.search(pool, query_text, top_k, verbose)
            )
            form_results, legislation_results = await asyncio.gather(form_task, legislation_task)
            return QueryResult(
                query=query_text,
                forms=form_results,
                legislation=legislation_results
            )

    async def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", False)
        question = state.get("question", "")
        if verbose:
            self._log(f"\n💬 Received query: \"{question}\"")
        results = await self.query(question)
        if verbose:
            self._log(f"📘 Found {len(results.legislation)} legislation matches.")
            self._log(f"📄 Found {len(results.forms)} form matches.")
        history = state.get("history", [])
        history.append({
            "agent": "RAGAgent",
            "found_legislation": len(results.legislation) > 0,
            "found_forms": len(results.forms) > 0
        })
        return {
            "legislation": results.legislation,
            "forms": results.forms,
            "history": history
        }

    def check_forms(self, state: AgentState) -> str:
        if state.get("verbose", self.verbose):
            self._log(f"📄 Form Check → Forms Found: {len(state.get('forms', []))}")
        if state.get("forms") and state.get("generation_stage") == "initial":
            return "TimelineAgent"
        return "ReasoningAgent"
