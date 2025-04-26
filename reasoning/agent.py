from typing import Optional, Any, Dict

from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.constants import END
from huggingface_hub import InferenceClient

from ..orchestration.state import AgentState
from ..rag.agent import RAGAgent


class ReasoningAgent(Runnable):
    node = "ReasoningAgent"

    def __init__(self, endpoint_url: str, api_token: str, verbose: bool = False):
        """
        Initialize a reasoning agent with a PEFT model.
        """
        self.client =  InferenceClient(
            base_url=endpoint_url,
            token=api_token
        )

        self.verbose = verbose

    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        """
        Process the current state and generate a response.
        """
        verbose = state.get("verbose", self.verbose)
        question = state.get("question")
        def log(msg: str):
            if verbose:
                print(f"[🧠 ReasoningAgent] {msg}")

        log(f"🌀 Generation stage: {state.get('generation_stage', 'initial')}")

        if state.get("generation_stage") == "final" and state.get("final_response"):
            log("🛑 Final response already exists. Skipping generation.")
            return {}

        legislation = state.get("legislation", [])
        forms = state.get("forms", [])
        timeline = state.get("timeline", [])

        if (legislation or forms or timeline) and state.get("generation_stage") == "initial":
            log("📚 Context enriched — composing final response")
            log(f"📘 Legislation: {len(legislation)} match(es)")
            log(f"📄 Forms: {len(forms)} match(es)")
            log(f"📆 Timeline: {len(timeline)} event(s)")

            legislation_entries = "\n\n".join(
                f"- {item.get('match_id', '')} | {item.get('title', '')} — {item.get('chapter', '')} — {item.get('subchapter', '')}\n"
                f"{item.get('chunk', '').strip()}"
                for item in legislation
            )

            forms_entries = "\n\n".join(
                f"- {item.get('title', '')}: {item.get('description', '').strip()}"
                for item in forms
            )

            timeline_entries = "\n".join(f"- 📆 {entry}" for entry in (timeline or []))

            context = f"""
            Context: "You are a helpful immigration assistant. Answer clearly and concisely. Combine all context into a helpful, final summary."
            
            Initial Response:
            {state.get("initial_response", "").strip()}

            Legislation Matches:
            {legislation_entries or 'None found'}

            Related Forms:
            {forms_entries or 'None found'}

            Timeline Suggestions:
            {timeline_entries or 'None found'}
            """

            log("🤖 Sending final prompt to model...")

            response = self.client.question_answering(question, context)
            log("✅ Final response generated.")
            if verbose:
                log(f"  → ✅ {response.answer}")
            history = state.get("history", [])
            history.append({
                "agent": ReasoningAgent.node,
                "stage": "final",
                "context_used": True,
                "response_length": len(response.answer)
            })

            return {
                "final_response": response.answer,
                "generation_stage": "final",
                "history": history
            }

        log("🧪 No external context yet — generating initial response.")
        system_message = "You are a helpful immigration assistant. Answer clearly and concisely."
        question = state.get("question", "")
        log("🧠 Sending initial prompt to model...")
        response = self.client.question_answering(question, system_message)
        log("✅ Initial response generated.")
        if verbose:
            log(f"  → ✅ {response.answer}")
        history = state.get("history", [])
        history.append({
            "agent": ReasoningAgent.node,
            "stage": "initial",
            "response_length": len(response.answer)
        })

        return {
            "initial_response": response.answer,
            "generation_stage": "initial",
            "history": history
        }

    def check_stage_for_rag(self, state: Dict) -> str:
        """
        Determine whether to route to RAG or end based on current state.
        """
        verbose = state.get("verbose", self.verbose)
        if verbose:
            print(f"[🔁 Routing Decision] Current generation stage: {state.get('generation_stage')}")
        return RAGAgent.node if state.get("generation_stage") == "initial" else END
