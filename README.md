# Rayzo AI — RAG backend integration

## Project structure
- `main.py` — FastAPI backend and your RAG pipeline
- `requirements.txt` — Python dependencies
- `index.html`, `style.css`, `script.js` — website frontend

## 1. Install dependencies
Open a terminal in this folder:

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

Then:
```bash
pip install -r requirements.txt
```

## 2. Set your Gemini API key
Set the key in the terminal before starting the server.

PowerShell:
```powershell
$env:GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

Command Prompt:
```cmd
set GEMINI_API_KEY=YOUR_GEMINI_API_KEY
```

Do not put your API key in `script.js`, HTML, or any frontend file.
The model names are configurable through `GEMINI_CHAT_MODEL` and `GEMINI_EMBED_MODEL`.
If your Google GenAI account does not recognize the model IDs from your original script,
set these environment variables to model IDs currently available to your account.

## 3. Start the API
```bash
uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`.
Interactive API docs: `http://127.0.0.1:8000/docs`.

## 4. Run the website
In another terminal, from this folder:
```bash
python -m http.server 5500
```
Open `http://127.0.0.1:5500`.

## How it works
1. The website sends a selected file to `POST /api/upload`.
2. Python extracts text, chunks it, and creates embeddings once.
3. The website sends each question to `POST /api/chat`.
4. Python embeds the question, retrieves the top three chunks, and asks Gemini to answer from that context.

## Notes
- This is a local single-user prototype. Uploaded document chunks and vectors are stored in RAM and disappear when the API restarts.
- Before public deployment, add authentication, per-user document isolation, persistent vector storage, upload limits/rate limits, and restrict CORS to your website domain.
- The document panel displays a local PDF preview in the browser. For other formats, it shows extracted text returned by the backend.
- Scanned PDFs and image uploads use Gemini file upload + vision extraction.
