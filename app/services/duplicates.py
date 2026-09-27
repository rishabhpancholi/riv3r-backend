"""Cross-domain duplicate checks composed from independent existence checks."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence

ExistenceCheck = Callable[[str], Awaitable[bool]]


class DuplicateChecker:
    def __init__(
        self,
        *,
        email_checks: Sequence[ExistenceCheck],
        url_checks: Sequence[ExistenceCheck],
    ):
        self.email_checks = tuple(email_checks)
        self.url_checks = tuple(url_checks)

    async def check_email_in_db(self, email: str) -> bool:
        return any(await asyncio.gather(*(check(email) for check in self.email_checks)))

    async def check_website_url_in_db(self, url: str) -> bool:
        return any(await asyncio.gather(*(check(url) for check in self.url_checks)))
