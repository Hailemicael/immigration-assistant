from typing import Optional, Any, Dict

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig

from ..orchestration.state import AgentState


class ReasoningAgent(Runnable):
    def __init__(self, llm, verbose_setting):
        self.llm = llm
        self.verbose_setting = verbose_setting

    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        verbose = state.get("verbose", self.verbose_setting)
        if verbose:
            print(f"\n[DEBUG - ReasoningAgent] Current generation stage: {state.get('generation_stage', 'initial')}")

        # Guard: already finalized
        if state.get("generation_stage") == "final" and state.get("final_response"):
            if verbose:
                print(f"[DEBUG - ReasoningAgent] Already finalized, returning existing state")
            return {}

        # Final pass: generate based on RAG + timeline context
        legislation = state.get("legislation", [])
        forms = state.get("forms", [])
        timeline = state.get("timeline", [])

        if (legislation or forms or timeline) and state.get("generation_stage") == "initial":
            if verbose:
                print(f"[DEBUG - ReasoningAgent] Generating final response using enriched context")
                print(f"[DEBUG - ReasoningAgent] Legislation: {legislation}")
                print(f"[DEBUG - ReasoningAgent] Forms: {forms}")
                print(f"[DEBUG - ReasoningAgent] Timeline: {timeline}")

            context = f"""
Initial response: {state.get("initial_response", "")}
Legislation: {', '.join(legislation or [])}
Forms: {', '.join(forms or [])}
Timelines: {', '.join(timeline or [])}
"""
            prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a legal assistant. Combine all context into a helpful, final summary."),
                ("human", "{context}")
            ])

            if verbose:
                print(f"[DEBUG - ReasoningAgent] Sending final prompt to LLM")

            response = (prompt | self.llm).invoke({"context": context})

            if verbose:
                print(f"[DEBUG - ReasoningAgent] Generated final response")

            # Update history
            history = state.get("history", [])
            history.append({
                "agent": "ReasoningAgent",
                "stage": "final",
                "context_used": True,
                "response_length": len(response)
            })

            return {
                "final_response": response,
                "generation_stage": "final",
                "history": history
            }

        # Initial pass: respond to question directly
        if verbose:
            print(f"[DEBUG - ReasoningAgent] Generating initial response")

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful immigration assistant. Answer clearly and concisely."),
            ("human", "{question}")
        ])

        if verbose:
            print(f"[DEBUG - ReasoningAgent] Sending initial prompt to LLM")

        response = (prompt | self.llm).invoke({"question": state.get("question", "")})

        if verbose:
            print(f"[DEBUG - ReasoningAgent] Generated initial response")

        # Update history
        history = state.get("history", [])
        history.append({
            "agent": "ReasoningAgent",
            "stage": "initial",
            "response_length": len(response)
        })

        return {
            "initial_response": response,
            "generation_stage": "initial",
            "history": history
        }

    def check_stage_for_rag(self, state: Dict) -> str:
        if state.get("verbose", self.verbose):
            print(f"[🔁 RAG Routing] → Generation Stage: {state.get('generation_stage')}")
        return "RAGAgent" if state.get("generation_stage") == "initial" else END