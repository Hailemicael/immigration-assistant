from typing import Dict
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph, END

from ..orchestration.state import AgentState
from ..reasoning.agent import ReasoningAgent
from ..timeline.agent import TimelineAgent
from ..rag.agent import RAGAgent
from ..relevance.agent import RelevanceAgent


class RMAIA:
    """
    R-MAIA: RAG-MultiAgent Immigration Assistant

    An orchestration system for LangGraph agents that integrates:
    - RAG: Retrieval-Augmented Generation for accessing relevant immigration information
    - MultiAgent: Coordination of specialized agents working together (Relevance, Reasoning, RAG, Timeline)
    - Immigration Assistant: Domain-specific focus on immigration law and policy

    This system enhances responses with relevant legislation, forms, and timelines by coordinating
    multiple agents that each handle a specific part of the information processing pipeline.
    """

    def __init__(
            self,
            relevance_agent: RelevanceAgent,
            reasoning_agent: ReasoningAgent,
            rag_agent: RAGAgent,
            timeline_agent: TimelineAgent,
            model_name: str = "mistral",
            verbose: bool = False,
            system_name: str = "Immigration Law Assistant"
    ):
        """Initialize the R-MAIA system with configuration options."""
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
        """Internal logging helper that respects verbose setting."""
        if self.verbose:
            print(f"[🧠 R-MAIA] {message}")

    def _build_graph(self):
        """Construct the LangGraph structure with nodes and edges."""
        self._log("🔧 Building agent graph...")

        builder = StateGraph(AgentState)

        # Add nodes
        builder.add_node("RelevanceAgent", self.relevance_agent)
        builder.add_node("ReasoningAgent", self.reasoning_agent)
        builder.add_node("RAGAgent", self.rag_agent)
        builder.add_node("TimelineAgent", self.timeline_agent)

        # Entry point
        builder.set_entry_point("RelevanceAgent")

        #Relevance check
        builder.add_conditional_edges("RelevanceAgent", self.relevance_agent.check_relevance)

        # Reasoning → RAG
        builder.add_conditional_edges("ReasoningAgent", self.reasoning_agent.check_stage_for_rag)

        # RAG → Timeline or Reasoning
        builder.add_conditional_edges("RAGAgent", self.rag_agent.check_forms)

        # Timeline → Reasoning
        builder.add_conditional_edges("TimelineAgent", self.timeline_agent.route_after_timeline)

        # Compile graph
        self.graph = builder.compile()
        self._log("✅ Graph compiled successfully.")

    def invoke(self, question: str, verbose: bool = None) -> Dict:
        """
        Process a question through the R-MAIA system.

        Args:
            question: The input question to process
            verbose: Override the system's verbose setting for this invocation

        Returns:
            Dict containing the full state after processing
        """
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
            result = self.graph.invoke(initial_state)
            self._log("✅ Processing complete.")
            return result
        except Exception as e:
            self._log(f"❌ Error during processing: {str(e)}")
            raise

    @staticmethod
    def get_response_summary(result: Dict) -> Dict:
        """
        Generate a clean summary of the system's response.

        Args:
            result: The full state returned from invoke()

        Returns:
            Dict with key response components
        """
        return {
            "success": True,
            "relevance": result.get("relevance"),
            "final_response": result.get("final_response"),
            "legislation": result.get("legislation", []),
            "forms": result.get("forms", []),
            "timeline": result.get("timeline", [])
        }


# Example usage
if __name__ == "__main__":
    # You would normally inject the agents here
    # system = RMAIA(relevance_agent, reasoning_agent, rag_agent, timeline_agent, verbose=True)

    # question = "Can you explain the new H-1B visa rules under the 2024 immigration policy changes?"
    # result = system.invoke(question)

    # print("\n--- Final Result ---")
    # print(f"Relevance: {result.get('relevance')}")
    # print(f"Final Response:\n{result.get('final_response')}")
    # print(f"Legislation: {result.get('legislation', [])}")
    # print(f"Forms: {result.get('forms', [])}")
    # print(f"Timeline: {result.get('timeline', [])}")
    pass
