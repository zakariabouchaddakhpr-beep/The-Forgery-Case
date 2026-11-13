"""Turn keys.env into an n8n credentials file (only for keys that are filled in).

Usage: python tools/apply_keys.py keys.env out.json   -> prints how many credentials were written.
Never prints the keys themselves.
"""
import json
import sys
from pathlib import Path

env = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8-sig").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")

g = env.get
creds = []
if g("GROQ_KEY_ARCHIVIST"):
    creds.append({"id": "fcGroqArchiv0001", "name": "Groq - Archivist (header)", "type": "httpHeaderAuth",
                  "data": {"name": "Authorization", "value": "Bearer " + g("GROQ_KEY_ARCHIVIST")}})
if g("GROQ_KEY_SCIENTIST") or g("GROQ_KEY_ARCHIVIST"):  # one Groq key works for both, at half the rate limit
    creds.append({"id": "fcGroqScient0001", "name": "Groq - Scientist", "type": "groqApi",
                  "data": {"apiKey": g("GROQ_KEY_SCIENTIST") or g("GROQ_KEY_ARCHIVIST")}})
if g("GEMINI_KEY_CURATOR") or g("GEMINI_KEY_RESTORER"):
    creds.append({"id": "fcGeminiCurat001", "name": "Gemini - Curator", "type": "googlePalmApi",
                  "data": {"host": "https://generativelanguage.googleapis.com",
                           "apiKey": g("GEMINI_KEY_CURATOR") or g("GEMINI_KEY_RESTORER")}})
if g("GEMINI_KEY_RESTORER") or g("GEMINI_KEY_CURATOR"):
    creds.append({"id": "fcGeminiResto001", "name": "Gemini - Restorer (header)", "type": "httpHeaderAuth",
                  "data": {"name": "x-goog-api-key", "value": g("GEMINI_KEY_RESTORER") or g("GEMINI_KEY_CURATOR")}})
if g("GEMINI_KEY_RESTORER") or g("GEMINI_KEY_CURATOR"):  # the Restorer agent's chat model (same key rule)
    creds.append({"id": "fcGeminiRestoAI1", "name": "Gemini - Restorer", "type": "googlePalmApi",
                  "data": {"host": "https://generativelanguage.googleapis.com",
                           "apiKey": g("GEMINI_KEY_RESTORER") or g("GEMINI_KEY_CURATOR")}})
if g("COHERE_KEY"):
    creds.append({"id": "fcCohere00000001", "name": "Cohere", "type": "cohereApi", "data": {"apiKey": g("COHERE_KEY")}})
if g("CHROMA_KEY"):
    creds.append({"id": "fcChromaCloud001", "name": "Chroma Cloud (Sirine)", "type": "chromaCloudApi",
                  "data": {"apiKey": g("CHROMA_KEY"), "tenant": g("CHROMA_TENANT") or "",
                           "database": g("CHROMA_DATABASE") or "", "baseUrl": "https://api.trychroma.com"}})

if g("CURATOR_COHERE_KEY") or g("COHERE_KEY"):
    creds.append({"id": "fcCohereCurat001", "name": "Cohere - Curator", "type": "cohereApi",
                  "data": {"apiKey": g("CURATOR_COHERE_KEY") or g("COHERE_KEY")}})
cur = "CURATOR_" if g("CURATOR_CHROMA_KEY") else ""  # no Curator account -> use the shared one
if g(cur + "CHROMA_KEY"):
    creds.append({"id": "fcChromaCurat001", "name": "Chroma Cloud - Curator", "type": "chromaCloudApi",
                  "data": {"apiKey": g(cur + "CHROMA_KEY"), "tenant": g(cur + "CHROMA_TENANT") or "",
                           "database": g(cur + "CHROMA_DATABASE") or "", "baseUrl": "https://api.trychroma.com"}})

Path(sys.argv[2]).write_text(json.dumps(creds), encoding="utf-8")
print(f"{len(creds)} credential(s) with keys: " + ", ".join(c["name"] for c in creds))
