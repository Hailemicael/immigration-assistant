import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Tuple, AsyncGenerator, Optional
import asyncio
import asyncpg
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END
from sentence_transformers import SentenceTransformer

from Project.immigration_assistant.summarization.agent import SummaryAgent
from Project.immigration_assistant.util import read_file_to_string
from Project.immigration_assistant.rag import forms
from Project.immigration_assistant.rag import legislation
from Project.immigration_assistant.rag.config import RAGConfig
from Project.immigration_assistant.config import database
from Project.immigration_assistant.rag.query_results import QueryResult
from Project.immigration_assistant.orchestration.state import AgentState

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
    model_name = "BAAI/bge-m3"
    node = "RAGAgent"
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
                        await conn.execute(read_file_to_string(schema_file))
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
        async with self.db_pool() as pool:
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
    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        results = asyncio.run(self._invoke(state, config, **kwargs))
        return results

    async def _invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", self.verbose)
        question = state.get("initial_response", "")
        if verbose:
            self._log(f"\n💬 Received query: \"{question}\"")
        results = await self.query(question)
        if verbose:
            self._log(f"📘 Found {len(results.legislation)} legislation matches.")
            self._log(f"📄 Found {len(results.forms)} form matches.")
        history = state.get("history", [])
        history.append({
            "agent": RAGAgent.node,
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
        return SummaryAgent.node

# Example usage
async def main():
    # Database configuration
    db_config = database.Config(
        schema_dir = "./sql",
        dsn = "postgresql://@localhost:5432",
        database= "maia",
        pool_size = (10, 10)
    )


    # Load the embedding model (SentenceTransformer)
    print("Loading SentenceTransformer model...")
    embedding_model = SentenceTransformer(RAGAgent.model_name)

    # RAG configuration
    rag_config =  RAGConfig(
        forms_path = "./uscis-crawler/documents/forms",
        legislation_path = "./uscis-crawler/documents/legislation",
        chunk_size = 1024, # Chunk size for content ingestion
        # input_embedding_prefix = "search_document:",
        # query_embedding_prefix = "search_query:"

    )

    print("Loading Translation model...")
    legalese_model = legislation.LegaleseTranslator("aiguy68/Super_legal_text_summarizer",disabled=True)

    # Initialize the RAGAgent
    rag_agent = RAGAgent(db_config, rag_config, embedding_model, legalese_model, verbose=True)

    # # Initialize database connection
    await rag_agent.init_database()

    # Populate the database
    await rag_agent.populate_database(clear=False)
    prompt = '''The new H-1B visa rules are outlined in USCIS’s Notice of Proposed Rulemaking (NPRM) published on August 11, 2021. The new rule changes include:

Requiring employers to register with the Office of Sponsorship of International Workers (OSI) in advance of the filing of an application for H-1B visas.

Eliminating the ability of the employer to request a waiver of the registration requirement.

Requiring the employer to provide evidence of a bona fide need for the foreign worker, including evidence that the foreign worker has met the eligibility requirements of the rule.

Requiring the employer to disclose information on the foreign worker’s salary and benefits.

The USCIS will consider the evidence provided by the employer, including the salary and benefits, in evaluating whether the employer’s bona fide need for the foreign worker is sufficient to demonstrate that the foreign worker will contribute to the economic development of the U.S. as a permanent resident.

The new H-1B visa rules will go into effect on October 22, 2021.

Question: What are the requirements for filing an application for H-1B visas?

Answer: Form I-129, Application for Permanent Resident Status, must be filed online, using the USCIS website or the USCIS online application form. If you filed the application online, you must print the form and submit it in person to the USCIS office where you filed your application. You can use the USCIS website or the USCIS online application form to file the application. The Form I-129 must be filed online, with the appropriate fee. You can find the appropriate fee for filing the Form I-129 online at https://www.uscis.gov/forms/filing-immigration-documents/forms/form-129. You must submit the Form I-129, with the appropriate fee, in person to the USCIS office where you filed your application. You may also submit the Form I-129, with the appropriate fee, in the mail. However, the USCIS does not accept online submissions of forms. You may request an alternative method of submission by contacting the office where you filed your application. We strongly recommend that you submit the Form I-129, with the appropriate fee, in person to the USCIS office where you filed your application. We also strongly recommend that you submit the Form I-129'''
    results = await rag_agent.query(prompt, verbose=True)
    print(json.dumps(results.forms, indent=4))
    # faq_path = Path("./uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json")
    # with open(faq_path, 'r') as file:
    #     data = json.load(file)
    #     res = {
    #         "total": 0,
    #         "question": {
    #             "misses": 0,
    #             "forms": {
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #             "legislation":{
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #         },
    #         "answer": {
    #             "misses": 0,
    #             "forms": {
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #             "legislation":{
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #         },
    #         "question | answer": {
    #             "misses": 0,
    #             "forms": {
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #             "legislation":{
    #                 "misses": 0,
    #                 "count": 0,
    #                 "similarity_score": 0
    #             },
    #         },
    #     }
    #     for i , item in enumerate(data):
    #         res["total"]+= 1
    #         # Query the database
    #         # query_string = "How much does it cost for a green card?"
    #         query = f'''question: {item["question"]} | answer: {item["answer"]}'''
    #         results = await rag_agent.query(query, top_k=3)
    #
    #         form_count = len(results.forms)
    #         if form_count == 0 :
    #             res["question | answer"]["forms"]["misses"] += 1
    #
    #         law_count = len(results.legislation)
    #         if law_count == 0 :
    #             res["question | answer"]["legislation"]["misses"] += 1
    #
    #         if law_count == 0 and form_count == 0 :
    #             res["question | answer"]["misses"] += 1
    #
    #         res["question | answer"]["forms"]["count"] += form_count
    #         res["question | answer"]["legislation"]["count"] += law_count
    #         res["question | answer"]["forms"]["similarity_score"] += np.sum([form["similarity_score"] for form in results.forms])
    #         res["question | answer"]["legislation"]["similarity_score"] += np.sum([law["chunk_similarity"] for law in results.legislation])
    #         if i == 0 :
    #             print(json.dumps(results, indent=2))
    #
    #         results = await rag_agent.query(item["question"], top_k=3)
    #         form_count = len(results.forms)
    #         if form_count == 0 :
    #             res["question"]["forms"]["misses"] += 1
    #
    #         law_count = len(results.legislation)
    #         if law_count == 0 :
    #             res["question"]["legislation"]["misses"] += 1
    #
    #         if law_count == 0 and form_count == 0 :
    #             res["question"]["misses"] += 1
    #
    #         res["question"]["forms"]["count"] += form_count
    #         res["question"]["legislation"]["count"] += law_count
    #         res["question"]["forms"]["similarity_score"] += np.sum([form["similarity_score"] for form in results.forms])
    #         res["question"]["legislation"]["similarity_score"] += np.sum([law["chunk_similarity"] for law in results.legislation])
    #         if i == 0 :
    #             print(json.dumps(results, indent=2))
    #
    #         results = await rag_agent.query(item["answer"], top_k=3)
    #         form_count = len(results.forms)
    #         if form_count == 0 :
    #             res["answer"]["forms"]["misses"] += 1
    #
    #         law_count = len(results.legislation)
    #         if law_count == 0 :
    #             res["answer"]["legislation"]["misses"] += 1
    #
    #         if law_count == 0 and form_count == 0 :
    #             res["answer"]["misses"] += 1
    #
    #         res["answer"]["forms"]["count"] += form_count
    #         res["answer"]["legislation"]["count"] += law_count
    #         res["answer"]["forms"]["similarity_score"] += np.sum([form["similarity_score"] for form in results.forms])
    #         res["answer"]["legislation"]["similarity_score"] += np.sum([law["chunk_similarity"] for law in results.legislation])
    #         if i == 0 :
    #             print(json.dumps(results, indent=2))
    #
    #     for group in ["question", "answer", "question | answer"]:
    #         for source in ["forms", "legislation"]:
    #             count = res[group][source]["count"]
    #             total_score = res[group][source]["similarity_score"]
    #             avg_key = "avg_similarity_score"
    #             if count > 0:
    #                 res[group][source][avg_key] = total_score / count
    #             else:
    #                 res[group][source][avg_key] = 0
    #     print(json.dumps(res, indent=2))




# Run the main function
if __name__ == "__main__":
    asyncio.run(main())