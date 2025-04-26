import asyncio
from typing import Optional, Any, Dict

import asyncpg
from langchain_core.runnables import RunnableConfig, Runnable
from langgraph.constants import END
from transformers import pipeline

from ..config import database
from ..orchestration.state import AgentState


class SummaryAgent(Runnable):
    node = "SummaryAgent"
    def __init__(self, db_config: database.Config, model:pipeline, min_length:int=30, max_length:int=250,  verbose=False):
        self.db_config = db_config
        self.db_init = False
        self.model = model
        self.min_length = min_length,
        self.max_length = max_length,
        self.verbose = verbose

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
                        await conn.execute(schema_file.read_text())
                    self.db_init = True
            except Exception as e:
                self._log(f"❌ Error initializing database: {e}")
                raise e
            finally:
                await conn.close()
                

    def _log(self, message: str):
        if self.verbose:
            print(f"[📡 SummaryAgent] {message}", flush=True)

    def _format_conversation(self, question, response, verbose):
        if verbose:
            self._log("Formatting conversation")
        return f"USER: {question}\nAGENT: {response}"

    async def persist_conversation_summary(self, user:str, conversation:str)-> None:
        server_dsn = self.db_config.dsn
        database = self.db_config.database
        self._log("Connecting to database...")
        conn = await asyncpg.connect(server_dsn, database=database)
        self._log(f"Persisting conversation summary for {user}")
        try:
            await conn.execute(
                '''
                UPDATE users.userInfo
                SET summ_last_convo = $1
                WHERE email = $2
                ''',
                conversation,
                user
            )

        except Exception as e:
            self._log(f"❌ Error persisting summary of conversation into database: {e}")
            raise e
        finally:
            await conn.close()

    async def retrieve_conversation_summary(self, user:str)-> Optional[str]:
        server_dsn = self.db_config.dsn
        database = self.db_config.database
        self._log("Connecting to database...")
        conn = await asyncpg.connect(server_dsn, database=database)
        self._log(f"Retrieving latest conversation summary for {user}")
        try:
           summary = await conn.fetchval(
                '''
                SELECT summ_last_convo
                FROM users.userInfo
                WHERE email = $1
                ''',
                user
            )
        except Exception as e:
            self._log(f"❌ Error fetching latest summary of conversation: {e}")
            raise e
        finally:
            await conn.close()

        return summary

    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", self.verbose)
        response = state.get("initial_response")
        user = state.get("user")
        if response is None:
            results = asyncio.run(self.retrieve_conversation_summary(user))
            return {
                "last_conversation_summary": results
            }

        question = state.get("question")
        conversation = self._format_conversation(question,response,verbose)
        if verbose:
            self._log("Generating summary of conversation")
        conversation = self.model(conversation, max_length=16, min_length=10, do_sample=False)[0]['summary_text']
        results = asyncio.run(self.persist_conversation_summary(user,conversation))
        return {
            "last_conversation_summary": results,
            "generation_stage": "final"
        }

    def route_after_summary(self, state: AgentState) -> str:
        stage = state.get('generation_stage')
        if state.get("verbose", self.verbose):
            self._log(f"[Summary Routing]: {stage}")
        if stage == "final":
            return END
        return "RelevanceAgent"