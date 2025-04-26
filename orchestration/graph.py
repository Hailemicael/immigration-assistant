from typing import Literal, List, Optional, Any, Dict, TypedDict
from typing_extensions import TypedDict

from langchain_ollama import OllamaLLM
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END

# ---------- 1. Define State ----------
class AgentState(TypedDict):
    question: str
    relevance: Literal["relevant", "irrelevant", "unknown"]
    generation_stage: Literal["initial", "final"]
    initial_response: Optional[str]
    legislation: Optional[List[str]]
    forms: Optional[List[str]]
    timeline: Optional[List[str]]
    final_response: Optional[str]
    verbose: bool  # Add verbose flag to state


# ---------- 2. LLM ----------
llm = OllamaLLM(model="mistral")


# ---------- 3. Agents ----------
# A. Relevance Agent
class RelevanceAgent(Runnable):
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        if state.get("verbose", False):
            print(f"\n[DEBUG - RelevanceAgent] Processing question: {state['question']}")

        prompt = ChatPromptTemplate.from_messages([
            ("system", "Is this question related to immigration law? Answer with 'relevant' or 'irrelevant'."),
            ("human", "{question}")
        ])

        if state.get("verbose", False):
            print(f"[DEBUG - RelevanceAgent] Sending prompt to LLM")

        result = (prompt | llm).invoke({"question": state["question"]})
        relevance = "relevant" if "relevant" in result.lower() else "irrelevant"

        if state.get("verbose", False):
            print(f"[DEBUG - RelevanceAgent] LLM result: {result}")
            print(f"[DEBUG - RelevanceAgent] Determined relevance: {relevance}")

        return {"relevance": relevance}


# B. Reasoning Agent (initial + final combined)
class ReasoningAgent(Runnable):
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        if state.get("verbose", False):
            print(f"\n[DEBUG - ReasoningAgent] Current generation stage: {state.get('generation_stage', 'initial')}")

        # Guard: already finalized
        if state.get("generation_stage") == "final" and state.get("final_response"):
            if state.get("verbose", False):
                print(f"[DEBUG - ReasoningAgent] Already finalized, returning existing state")
            return {}

        # Final pass: generate based on RAG + timeline context
        legislation = state.get("legislation", [])
        forms = state.get("forms", [])
        timeline = state.get("timeline", [])

        if (legislation or forms or timeline) and state.get("generation_stage") == "initial":
            if state.get("verbose", False):
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

            if state.get("verbose", False):
                print(f"[DEBUG - ReasoningAgent] Sending final prompt to LLM")

            response = (prompt | llm).invoke({"context": context})

            if state.get("verbose", False):
                print(f"[DEBUG - ReasoningAgent] Generated final response")

            return {
                "final_response": response,
                "generation_stage": "final"
            }

        # Initial pass: respond to question directly
        if state.get("verbose", False):
            print(f"[DEBUG - ReasoningAgent] Generating initial response")

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful immigration assistant. Answer clearly and concisely."),
            ("human", "{question}")
        ])

        if state.get("verbose", False):
            print(f"[DEBUG - ReasoningAgent] Sending initial prompt to LLM")

        response = (prompt | llm).invoke({"question": state.get("question", "")})

        if state.get("verbose", False):
            print(f"[DEBUG - ReasoningAgent] Generated initial response")

        return {
            "initial_response": response,
            "generation_stage": "initial"
        }


# C. RAG Agent
class RAGAgent(Runnable):
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        if state.get("verbose", False):
            print(f"\n[DEBUG - RAGAgent] Looking up relevant information for: {state.get('question', '')}")

        # Fake simulated lookup
        question = state.get("question", "")
        legislation = ["8 CFR 214.2(h)(4) - H-1B Specialty Occupations"] if "H-1B" in question else []
        forms = ["Form I-129", "Form ETA-9035"] if "H-1B" in question else []

        if state.get("verbose", False):
            print(f"[DEBUG - RAGAgent] Found legislation: {legislation}")
            print(f"[DEBUG - RAGAgent] Found forms: {forms}")

        return {"legislation": legislation, "forms": forms}


# D. Timeline Agent
class TimelineAgent(Runnable):
    def invoke(self, state: Dict, config: Optional[RunnableConfig] = None, **kwargs: Any) -> Dict:
        if state.get("verbose", False):
            print(f"\n[DEBUG - TimelineAgent] Processing forms: {state.get('forms', [])}")

        if not state.get("forms"):
            if state.get("verbose", False):
                print(f"[DEBUG - TimelineAgent] No forms found, skipping")
            return {}

        timeline_info = [f"{form}: 3–6 months processing" for form in state.get("forms", [])]

        if state.get("verbose", False):
            print(f"[DEBUG - TimelineAgent] Generated timeline info: {timeline_info}")

        return {"timeline": timeline_info}


# ---------- 4. Build LangGraph ----------
builder = StateGraph(AgentState)

# Nodes
builder.add_node("RelevanceAgent", RelevanceAgent())
builder.add_node("ReasoningAgent", ReasoningAgent())
builder.add_node("RAGAgent", RAGAgent())
builder.add_node("TimelineAgent", TimelineAgent())

# Entry
builder.set_entry_point("RelevanceAgent")

# Relevance Check
def check_relevance(state: Dict) -> str:
    if state.get("verbose", False):
        print(f"\n[DEBUG - Graph] Checking relevance: {state.get('relevance')}")
    if state.get("relevance") == "relevant":
        return "ReasoningAgent"
    elif state.get("relevance") == "irrelevant":
        return END
    else:  # Handle 'unknown' case
        return "RelevanceAgent"  # Loop back to re-evaluate relevance

builder.add_conditional_edges("RelevanceAgent", check_relevance)

# Initial Reasoning → RAG
def check_stage_for_rag(state: Dict) -> str:
    if state.get("verbose", False):
        print(f"\n[DEBUG - Graph] Checking stage for RAG routing: {state.get('generation_stage')}")
    # Only proceed to RAG if we're in the initial stage
    return "RAGAgent" if state.get("generation_stage") == "initial" else END

builder.add_conditional_edges("ReasoningAgent", check_stage_for_rag)

# RAG → Timeline or Final Reasoning
def check_forms(state: Dict) -> str:
    if state.get("verbose", False):
        print(f"\n[DEBUG - Graph] Checking forms: {state.get('forms', [])}")
    # Only go to timeline if we have forms and haven't finished yet
    if state.get("forms") and state.get("generation_stage") == "initial":
        return "TimelineAgent"
    # If no forms or already finished, go back to reasoning for finalization
    return "ReasoningAgent"

builder.add_conditional_edges("RAGAgent", check_forms)

# Timeline → Final Reasoning (only if we're not done)
def route_after_timeline(state: Dict) -> str:
    if state.get("verbose", False):
        print(f"\n[DEBUG - Graph] Routing after timeline: {state.get('generation_stage')}")
    # If we're still in the initial stage, go to reasoning for finalization
    return "ReasoningAgent" if state.get("generation_stage") == "initial" else END

builder.add_conditional_edges("TimelineAgent", route_after_timeline)

# Compile
graph = builder.compile()

# ---------- 5. Run ----------
if __name__ == "__main__":
    verbose = True  # Set to True for verbose mode

    if verbose:
        print("\n[DEBUG] Starting agent with verbose mode enabled\n")

    initial_state = {
        "question": "Can you explain the new H-1B visa rules under the 2024 immigration policy changes?",
        "relevance": "unknown",  # Changed back to unknown as default
        "generation_stage": "initial",
        "initial_response": None,
        "legislation": [],
        "forms": [],
        "timeline": [],
        "final_response": None,
        "verbose": verbose
    }

    if verbose:
        print(f"[DEBUG] Initial state: {initial_state}\n")
        print(f"[DEBUG] Invoking graph...\n")

    result = graph.invoke(initial_state)

    if verbose:
        print("\n[DEBUG] Graph execution complete\n")

    print("\n--- Final State ---")
    print(f"Relevance: {result.get('relevance')}")
    print(f"Initial Response:\n{result.get('initial_response')}")
    print(f"Legislation: {result.get('legislation', [])}")
    print(f"Forms: {result.get('forms', [])}")
    print(f"Timeline: {result.get('timeline', [])}")
    print(f"\nFinal Answer:\n{result.get('final_response')}")