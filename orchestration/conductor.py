import asyncio
from typing import Dict
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph
from sentence_transformers import SentenceTransformer

from Project.immigration_assistant.rag.config import RAGConfig
from Project.immigration_assistant.config import database
from Project.immigration_assistant.orchestration.state import AgentState
from Project.immigration_assistant.reasoning.agent import ReasoningAgent
from Project.immigration_assistant.timeline.agent import TimelineAgent
from Project.immigration_assistant.rag.agent import RAGAgent, model_name
from Project.immigration_assistant.relevance.agent import RelevanceAgent


class RMAIA:
    def __init__(
            self,
            relevance_agent: RelevanceAgent,
            reasoning_agent: ReasoningAgent,
            rag_agent: RAGAgent,
            timeline_agent: TimelineAgent,
            verbose: bool = False,
            system_name: str = "Immigration Law Assistant"
    ):
        self.relevance_agent = relevance_agent
        self.reasoning_agent = reasoning_agent
        self.rag_agent = rag_agent
        self.timeline_agent = timeline_agent
        self.model_name = model_name
        self.verbose = verbose
        self.system_name = system_name
        self.llm = OllamaLLM(model=model_name)
        self.graph = None
        self._build_graph()

    def _log(self, message: str):
        if self.verbose:
            print(f"[🧠 R-MAIA] {message}", flush=True)

    def _build_graph(self):
        self._log("🔧 Building agent graph...")
        builder = StateGraph(AgentState)
        builder.add_node("RelevanceAgent", self.relevance_agent)
        builder.add_node("ReasoningAgent", self.reasoning_agent)
        builder.add_node("RAGAgent", self.rag_agent)
        builder.add_node("TimelineAgent", self.timeline_agent)
        builder.set_entry_point("RelevanceAgent")
        builder.add_conditional_edges("RelevanceAgent", self.relevance_agent.check_relevance)
        builder.add_conditional_edges("ReasoningAgent", self.reasoning_agent.check_stage_for_rag)
        builder.add_conditional_edges("RAGAgent", self.rag_agent.check_forms)
        builder.add_conditional_edges("TimelineAgent", self.timeline_agent.route_after_timeline)
        self.graph = builder.compile()
        self._log("✅ Graph compiled successfully.")

    async def ainvoke(self, question: str, verbose: bool = None) -> Dict:
        if verbose is None:
            verbose = self.verbose
        self._log(f"💬 Processing question: \"{question}\"")

        initial_state = {
            "question": question,
            "relevance": "unknown",
            "generation_stage": "initial",
            "initial_response": None,
            "legislation": [],
            "forms": [],
            "timeline": [],
            "final_response": None,
            "verbose": verbose,
            "history": []
        }

        try:
            result = await self.graph.ainvoke(initial_state)
            self._log("✅ Processing complete.")
            return result
        except Exception as e:
            self._log(f"❌ Error during processing: {str(e)}")
            raise

    @staticmethod
    def get_response_summary(result: Dict) -> Dict:
        return {
            "success": True,
            "relevance": result.get("relevance"),
            "final_response": result.get("final_response"),
            "legislation": result.get("legislation", []),
            "forms": result.get("forms", []),
            "timeline": result.get("timeline", [])
        }


async def main():
    print("Loading SentenceTransformer model...", flush=True)
    embedding_model = SentenceTransformer(model_name)

    db_config = database.Config(
        dsn="postgresql://@localhost:5432",
        database="maia",
        pool_size=(10, 10)
    )

    relevance_agent = RelevanceAgent(
        model=embedding_model,
        baseline_path="../rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json",
        relevance_threshold=0.65
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
        llm=OllamaLLM(model="llama3"),
        verbose=True
    )

    system = RMAIA(relevance_agent, reasoning_agent, rag_agent, timeline_agent, verbose=True)
    question = "My home nation is a war zone and i would like to escape to the US, what do i need to do?"
    # question = "I need to sleep"
    result = await system.ainvoke(question)

    print("\n--- Final Result ---", flush=True)
    print(f"Relevance: {result.get('relevance')}", flush=True)
    print(f"Final Response:\n{result.get('initial_response')}", flush=True)
    print(f"Legislation: {result.get('legislation', [])}", flush=True)
    print(f"Forms: {result.get('forms', [])}", flush=True)
    print(f"Timeline: {result.get('timeline', [])}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
