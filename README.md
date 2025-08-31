# AI MemeGen — "I need a MEME"

Generate situational memes from a short description, optionally swapping in a face from an uploaded image or URL. The app picks a meme template, crafts an edit prompt, and calls an image model to produce the final meme.

## What it does

- Selects a suitable meme template from `meme_templates.json` (derived from Memegen.link)
- Downloads the template image
- Optionally takes a reference face (file or URL)
- Asks a text model to produce a concise edit instruction
- Asks an image model to generate the final meme
- Returns a `data:` URI you can render or download

Backend is FastAPI; the UI is a single static page served by the backend.

## Requirements

- Python 3.12+
- An OpenRouter API key (free-tier models supported)

## Quickstart

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export OPENROUTER_API_KEY="<your_openrouter_api_key>"
uvicorn src.api:app --reload
# Open http://localhost:8000/
```

Alternatively, you can run the built-in entrypoint:

```bash
export OPENROUTER_API_KEY="<your_openrouter_api_key>"
python -m src.api
```

## Configuration

- `OPENROUTER_API_KEY` (required): API key used by `src/clients.py`.
- `PORT` (optional): Port for the built-in runner in `src/api.py` (defaults to `8000`).

## Endpoints

### GET `/`
Serves the static UI from `static/index.html`.

### POST `/meme`
Create a meme. Expects a multipart form:

- `description` (string, required)
- `reference_url` (string, optional)
- `reference_file` (file, optional; image)

Response (200):

```json
{
  "mime_type": "image/png",
  "data_uri": "data:image/png;base64,...",
  "template_id": "stonks",
  "template_name": "Stonks"
}
```

Possible errors:
- 400 if the model refuses for safety/policy reasons
- 400 if `description` is missing
- 500 on other failures

Curl examples:

```bash
# With only a description
curl -s -X POST \
  -F "description=When your Friday deploy actually works" \
  http://localhost:8000/meme | jq .

# With a face image file
curl -s -X POST \
  -F "description=Make a Stonks meme with this face" \
  -F "reference_file=@/path/to/face.png" \
  http://localhost:8000/meme | jq .

# With a face image URL
curl -s -X POST \
  -F "description=It finally compiles" \
  -F "reference_url=https://example.com/face.jpg" \
  http://localhost:8000/meme | jq .
```

### GET `/memes/background`
Returns a random list of template image URLs, used by the UI for the background grid.

Query params:
- `count` (int, default 60)

Response:

```json
{ "images": ["https://...", "https://..."] }
```

## Web UI

Open `http://localhost:8000/`. Enter a description, optionally upload a face or provide an image URL, then press Generate. The result appears inline and can be downloaded.

## How it works (architecture)

- `src/core.py`
  - `TemplateRepository` loads templates from `meme_templates.json`
  - `OpenRouterTemplateMatcher` ranks templates via OpenRouter (model: `google/gemini-2.5-flash-image-preview:free`)
  - `ImageDownloader` fetches the blank template image
  - `ImageEditPromptGenerator` asks a text model for a concise edit instruction
  - `MemeImageGenerator` asks an image model to produce one final image and returns it as bytes
- `src/api.py`
  - Defines FastAPI app and endpoints
  - Serves static UI from `static/`

Important: reference images and template images are sent to OpenRouter (embedded in the request as `data:` URIs). Do not upload sensitive content.

## Development

- Run the server in dev mode:

  ```bash
  uvicorn src.api:app --reload
  ```

- Logs use the `ai.memegen` logger; request flow includes correlation IDs.
- A small programmatic example exists in `test.py` (writes `generated_image.png`). Adjust the hardcoded example before using.

## Troubleshooting

- "OpenRouter API key not provided" — set `OPENROUTER_API_KEY` in your environment
- 400 with a refusal message — the model declined for safety/policy reasons; try changing the description
- 500 generating image — transient issues; retry, or check connectivity and logs

## Attribution

- Templates: Memegen.link (`meme_templates.json`)
- Models via OpenRouter — using `google/gemini-2.5-flash-image-preview:free`

## License

No license specified. Use at your own risk.
