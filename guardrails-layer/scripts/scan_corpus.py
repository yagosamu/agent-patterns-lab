"""Run the prompt-injection scanner over every document in the corpus."""

import asyncio
import sys

from src.corpus import DOCS
from src.promptguard import scan

sys.stdout.reconfigure(encoding="utf-8")


async def main() -> None:
    for doc in DOCS.values():
        result = await scan(doc.body)
        print(f"{doc.doc_id:12} poisoned={str(doc.poisoned):5} score={result.score:.4f}")


asyncio.run(main())
