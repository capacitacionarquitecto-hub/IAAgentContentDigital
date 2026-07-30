import math
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
import gradio as gr

load_dotenv()

MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma4:e2b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
AGENT_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0.7"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")

llm = ChatOllama(model=MODEL_NAME, base_url=OLLAMA_BASE_URL, temperature=AGENT_TEMPERATURE)
embedding_model = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)

base_dir = Path(__file__).resolve().parent.parent
context_file = base_dir / "negocio_info.txt"

text = None
if context_file.exists():
    text = context_file.read_text(encoding="utf-8")

if text:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = text_splitter.split_text(text)
else:
    chunks = []

vector_store = []
if chunks:
    try:
        vector_store = [
            {"text": chunk, "embedding": embedding_model.embed_query(chunk)}
            for chunk in chunks
        ]
    except Exception:
        vector_store = []


def obtener_chunks_relevantes(pregunta: str, chunks_lista: list[str], top_k: int = 3) -> list[str]:
    if not chunks_lista:
        return []

    términos = set(re.findall(r"[a-záéíóúñ0-9]+", pregunta.lower()))
    if not términos:
        return chunks_lista[:top_k]

    puntuados = []
    for chunk in chunks_lista:
        texto = chunk.lower()
        score = sum(texto.count(término) for término in términos)
        puntuados.append((score, chunk))

    puntuados.sort(key=lambda item: item[0], reverse=True)
    resultados = [chunk for _, chunk in puntuados if chunk]
    return resultados[:top_k]


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def buscar_chunks_vectoriales(pregunta: str, top_k: int = 5) -> list[str]:
    if not vector_store:
        return obtener_chunks_relevantes(pregunta, chunks, top_k=top_k)

    try:
        query_embedding = embedding_model.embed_query(pregunta)
        puntuados = []
        for entry in vector_store:
            score = cosine_similarity(query_embedding, entry["embedding"])
            puntuados.append((score, entry["text"]))

        puntuados.sort(key=lambda item: item[0], reverse=True)
        resultados = [chunk for _, chunk in puntuados if chunk]
        return resultados[:top_k]
    except Exception:
        return obtener_chunks_relevantes(pregunta, chunks, top_k=top_k)


prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "Eres un asistente amable, claro y profesional que ofrece un servicio al cliente cálido y útil. Responde únicamente con información verificada del negocio. Usa el contexto proporcionado y no inventes datos. Si no tienes la respuesta, dilo de forma natural y concreta, por ejemplo: 'No tengo esa información en mi base de conocimiento'. Cuando el usuario pregunte por opciones del menú, incluye la descripción del plato y su precio exacto tal como aparece en el contexto. Evita respuestas vagas, evita inventar datos y evita sonar como un chatbot rígido o robotizado.",
        ),
        ("human", "Contexto del negocio:\n{contexto}\n\nPregunta: {question}"),
    ]
)

chain = prompt | llm


def responder(pregunta: str) -> str:
    if not pregunta or not pregunta.strip():
        return "Escribe una pregunta para comenzar."

    pregunta_norm = pregunta.lower()
    if any(palabra in pregunta_norm for palabra in ["hola", "buenos", "buenas", "ayuda", "saludo"]):
        return "Claro, con gusto te ayudo. ¿Qué necesitas saber sobre el negocio hoy?"

    try:
        contexto_relevante = buscar_chunks_vectoriales(pregunta, top_k=5)
        contexto = "\n\n".join(contexto_relevante) if contexto_relevante else "No hay información suficiente en el contexto del negocio."
        resultado = chain.invoke({"contexto": contexto, "question": pregunta})
        respuesta = resultado.content if hasattr(resultado, "content") else str(resultado)

        if not respuesta.strip():
            return "No tengo esa información en el contexto disponible, pero puedo ayudarte a encontrarla o indicar la mejor opción para consultar."

        return respuesta
    except Exception as exc:
        return (
            f"No se pudo conectar con Ollama. Verifica que Ollama esté corriendo y que el modelo '{MODEL_NAME}' esté descargado.\n"
            f"Error: {exc}"
        )


def chat(message: str, history):
    if not message:
        return history, ""

    response = responder(message)
    history = history or []
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": response})
    return history, ""


with gr.Blocks(title="El Sabor de la Plaza - Asistente Virtual") as demo:
    gr.Markdown("# El Sabor de la Plaza - Asistente Virtual")
    gr.Markdown(
        "Hola, soy tu asistente virtual. Puedo ayudarte con información sobre horarios, menú, domicilios, contacto y más."
    )
    gr.Markdown("**Ejemplos de preguntas:**\n- ¿Cuál es el horario de atención?\n- ¿Qué platos sirven para almuerzo?\n- ¿Cómo puedo hacer un pedido a domicilio?\n- ¿Cuál es su WhatsApp de contacto?")

    chatbot = gr.Chatbot(height=400)
    msg = gr.Textbox(label="Tu mensaje", placeholder="Escribe tu pregunta aquí...")
    clear = gr.Button("Limpiar conversación")

    msg.submit(chat, inputs=[msg, chatbot], outputs=[chatbot, msg])
    clear.click(lambda: [], None, chatbot)


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)