import asyncio
import logging
from typing import List, Optional, Any, Dict, Tuple

import discord
from discord.auth import Account

coldcaller_logger: logging.Logger = logging.getLogger(__name__)


class _ClientContextManager:
    def __init__(self, account: Account, **kwargs) -> None:
        self._account: Account = account
        self._client: Optional[discord.Client] = None
        self._client_kwargs: Dict[str, Any] = kwargs

    async def __aenter__(self) -> discord.Client:
        if self._client_kwargs.get("loop") is None:
            self._client_kwargs["loop"] = self._account.loop

        self._client = discord.Client(**self._client_kwargs)

        await self._client.login(self._account.token)

        self._account.loop.create_task(self._client.connect())

        await self._client.wait_until_ready()

        return self._client

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if not self._client.is_closed():
            await self._client.close()


async def verify_account(account: Account, loop: Optional[asyncio.AbstractEventLoop] = None, **kwargs) -> bool:
    loop = loop or asyncio.get_event_loop()

    async with _ClientContextManager(account, loop=loop, **kwargs) as client:
        try:
            await client.fetch_user_profile(account.user.id)
        except discord.Forbidden:
            logging.error(f"{account.user.name}#{account.user.discriminator} ({account.user.id}) "
                          f"with email {account.email} is not in good standing!")
            return False
        except discord.HTTPException:
            await asyncio.sleep(90)  # In case we are getting rate-limited.
            return await verify_account(account, **kwargs)
        except Exception:
            raise
        else:
            logging.info(f"{account.user.name}#{account.user.discriminator} ({account.user.id}) "
                         f"with email {account.email} is in good standing!")
            return True


def get_logging_level(name: str) -> int:
    match name.upper():
        case "CRITICAL":
            return logging.CRITICAL
        case "FATAL":
            return logging.FATAL
        case "ERROR":
            return logging.ERROR
        case "WARNING":
            return logging.WARNING
        case "WARN":
            return logging.WARN
        case "INFO":
            return logging.INFO
        case "DEBUG":
            return logging.DEBUG
    return logging.NOTSET


async def unblock_all_as_all(accounts: List[Account], *, loop: Optional[asyncio.AbstractEventLoop] = None,
                             **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    tasks: List[asyncio.Task] = []

    for account in accounts:
        tasks.append(loop.create_task(unblock_all(account, loop=loop, **kwargs)))

    for task in tasks:
        await task


async def leave_all_as_all(accounts: List[Account], *, loop: Optional[asyncio.AbstractEventLoop] = None,
                           **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    tasks: List[asyncio.Task] = []

    for account in accounts:
        tasks.append(loop.create_task(leave_all(account, loop=loop, **kwargs)))

    for task in tasks:
        await task


async def leave_all(account: Account, *, loop: Optional[asyncio.AbstractEventLoop], **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    async with _ClientContextManager(account, loop=loop, **kwargs) as client:
        for guild in client.guilds:
            guild: discord.Guild
            try:
                await guild.leave()
            except discord.HTTPException:
                coldcaller_logger.warning(
                    f"Couldn't leave {guild.name} ({guild.id}) as "
                    f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                )
                continue
            except Exception:
                raise
            else:
                coldcaller_logger.info(
                    f"Left {guild.name} ({guild.id}) as "
                    f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                )
            finally:
                await asyncio.sleep(10)


async def verify_all(accounts: List[Account], *, loop: Optional[asyncio.AbstractEventLoop] = None,
                     **kwargs) -> List[Account]:
    loop = loop or asyncio.get_event_loop()

    tasks: List[Tuple[Account, asyncio.Task]] = []
    good_accounts: List[Account] = []

    for account in accounts:
        tasks.append((account, loop.create_task(verify_account(account, loop=loop, **kwargs))))

    for account, task in tasks:
        if await task:
            good_accounts.append(account)

    return good_accounts


async def unblock_all(account: Account, *, loop: Optional[asyncio.AbstractEventLoop], **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    async with _ClientContextManager(account, loop=loop, **kwargs) as client:
        for user in client.users:
            if user is client.user:
                continue
            user: discord.User
            if user.is_blocked():
                try:
                    await user.unblock()
                except discord.HTTPException:
                    coldcaller_logger.warning(
                        f"Couldn't unblock {user.name}#{user.discriminator} ({user.id}) as "
                        f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                    )
                    continue
                except Exception:
                    raise
                else:
                    coldcaller_logger.info(
                        f"Unblocked {user.name}#{user.discriminator} ({user.id}) as "
                        f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                    )
                finally:
                    await asyncio.sleep(10)


__all__: List[str] = [
    "unblock_all_as_all",
    "unblock_all",
    "verify_all",
    "verify_account",
    "leave_all",
    "leave_all_as_all",
    "get_logging_level"
]
