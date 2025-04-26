import json
from typing import Dict, Optional, Any
from contextlib import asynccontextmanager
import asyncio
import asyncpg
from pathlib import Path

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END

from ..config import database


class TimelineAgent(Runnable):
    def __init__(self, db_config: database.Config = None, verbose:bool = False):
        self.verbose = verbose
        self.db_config = db_config
        self.db_init = False
    
    def _log(self, message: str):
        if self.verbose:
            print(f"[📆 TimelineAgent] {message}", flush=True)

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

    @asynccontextmanager
    async def db_pool(self):
        """Create a connection pool to the database"""
        server_dsn = self.db_config.dsn
        database = self.db_config.database

        self._log(f"🔌 Connecting to database '{database}'...")
        pool = await asyncpg.create_pool(f'{server_dsn}/{database}')

        try:
            yield pool
        finally:
            await pool.close()
    
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        """Synchronous wrapper for async invoke method"""
        return asyncio.run(self._invoke(state, config, **kwargs))

    async def _invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        """Process forms and generate timeline information"""
        verbose = state.get("verbose", self.verbose)
        if verbose:
            self._log(f"Processing forms: {state.get('forms', [])}")
        
        if not state.get("forms"):
            if verbose:
                self._log("No forms found, skipping")
            return {}
        
        timeline_info = [f"{form}: 3–6 months processing" for form in state.get("forms", [])]
        
        if verbose:
            self._log(f"Generated timeline info: {timeline_info}")
        
        # Update history
        history = state.get("history", [])
        history.append({
            "agent": "TimelineAgent",
            "generated_timelines": len(timeline_info)
        })
        
        # Save to database if connection is available
        if self.db_config and self.db_init:
            try:
                async with self.db_pool() as pool:
                    async with pool.acquire() as conn:
                        # Get history entry
                        history_entry = history[-1]
                        generated_timelines = history_entry.get("generated_timelines", 0)

                        # Use the database function to save the timeline data
                        await conn.execute(
                            """
                            SELECT timeline.save_agent_timeline(
                                $1,  -- agent_name_param
                                $2,  -- generated_items_param
                                $3,  -- state_data_param
                                $4   -- timeline_entries_param
                            )
                            """,
                            "TimelineAgent", 
                            generated_timelines,
                            json.dumps(state),
                            json.dumps(timeline_info)
                        )

                        if verbose:
                            self._log("Successfully saved data to database")
            except Exception as e:
                self._log(f"❌ Database save failed: {str(e)}")
        
        return {
            "timeline": timeline_info,
            "history": history
        }
    
    def route_after_timeline(self, state: Dict) -> str:
        """Determine the next step after timeline generation"""
        if state.get("verbose", self.verbose):
            print(f"[📆 Timeline Routing] → Summary Stage: {state.get('generation_stage')}")
        return "SummaryAgent"
        # return "ReasoningAgent" if state.get("generation_stage") == "initial" else END
async def main():
    # Database configuration
    config = database.Config(
        schema_dir = "./sql",
        dsn = "postgresql://@localhost:5432",
        database= "maia",
        pool_size = (10, 10)
    )
    agent = TimelineAgent(db_config=config)
    await agent.init_database()

if __name__ == "__main__":
    asyncio.run(main())
