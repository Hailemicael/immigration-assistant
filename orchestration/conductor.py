import asyncio
from typing import Dict
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph
from sentence_transformers import SentenceTransformer
from transformers import pipeline

from ..rag.config import RAGConfig
from ..config import database
from ..orchestration.state import AgentState
from ..reasoning.agent import ReasoningAgent
from ..summarization.agent import SummaryAgent
from ..timeline.agent import TimelineAgent
from ..rag.agent import RAGAgent
from ..relevance.agent import RelevanceAgent
from ..translator.agent import TranslatorAgent


class RMAIA:
    def __init__(
            self,
            user: str,
            translator_agent: TranslatorAgent,
            summary_agent: SummaryAgent,
            relevance_agent: RelevanceAgent,
            reasoning_agent: ReasoningAgent,
            rag_agent: RAGAgent,
            timeline_agent: TimelineAgent,
            verbose: bool = False,
            system_name: str = "Immigration Law Assistant"
    ):
        self.user = user
        self.translator_agent = translator_agent
        self.summary_agent = summary_agent
        self.relevance_agent = relevance_agent
        self.reasoning_agent = reasoning_agent
        self.rag_agent = rag_agent
        self.timeline_agent = timeline_agent
        self.model_name = RAGAgent.model_name
        self.verbose = verbose
        self.system_name = system_name
        self.llm = OllamaLLM(model=RAGAgent.model_name)
        self.graph = None
        self._build_graph()

    def _log(self, message: str):
        if self.verbose:
            print(f"[🧠 R-MAIA] {message}", flush=True)

    def _build_graph(self):
        self._log("🔧 Building agent graph...")
        builder = StateGraph(AgentState)
        builder.add_node(TranslatorAgent.node, self.translator_agent)
        builder.add_node(SummaryAgent.node, self.summary_agent)
        builder.add_node(RelevanceAgent.node, self.relevance_agent)
        builder.add_node(ReasoningAgent.node, self.reasoning_agent)
        builder.add_node(RAGAgent.node, self.rag_agent)
        builder.add_node("TimelineAgent", self.timeline_agent)

        builder.set_entry_point(SummaryAgent.node)
        builder.add_conditional_edges(SummaryAgent.node, self.summary_agent.route_after_summary)
        builder.add_conditional_edges(TranslatorAgent.node, self.translator_agent.check_translation_needed)
        builder.add_conditional_edges(RelevanceAgent.node, self.relevance_agent.check_relevance)
        builder.add_conditional_edges(ReasoningAgent.node, self.reasoning_agent.check_stage_for_rag)
        builder.add_conditional_edges(RAGAgent.node, self.rag_agent.check_forms)
        builder.add_conditional_edges("TimelineAgent", self.timeline_agent.route_after_timeline)
        self.graph = builder.compile()
        self._log("✅ Graph compiled successfully.")

    async def ainvoke(self, question: str, verbose: bool = None) -> Dict:
        if verbose is None:
            verbose = self.verbose
        self._log(f"💬 Processing question: \"{question}\"")

        initial_state = AgentState(
            user=self.user,
            question= question,
            relevance= "unknown",
            generation_stage= "initial",
            initial_response= None,
            legislation= [],
            forms= [],
            timeline= [],
            final_response= None,
            verbose= verbose,
            history= [],
            last_conversation_summary=None
        )

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
    translator_agent = TranslatorAgent(verbose=True)

    relevance_agent = RelevanceAgent(
        model=embedding_model,
        baseline_path="../rag/uscis-crawler/documents/frequently-asked-questions/immigration_faqs.json",
        relevance_threshold=0.65,
        verbose=True
    )

    reasoning_agent = ReasoningAgent(
        endpoint_url="https://apc68c0a4ml2min4.us-east-1.aws.endpoints.huggingface.cloud",
        api_token="",
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
        translator_agent=translator_agent,
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


# if __name__ == "__main__":
#     asyncio.run(main())
