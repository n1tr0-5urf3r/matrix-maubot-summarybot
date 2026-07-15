# Summarybot

A [maubot](https://github.com/maubot/maubot) plugin that summarizes recent messages in a Matrix room using an LLM. Point it at any OpenAI-compatible chat-completions endpoint — for example the same LLM backend you already serve through [baibot](https://github.com/etkecc/baibot), a self-hosted vLLM/Ollama/LM Studio server, or a hosted API — and it will condense the last _N_ messages of a room into a short, structured summary on demand.

## What it does

Send `!summary` in a room and the bot will:

1. Fetch the recent message history (backwards from the current point).
2. Flatten it into a plain-text transcript (`sender: message`), oldest first, skipping non-text events and the `!summary` command itself.
3. Send that transcript to the configured LLM together with a system prompt.
4. Reply in the room with a Markdown-formatted summary.

### Command

| Command            | Description                                                       |
| ------------------ | ----------------------------------------------------------------- |
| `!summary`         | Summarize the last 100 messages (capped by `max_messages`).       |
| `!summary <count>` | Summarize the last `<count>` messages (capped by `max_messages`). |

Example:

```
!summary 50
```

## Configuration

Configuration is edited through the maubot admin UI (or the instance's client config). The defaults live in [`base-config.yaml`](base-config.yaml):

| Key             | Description                                                        | Default                           |
| --------------- | ------------------------------------------------------------------ | --------------------------------- |
| `api_url`       | Full URL of the OpenAI-compatible `chat/completions` endpoint.     | `CHANGEME`                        |
| `api_key`       | Bearer token sent as `Authorization: Bearer <api_key>`.            | `CHANGEME`                        |
| `model`         | Model name passed to the API.                                      | `qwen3-30b-a3b-instruct-2507`     |
| `max_messages`  | Hard upper bound on how many messages are ever fetched/summarized. | `200`                             |
| `max_tokens`    | Max tokens requested from the LLM for the summary.                 | `1000`                            |
| `temperature`   | Sampling temperature.                                              | `0.5`                             |
| `system_prompt` | Instruction prepended as the `system` message.                     | Concise summary prompt (see below) |

The shipped `system_prompt` asks for a concise, structured summary highlighting the main topics and decisions. Replace it with whatever style/language you prefer.

You **must** set `api_url` and `api_key` before the plugin will work.

### `api_url` examples

`api_url` is the full chat-completions endpoint, i.e. the provider's base URL plus `/chat/completions`. For a provider whose base URL is `https://chat-ai.academiccloud.de/v1`:

```yaml
api_url: https://chat-ai.academiccloud.de/v1/chat/completions
```

The same pattern applies to any OpenAI-compatible provider — take its base URL and append `/chat/completions`.

### Request shape

The plugin POSTs a standard OpenAI-style payload:

```json
{
  "model": "<model>",
  "messages": [
    { "role": "system", "content": "<system_prompt>" },
    { "role": "user", "content": "<transcript>" }
  ],
  "max_tokens": 1000,
  "temperature": 0.5
}
```

(`max_tokens` and `temperature` come from config.) The plugin reuses maubot's shared HTTP session and expects the response at `choices[0].message.content`. Requests time out after 120 seconds.

## Installation

1. Build the plugin (see below) or grab a prebuilt `.mbp` from the [Releases](../../releases) page.
2. In the maubot admin UI, upload the `.mbp` under **Plugins**.
3. Create a client (a Matrix account for the bot) and an instance that binds the client to the `de.kn.summarybot` plugin.
4. Edit the instance config: set `api_url` and `api_key`, adjust the model and prompt.
5. Invite the bot to a room and run `!summary`.

## Building

The plugin is packaged with the maubot CLI (`mbc`), which ships with the `maubot` PyPI package:

```bash
pip install maubot
mbc build          # produces de.kn.summarybot-v<version>.mbp
```

`mbc build` reads [`maubot.yaml`](maubot.yaml) and bundles the listed modules and `extra_files` into a `.mbp` archive (a zip of `maubot.yaml`, `summarybot.py`, and `base-config.yaml`).

To build and upload to a running maubot server in one step:

```bash
mbc login          # authenticate against your maubot instance
mbc build --upload
```

## Project layout

| File                       | Purpose                                              |
| -------------------------- | ---------------------------------------------------- |
| `summarybot.py`            | Plugin implementation (`SummaryBot` / `Config`).     |
| `maubot.yaml`              | Plugin manifest (id, version, modules, extra files). |
| `base-config.yaml`         | Default configuration values.                        |
| `.github/workflows/ci.yml` | Build verification + release packaging.              |

## License

MIT (see `license` in `maubot.yaml`).
