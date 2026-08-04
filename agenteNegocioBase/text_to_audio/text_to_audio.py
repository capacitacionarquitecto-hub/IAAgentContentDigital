import asyncio
import edge_tts

async def text_to_speech_tool(text: str, output_file: str = "output.mp3", voice: str = "es-MX-JorgeNeural") -> str:
    """
    Convierte un texto dado en un archivo de audio MP3 usando voces neuronales gratuitas.
    
    Voces populares en español:
    - 'es-ES-AlvaroNeural' (Español de España, masculino)
    - 'es-ES-ElviraNeural' (Español de España, femenino)
    - 'es-MX-JorgeNeural' (Español de México, masculino)
    - 'es-MX-DaliaNeural' (Español de México, femenino)
    """
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)
    return f"Audio generado exitosamente y guardado en '{output_file}'"

# Ejemplo de uso desde el agente:
if __name__ == "__main__":
    prompt = "Hola, soy tu asistente virtual y este audio fue generado sin costo."
    
    # Ejecutar la función asíncrona
    resultado = asyncio.run(text_to_speech_tool(prompt, "respuesta_agente.mp3"))
    print(resultado)