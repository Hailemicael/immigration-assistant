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
        self.db_init = False
        self.forms_db =  forms.FormsDatabase(embedding_model, rag_config.forms_path)
        self.legislation_db = legislation.LegislationDatabase(embedding_model, rag_config.legislation_path)


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
                    for schema_file in self.db_config.schema_dir.rglob("*.sql"):
                        print(f"Executing {schema_file}...")
                        await conn.execute(helpers.read_file_to_string(schema_file))
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




    async def populate_database(self, clear: bool = True):
        """
        Populate the database with forms and legislation data.
        """
        print("Populating the database...")
        async with self.db_pool() as pool:
            if clear:
                await self.forms_db.clear(pool)
                await self.legislation_db.clear(pool)
            # Populate forms
            await self.forms_db.populate(pool)
            # Populate legislation
            await self.legislation_db.populate(pool)
        print("Database population complete.")

    async def query(self, query_text: str, top_k: int = 5, verbose: bool = False) -> dict:
        """
        Query the database using the embedding model to find relevant forms and legislation.
        Combines results from both sources into a unified result set.

        Args:
            query_text: The input query string.
            top_k: Number of top results to retrieve per source.
            verbose:

        Returns:
            Dictionary containing combined results from forms and legislation.
        """
        async with self.db_pool() as pool:
            # Run both searches in parallel for efficiency
            form_task = asyncio.create_task(
                self.forms_db.search(pool, query_text, top_k, verbose)
            )

            legislation_task = asyncio.create_task(
                self.legislation_db.search(pool, query_text, top_k, verbose)
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
            }

            return combined_results


# Example usage
async def main():
    # Database configuration
    db_config = DBConfig(
        schema_dir = "./sql",
        dsn = "postgresql://@localhost:5432",
        database= "maia",
        pool_size = (10, 10)
    )


    # Load the embedding model (SentenceTransformer)
    print("Loading SentenceTransformer model...")
    embedding_model = SentenceTransformer("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")
    # embedding_model = SentenceTransformer("nomic-ai/nomic-embed-text-v1", trust_remote_code=True)

    # RAG configuration
    rag_config =  Config(
        forms_path = "./uscis-crawler/documents/forms",
        legislation_path = "./uscis-crawler/documents/legislation",
        chunk_size = 1024, # Chunk size for content ingestion
        # input_embedding_prefix = "search_document:",
        # query_embedding_prefix = "search_query:"

    )
    # Initialize the RAGAgent
    rag_agent = RAGAgent(db_config, rag_config, embedding_model)

    # Initialize database connection
    # await rag_agent.init_database()
    #
    # # Populate the database
    #
    # await rag_agent.populate_database(clear=True)

    faq_path = Path("./uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json")
    with open(faq_path, 'r') as file:
        data = json.load(file)
        res = {
            "total": 0,
            "question": {
                "forms": 0,
                "legislation": 0
            },
            "answer": {
                "forms": 0,
                "legislation": 0
            },
            "question | answer": {
                "forms": 0,
                "legislation": 0
            },
        }
        for item in data:
            res["total"]+= 1
            # Query the database
            # query_string = "How much does it cost for a green card?"
            query = f'''question: {item["question"]} | answer: {item["answer"]}'''
            results = await rag_agent.query(query, top_k=3)
            res["question | answer"]["forms"] += len(results["sources"]["forms"])
            res["question | answer"]["legislation"] += len(results["sources"]["legislation"])

            results = await rag_agent.query(item["question"], top_k=3)
            res["question"]["forms"] += len(results["sources"]["forms"])
            res["question"]["legislation"] += len(results["sources"]["legislation"])

            results = await rag_agent.query(item["answer"], top_k=3)
            res["answer"]["forms"] += len(results["sources"]["forms"])
            res["answer"]["legislation"] += len(results["sources"]["legislation"])

        print(res)




# Run the main function
if __name__ == "__main__":
    asyncio.run(main())
