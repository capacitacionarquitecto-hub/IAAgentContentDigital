# IAAgentContentDigital

## Crear y activar entorno virtual

En Windows, puedes crear un entorno virtual con Python desde la raíz del proyecto:

```powershell
py -m venv .venv
```

Para activarlo:

```powershell
.\.venv\Scripts\activate
```

Si deseas instalar las dependencias del proyecto:

```powershell
pip install -r requirements.txt
```

## Usar Ollama

1. Instala Ollama en tu sistema y asegúrate de que esté corriendo.
2. Descarga los modelos necesarios:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

3. Desde la raíz del proyecto, instala las dependencias:

```powershell
pip install -r requirements.txt
```

4. Ejecuta la aplicación:

```powershell
python agenteNegocioBase/app.py
```

5. Si quieres usar otro modelo de chat, define la variable de entorno:

```powershell
$env:OLLAMA_MODEL="phi3"
```

6. Si quieres cambiar el modelo de embeddings:

```powershell
$env:OLLAMA_EMBEDDING_MODEL="nomic-embed-text"
```
