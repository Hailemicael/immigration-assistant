import json
from typing import Dict, Optional, Any

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END
from sentence_transformers import SentenceTransformer, util

from ..orchestration.state import AgentState


# https://huggingface.co/tasks/sentence-similarity
class RelevanceAgent(Runnable):
    def __init__(
            self,
            model: SentenceTransformer,
            baseline_path: str,
            relevance_threshold: float = 0.4,
            verbose: bool = False
    ) -> None:
        self.model = model
        self.relevance_threshold = relevance_threshold
        self.verbose_setting = verbose
        self.baseline_path = baseline_path
        self._init()

    def _init(self):
        with open(self.baseline_path, "r") as file:
            self.baseline_prompts = [item["question"] for item in json.load(file)]

        self.baseline_embedding = self.model.encode(
            self.baseline_prompts, convert_to_tensor=True
        )

    def invoke(
            self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> AgentState:
        verbose = state.get("verbose", self.verbose_setting)
        prompt = state.get("question")

        if verbose:
            print("\n[🧠 RelevanceAgent] — Starting relevance check")
            print(f"[🧠 RelevanceAgent] Input Prompt: \"{prompt}\"")

        prompt_embedding = self.model.encode(prompt, convert_to_tensor=True)
        score = util.pytorch_cos_sim(prompt_embedding, self.baseline_embedding).item()
        relevance = "relevant" if score > self.relevance_threshold else "irrelevant"

        if verbose:
            print(f"[🧠 RelevanceAgent] Cosine Similarity Score: {score:.4f}")
            print(f"[🧠 RelevanceAgent] Threshold: {self.relevance_threshold}")
            print(f"[🧠 RelevanceAgent] Classified as: {relevance.upper()}")

        # Update history
        history_entry = {
            "agent": "RelevanceAgent",
            "question": prompt,
            "assessment": relevance,
        }

        history = state.get("history", [])
        history.append(history_entry)

        return {
            "relevance": relevance,
            "history": history,
        }

    def check_relevance(self, state: AgentState) -> str:
        if state.get("verbose", self.verbose):
            print(f"[🔎 Relevance Check] → Status: {state.get('relevance')}")
        match state.get("relevance"):
            case "relevant":
                return "ReasoningAgent"
            case "irrelevant":
                return END
            case _:
                return "RelevanceAgent"