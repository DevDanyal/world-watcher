from __future__ import annotations

import httpx

from workers.base import WorkerContext


class PriceWorker:
    type = "price"

    def __init__(self, client: httpx.AsyncClient, limiter):
        self.client = client
        self.limiter = limiter

    async def run(self, ctx: WorkerContext) -> dict:
        symbol = (ctx.payload.get("symbol") or "bitcoin").lower()
        vs = (ctx.payload.get("vs") or "usd").lower()
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies={vs}&include_24hr_change=true"
        await ctx.report(20, f"rate limit {url}")
        await self.limiter.wait("api.coingecko.com")
        await ctx.report(50, f"fetching price {symbol}")
        r = await self.client.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        price = data.get(symbol, {}).get(vs)
        change = data.get(symbol, {}).get(f"{vs}_24h_change")
        await ctx.report(100, f"{symbol}={price} ({change}%)")
        return {"ok": True, "symbol": symbol, "vs": vs, "price": price, "change_24h": change}
