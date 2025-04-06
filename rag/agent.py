import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Tuple, AsyncGenerator
import asyncio
import asyncpg
from sentence_transformers import SentenceTransformer

import helpers
import forms
import legislation

class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class Config:
    def __init__(self, forms_path: str, legislation_path: str, chunk_size: int = 512):
        self.forms_path = Path(forms_path)
        self.legislation_path = Path(legislation_path)
        self.chunk_size = chunk_size

class DBConfig:
    def __init__(self, dsn: str = "postgresql://@localhost:5432", database: str = "maia", pool_size: Tuple[int, int] = (1, 10) ):
        self.dsn = dsn
        self.database = database
        self.min_pool_size = pool_size[0]
        self.max_pool_size = pool_size[1]


def _merge_and_sort_results(form_results, legislation_results):
    """
    Merge and sort results from forms and legislation sources.

    Args:
        form_results: List of form objects with combined_score.
        legislation_results: List of legislation objects with combined_score.

    Returns:
        List of combined results, sorted by relevance score.
    """
    # Prepare combined list
    combined = []

    # Add form results with source type
    for form in form_results:
        combined.append({
            "source_type": "form",
            "item_id": form["form_id"],
            "title": form["form_title"],
            "description": form.get("form_description", ""),
            "url": form["form_url"],
            "score": form["combined_score"],
            "details": form  # Include all original data
        })

    # Add legislation results with source type
    for law in legislation_results:
        combined.append({
            "source_type": "legislation",
            "item_id": f"{law['act']}:{law['code']}",
            "title": f"{law['act']} - {law['code']}",
            "description": law["description"],
            "url": law["link"],
            "score": law["combined_score"],
            "details": law  # Include all original data
        })

    # Sort by score (lower is better with the cosine distance)
    return sorted(combined, key=lambda x: x["score"])


class RAGAgent(metaclass=Singleton):
    def __init__(
            self,
            db_config: DBConfig,
            rag_config: Config,
            embedding_model: SentenceTransformer,
    ):
        """
        Initialize the RAG agent with configurations and an embedding model.
        :param db_config: Configuration object for the database (e.g., DSN, pool size).
        :param rag_config: Configuration object for RAG process (e.g., chunk size).
        :param embedding_model: Preloaded embedding model for use in similarity search.
        """
        self.db_config = db_config
        self.rag_config = rag_config
        self.embedding_model = embedding_model
        self.db_init = False


    async def init_database(self):
        """
        Initialize the database connection pool using the configuration.
        """
        if not self.db_init:
            server_dsn = self.db_config.dsn
            database = self.db_config.database
            print(f"Connecting to server to check if database {database} exists...")
            conn = await asyncpg.connect(server_dsn, database=database)
            try:
                async with conn.transaction():
                    db_exists = await conn.fetchval(
                        'SELECT 1 FROM pg_database WHERE datname = $1', database
                    )
                    if not db_exists:
                        print(f"Creating database {database}...")
                        await conn.execute(f'CREATE DATABASE {database}')
                        print(f"Database {database} created successfully.")
                    else:
                        print(f"Database {database} already exists.")

                    print("Setting up database schema...")
                    await conn.execute(helpers.read_file_to_string("sql/forms-db-init.sql"))
                    self.db_init = True
            except Exception as e:
                print(f"Error initializing database: {e}")
                raise e
            finally:
                await conn.close()
            return

    @asynccontextmanager
    async def db_pool(self) -> AsyncGenerator[asyncpg.Pool, None]:
        server_dsn = self.db_config.dsn
        database = self.db_config.database
        print(f"Connecting to database {database}...")
        pool = await asyncpg.create_pool(f'{server_dsn}/{database}')
        try:
            yield pool
        finally:
            await pool.close()




    async def populate_database(self):
        """
        Populate the database with forms and legislation data.
        """
        print("Populating the database...")
        async with self.db_pool() as pool:
            # Populate forms
            await forms.populate_db(self.embedding_model, pool, self.rag_config.forms_path)
            # Populate legislation
            await legislation.populate_db(self.embedding_model, pool, self.rag_config.legislation_path)
        print("Database population complete.")

    async def query(self, query_text: str, top_k: int = 5) -> dict:
        """
        Query the database using the embedding model to find relevant forms and legislation.
        Combines results from both sources into a unified result set.

        Args:
            query_text: The input query string.
            top_k: Number of top results to retrieve per source.

        Returns:
            Dictionary containing combined results from forms and legislation.
        """
        async with self.db_pool() as pool:
            # Run both searches in parallel for efficiency
            form_task = asyncio.create_task(
                forms.search(self.embedding_model, pool, query_text, top_k)
            )

            legislation_task = asyncio.create_task(
                legislation.search(self.embedding_model, pool, query_text, top_k)
            )

            # Wait for both searches to complete
            form_results, legislation_results = await asyncio.gather(form_task, legislation_task)

            # Combine the results
            combined_results = {
                "query": query_text,
                "sources": {
                    "forms": form_results,
                    "legislation": legislation_results
                },
                # Create a unified list of results, sorted by combined_score
                "combined_results": _merge_and_sort_results(form_results, legislation_results)
            }

            return combined_results


# Example usage
async def main():
    # Database configuration
    db_config = DBConfig(
        dsn = "postgresql://@localhost:5432",
        database= "maia",
        pool_size = (10, 10)
    )


    # RAG configuration
    rag_config =  Config(
        forms_path = "./uscis-crawler/documents/forms",
        legislation_path = "./uscis-crawler/documents/legislation",
        chunk_size = 512  # Chunk size for content ingestion
    )

    # Load the embedding model (SentenceTransformer)
    print("Loading SentenceTransformer model...")
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    # Initialize the RAGAgent
    rag_agent = RAGAgent(db_config, rag_config, embedding_model)

    # # Initialize database connection
    # await rag_agent.init_database()
    #
    # # Populate the database
    #
    # await rag_agent.populate_database()

    # Query the database
    query_string = "what is the replacement fee for Form I-765?"
    results = await rag_agent.query(query_string, top_k=3)
    print("Query Results:", json.dumps(results, indent=4))


# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
