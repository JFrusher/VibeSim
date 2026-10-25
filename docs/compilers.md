# Compilers


A prompt is compiled once, when the simulation is created. Pick the compiler per request:

- `"compiler": "keyword"` (default): offline keyword parser over the built-in presets, the only one that sets up real-road vans and order books.
- `"compiler": "claude"`: Claude (`claude-opus-5-5`, structured output) designs entities from any description, using declarative fields and machines. Needs `pip install "vibesim[claude]"` and `ANTHROPIC_API_KEY`. It fails with a clear error if either is missing, and never quietly falls back to the keyword parser. Requests opt into the API's server-side refusal fallback.

`POST /compile` returns the config without running it, so you can inspect or edit it and then POST it back as `{"config": ...}`.
