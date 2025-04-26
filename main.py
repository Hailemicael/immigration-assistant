import asyncio

from sentence_transformers import SentenceTransformer
from transformers import pipeline

from Project.immigration_assistant.config import database
from Project.immigration_assistant.orchestration.conductor import RMAIA
from Project.immigration_assistant.rag.agent import RAGAgent
from Project.immigration_assistant.rag.config import RAGConfig
from Project.immigration_assistant.reasoning.agent import ReasoningAgent
from Project.immigration_assistant.relevance.agent import RelevanceAgent
from Project.immigration_assistant.summarization.agent import SummaryAgent
from Project.immigration_assistant.timeline.agent import TimelineAgent


async def main():
    print("Loading SentenceTransformer model...", flush=True)
    embedding_model = SentenceTransformer(RAGAgent.model_name)

    db_config = database.Config(
        dsn="postgresql://@localhost:5432",
        database="maia",
        pool_size=(10, 10)
    )
    summary_agent = SummaryAgent(
        db_config=db_config.copy("../user-registration/sql"),
        model = pipeline("summarization", model="facebook/bart-large-cnn"),
        verbose=True
    )
    relevance_agent = RelevanceAgent(
        model=embedding_model,
        baseline_path="../rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json",
        relevance_threshold=0.65,
        verbose=True
    )

    reasoning_agent = ReasoningAgent(
        endpoint_url="https://apc68c0a4ml2min4.us-east-1.aws.endpoints.huggingface.cloud",
        api_token=
        verbose=True
    )

    rag_agent = RAGAgent(
        db_config=db_config.copy(schema_dir="../rag/sql"),
        rag_config=RAGConfig(
            forms_path="../rag/uscis-crawler/documents/forms",
            legislation_path="../rag/uscis-crawler/documents/legislation",
        ),
        embedding_model=embedding_model,
        verbose=True
    )

    timeline_agent = TimelineAgent(
        verbose=True
    )

    system = RMAIA(
        user="bob@test.com",
        summary_agent=summary_agent,
        relevance_agent=relevance_agent,
        reasoning_agent=reasoning_agent,
        rag_agent=rag_agent,
        timeline_agent=timeline_agent,
        verbose=True)

    question = "My home nation is a war zone and i would like to escape to the US, what do i need to do?"
    # question = "I need to sleep"
    result = await system.ainvoke(question)

    print("\n--- Final Result ---", flush=True)
    print(result.get('history'))
    print(f"Relevance: {result.get('relevance')}", flush=True)
    print(f"Final Response:\n{result.get('initial_response')}", flush=True)
    print(f"Legislation: {result.get('legislation', [])}", flush=True)
    print(f"Forms: {result.get('forms', [])}", flush=True)
    print(f"Timeline: {result.get('timeline', [])}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())