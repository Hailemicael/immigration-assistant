from typing import Literal, List, Optional, Union, Dict
from pydantic import BaseModel
from langchain_ollama import OllamaLLM #use our llm
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import Runnable
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END


# ---- 1. Define State ----
class AgentState(BaseModel):
    question: str
    relevance: str #Optional or not
    initialResponse: str #Optional or not
    intent: Literal["simple", "complex", "unknown"]
    timeline: Dict #verify with Santoshi code output type + Optional or not
    forms: List[Dict] = [] #Optional or not
    legislation: List[Dict] = [] #Optional or not
    documents: Optional[List[str]] = []
    answer: Optional[str] = None
    interpreted_answer: Optional[str] = None

# ---- 2. Define Agents ----
llm = OllamaLLM(model="mistral") #use our llm

# Agent 1: Chatbot agent (replace with real chatbot LLM)
class UserQueryAgent(Runnable):
    def __init__(self, llm):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You classify questions as 'simple' or 'complex'."),
            ("human", "{question}")
        ])
        self.chain = self.prompt | self.llm

    def invoke(self, state, config=None):  # <--- FIXED: add `config=None`
        result = self.chain.invoke({"question": state.question})
        intent = "complex" if "complex" in result.lower() else "simple"
        return state.copy(update={"intent": intent})
    
class ReasoningAgent(Runnable):
    def __init__(self, llm):
        self.llm = llm
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You classify questions as 'simple' or 'complex'."),
            ("human", "{question}")
        ])
        self.chain = self.prompt | self.llm

    def invoke(self, state, config=None):  # <--- FIXED: add `config=None`
        result = self.chain.invoke({"question": state.question})
        intent = "complex" if "complex" in result.lower() else "simple"
        return state.copy(update={"intent": intent})

class RAGAgent(Runnable):
    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None) -> AgentState:
        # Fake "retrieved" docs
        docs = [f"Doc1 about {state.question}", f"Doc2 with details on {state.question}"]
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful legal assistant using retrieved documents."),
            ("human", "Question: {question}\nDocuments: {documents}")
        ])
        chain = prompt | llm
        answer = chain.invoke({
            "question": state.question,
            "documents": "\n".join(docs)
        })#.content
        return state.copy(update={"documents": docs, "answer": answer})

# Agent 3: Legalese interpreter
class LegaleseInterpreterAgent(Runnable):
    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None) -> AgentState:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite this legal text in plain English."),
            ("human", "{answer}")
        ])
        chain = prompt | llm
        interpreted = chain.invoke({"answer": state.answer})#.content
        return state.copy(update={"interpreted_answer": interpreted})
    
# Agent 4: Relevance
class RelevanceAgent(Runnable):
    def invoke(self, state: AgentState, config: Optional[RunnableConfig] = None) -> AgentState:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Rewrite this legal text in plain English."),
            ("human", "{answer}")
        ])
        chain = prompt | llm
        interpreted = chain.invoke({"answer": state.answer})#.content
        return state.copy(update={"interpreted_answer": interpreted})

# ---- 3. Build LangGraph ----
builder = StateGraph(AgentState)

# Nodes
builder.add_node("RelevanceAgent", RelevanceAgent())
builder.add_node("ReasoningAgent", ReasoningAgent(llm))
builder.add_node("UserQueryAgent", UserQueryAgent(llm))
builder.add_node("RAGAgent", RAGAgent())
builder.add_node("LegaleseInterpreterAgent", LegaleseInterpreterAgent())

# Edges
builder.set_entry_point("RelevanceAgent")
#builder.set_entry_point("UserQueryAgent")
builder.add_edge("RelevanceAgent", "ReasoningAgent")
builder.add_edge("ReasoningAgent", "RAGAgent")
builder.add_edge("UserQueryAgent", "RAGAgent")

def route_after_rag(state: AgentState) -> str:
    if state.intent == "complex":
        return "LegaleseInterpreterAgent"
    return "end"

builder.add_conditional_edges("RAGAgent", route_after_rag)
builder.add_edge("LegaleseInterpreterAgent", END)
builder.add_edge("RAGAgent", END)

graph = builder.compile()

# ---- 4. Run it! ----
if __name__ == "__main__":
    #get question from flask
    question = "Can you explain the new H-1B visa rules under the 2024 immigration policy changes?"
    initial_state = AgentState(question=question, intent="unknown")

    final_state = graph.invoke(initial_state)

    print("\n--- Final State ---")
    print(f"Intent: {final_state.intent}")
    print(f"Retrieved Docs: {final_state.documents}")
    print(f"Answer: {final_state.answer}")
    print(f"Interpreted Answer: {final_state.interpreted_answer}")