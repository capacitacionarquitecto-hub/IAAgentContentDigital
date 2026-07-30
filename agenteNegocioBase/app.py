from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from dotenv import load_dotenv
from IPython.display import display, Image
import gradio as gr
import requests
import os
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.tools import Tool
from langchain_community.utilities import GoogleSerperAPIWrapper

load_dotenv(override=True)

serper = GoogleSerperAPIWrapper(api_key=os.getenv("SERPER_API_KEY"))

tool_search_google = Tool(
    name="Search Google",
    description="Searches Google for information.",
    func=serper.run,
)

pushover_token = os.getenv("PUSH_OVER_API_KEY")
pushover_user = os.getenv("PUSH_OVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"


def push(text: str):
    """Send a notification using Pushover."""
    requests.post(
        pushover_url,
        data={"token": pushover_token, "user": pushover_user, "message": text},
    )


tool_push_notification = Tool(
    name="Push Notification",
    description="Sends a push notification using Pushover.",
    func=push,
)

agent_tools = [tool_search_google, tool_push_notification]


class State(TypedDict):
    """State of the agent."""

    messages: list[dict]
    tools: list[Tool]


MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
AGENT_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL, temperature=AGENT_TEMPERATURE)
embedding_model = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)

system_prompt = """
Eres un asistente útil y proactivo. Responde directamente a la pregunta del usuario.
Si la pregunta requiere información externa, actual, deportiva, reciente o factual, usa la herramienta Search Google antes de responder.
No saludes ni respondas con mensajes genéricos como 'Hola, soy un asistente útil y proactivo. ¿En qué puedo ayudarte hoy?'.
Responde con la respuesta concreta a la pregunta.
"""

llm_with_tools = llm.bind_tools(agent_tools)


def chat_node(state: State) -> dict:
    try:
        messages = state.get("messages", [])
        if not messages:
            messages = [{"role": "system", "content": system_prompt}]
        else:
            messages = [{"role": "system", "content": system_prompt}] + list(messages)

        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    except Exception as exc:
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": f"No se pudo conectar con Ollama. Verifica que esté corriendo. Error: {exc}",
                }
            ]
        }


def should_continue(state: State):
    messages = state.get("messages", [])
    if not messages:
        return END
    last_message = messages[-1]
    if getattr(last_message, "tool_calls", None):
        return "tools"
    return END


def build_graph():
    graph_builder = StateGraph(State)
    graph_builder.add_node("chatBot", chat_node)
    graph_builder.add_node("tools", ToolNode(tools=agent_tools))
    graph_builder.add_edge(START, "chatBot")
    graph_builder.add_conditional_edges("chatBot", should_continue, {"tools": "tools", END: END})
    graph_builder.add_edge("tools", "chatBot")
    return graph_builder.compile()


def chat_interface_fn(user_input: str, history):
    if not user_input or not user_input.strip():
        return ""

    try:
        history_messages = []
        if history:
            for item in history:
                if isinstance(item, dict):
                    role = item.get("role", "user")
                    content = item.get("content", "")
                else:
                    role = getattr(item, "role", "user")
                    content = getattr(item, "content", "")
                history_messages.append({"role": role, "content": content})

        messages = history_messages + [{"role": "user", "content": user_input}]
        result = graph.invoke({"messages": messages})
        messages_out = result.get("messages", [])
        if not messages_out:
            return "No se recibió respuesta del agente."

        last_message = messages_out[-1]
        if hasattr(last_message, "content"):
            content = last_message.content
        elif isinstance(last_message, dict):
            content = last_message.get("content", "")
        else:
            content = str(last_message)

        return content if isinstance(content, str) else str(content)
    except Exception as exc:
        return f"No se pudo procesar la solicitud: {exc}"


def main():
    global graph
    graph = build_graph()
    try:
        display(Image(graph.get_graph().draw_mermaid_png()))
    except Exception as exc:
        print(f"Agente compilado correctamente. No se pudo renderizar el grafo: {exc}")
    gr.ChatInterface(chat_interface_fn).launch()


if __name__ == "__main__":
    main()


