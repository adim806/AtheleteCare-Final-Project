# Local LLM Model Directory

Place your Llama.cpp-compatible **GGUF** model file in this directory.

## Active Model (configured)

| File | Size | Description |
|------|------|-------------|
| `llama-3-8b-instruct.gguf` | ~4.6 GB | Meta Llama 3 8B Instruct (Q4_K_M quantisation) |

This filename matches the default in `app/config.py` and `.env`.

## Configuration

Set in `.env` (copy from `.env.example`):

```env
LLAMA_MODEL_PATH=models/llama-3-8b-instruct.gguf
LLAMA_CHAT_FORMAT=llama-3
```

If you use a different filename, update `LLAMA_MODEL_PATH` accordingly.

## GPU acceleration (optional)

If you have an NVIDIA GPU, increase offloading in `.env`:

```env
LLAMA_N_GPU_LAYERS=35
```

## Notes

- Model files are **not** committed to git (see `.gitignore`).
- Do **not** use Ollama for this service — the app loads the `.gguf` file directly via `llama-cpp-python`.
