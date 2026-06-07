"""Identity paraphraser for the no-defence condition (returns text unchanged)."""

from __future__ import annotations


class NoneParaphraser:
    name = "none"

    def rewrite(self, question: str, argument: str) -> str:
        return argument

    async def arewrite(self, question: str, argument: str) -> str:
        return argument
