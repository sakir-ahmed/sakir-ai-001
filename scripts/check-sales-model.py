#!/usr/bin/env python3
"""Free-only smoke check of the deployed sales LLM and spend accounting.

Run inside dt-assistant. Uses one synthetic prompt, records its usage normally,
and disables paid fallback in memory for this probe only. No customer sends.
"""
import asyncio
from app.config import load_secrets, load_settings
from app.db import Database
from app.llm import LLM


async def check():
    secrets, settings = load_secrets(), load_settings()
    assert settings.get('routing','free_first'), 'Free-first policy is not active'
    settings.raw['routing']['allow_paid'] = False
    db=Database(secrets.database_url)
    await db.connect()
    model=LLM(secrets.openrouter_key,settings,db)
    try:
        before=await db.month_spend()
        text=await model.chat('cost_smoke',[{'role':'user','content':'Reply only with OK.'}],max_tokens=128)
        after=await db.month_spend()
        assert text and abs(after-before)<1e-9, 'Probe did not establish zero-cost inference'
        print('DEPLOYED_FREE_ROUTE_PASS nonempty=True incremental_cost_usd=0 paid_fallback_for_probe=False')
    finally:
        await model.close()
        await db.close()


if __name__=='__main__':
    asyncio.run(check())
