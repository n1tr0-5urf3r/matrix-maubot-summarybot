from typing import Type
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import EventType, MessageType, PaginationDirection
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from aiohttp import ClientError, ClientTimeout

REQUEST_TIMEOUT = ClientTimeout(total=120)


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("api_url")
        helper.copy("api_key")
        helper.copy("model")
        helper.copy("max_messages")
        helper.copy("max_tokens")
        helper.copy("temperature")
        helper.copy("system_prompt")


class SummaryBot(Plugin):
    async def start(self) -> None:
        self.config.load_and_update()

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config

    @command.new("summary", help="Summarize recent room messages")
    @command.argument("count", required=False)
    async def summary(self, evt: MessageEvent, count: str | None) -> None:
        if not self.config["api_url"] or self.config["api_url"] == "CHANGEME":
            await evt.reply("Not configured yet: set `api_url` and `api_key` in the plugin config.")
            return

        limit = min(int(count) if count and count.isdigit() else 100,
                    self.config["max_messages"])

        # 1. Fetch history (backwards from now)
        resp = await self.client.get_messages(
            evt.room_id, direction=PaginationDirection.BACKWARD, limit=limit
        )

        # 2. Build a plain-text log, oldest first
        lines = []
        for e in reversed(resp.events):
            if e.type != EventType.ROOM_MESSAGE:
                continue
            body = getattr(e.content, "body", "") or ""
            if body.startswith("!summary"):
                continue  # don't summarize the summon
            if getattr(e.content, "msgtype", None) in (MessageType.TEXT, MessageType.NOTICE,
                                                        MessageType.EMOTE):
                sender = e.sender.split(":")[0].lstrip("@")
                lines.append(f"{sender}: {body}")

        if not lines:
            await evt.reply("Nothing to summarize. Suspiciously quiet in here.")
            return

        await evt.mark_read()

        # 3. Ship to the LLM
        payload = {
            "model": self.config["model"],
            "messages": [
                {"role": "system", "content": self.config["system_prompt"]},
                {"role": "user", "content": "\n".join(lines)},
            ],
            "max_tokens": self.config["max_tokens"],
            "temperature": self.config["temperature"],
        }
        headers = {"Authorization": f"Bearer {self.config['api_key']}"}

        try:
            async with self.http.post(self.config["api_url"], json=payload,
                                      headers=headers, timeout=REQUEST_TIMEOUT) as r:
                if r.status != 200:
                    body = (await r.text())[:200]
                    self.log.warning(f"LLM API returned {r.status}: {body}")
                    await evt.reply(f"API error {r.status}: {body}")
                    return
                data = await r.json()
        except ClientError as e:
            self.log.exception("LLM request failed")
            await evt.reply(f"Request failed: {e}")
            return

        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            self.log.warning(f"Unexpected LLM response shape: {data!r:.500}")
            await evt.reply("Got an unexpected response from the LLM.")
            return

        await evt.reply(f"**Summary of the last {len(lines)} messages:**\n\n{text}",
                        markdown=True)
