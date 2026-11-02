"""Exercise model routing against fake HTTP, with no live provider credentials."""
import json
from unittest.mock import AsyncMock
import httpx
import pytest
from app.config import Settings
from app.llm import LLM, LLMError, BudgetExceeded


def config(**overrides):
    return Settings({'routing': {'free_first': True, 'free_models': ['openrouter/free'], 'allow_paid': True,
                                'paid_purposes': ['reply_premium'], 'max_attempts': 2, **overrides},
                     'models': {'paid_fallback': {'id': 'cheap/paid', 'price_in': .1, 'price_out': .4},
                                'reply_premium': {'id': 'strong/paid', 'price_in': .3, 'price_out': .5}},
                     'budget': {'monthly_usd': 1}})


def answer(content='hello', cost=0):
    return httpx.Response(200,json={'choices':[{'message':{'content':content}}],
                                    'usage':{'prompt_tokens':10,'completion_tokens':5,'cost':cost}})


async def make(handler, spent=0, **options):
    db=AsyncMock(); db.month_spend.return_value=spent; db.get_setting.return_value=False
    llm=LLM('fake',config(**options),db)
    await llm.http.aclose()
    llm.http=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return llm,db


@pytest.mark.asyncio
async def test_free_then_rate_limit_fallback_and_cooldown():
    seen=[]
    def handler(req):
        body=json.loads(req.content); seen.append(body)
        if body['model']=='openrouter/free': return httpx.Response(429,headers={'Retry-After':'120'})
        return answer(cost=.001)
    llm,db=await make(handler)
    try:
        for _ in range(2): assert await llm.chat('reply',[])=='hello'
        assert [x['model'] for x in seen]==['openrouter/free','cheap/paid','cheap/paid']
        assert seen[0]['provider']['max_price']=={'prompt':0,'completion':0,'request':0}
        assert seen[0]['provider']['data_collection']=='deny'
        assert db.add_spend.await_count==2
    finally: await llm.close()


@pytest.mark.asyncio
async def test_free_success_does_not_spend_on_paid():
    seen=[]
    def handler(req): seen.append(json.loads(req.content)['model']); return answer()
    llm,db=await make(handler)
    try:
        assert await llm.chat('reply',[])=='hello'
        assert seen==['openrouter/free']
        db.add_spend.assert_awaited_once_with('reply',0.,10,5)
    finally: await llm.close()


@pytest.mark.asyncio
async def test_free_only_even_for_complex_purpose():
    seen=[]
    def handler(req): seen.append(json.loads(req.content)['model']); return httpx.Response(429)
    llm,_=await make(handler,allow_paid=False)
    try:
        with pytest.raises(LLMError): await llm.chat('reply_premium',[])
        with pytest.raises(LLMError): await llm.chat('reply',[])
        assert seen==['openrouter/free']
    finally: await llm.close()


@pytest.mark.asyncio
async def test_only_explicit_complex_purpose_selects_stronger_model():
    seen=[]
    def handler(req): seen.append(json.loads(req.content)['model']); return answer(cost=.001)
    llm,_=await make(handler)
    try:
        await llm.chat('reply_premium',[])
        assert seen==['strong/paid']
    finally: await llm.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('code',[400,401,402,403])
async def test_no_paid_failover_for_auth_billing_moderation(code):
    seen=[]
    def handler(req): seen.append(req); return httpx.Response(code,text='private prompt')
    llm,_=await make(handler)
    try:
        with pytest.raises(LLMError) as exc: await llm.chat('reply',[])
        assert 'private prompt' not in str(exc.value)
        assert len(seen)==1
    finally: await llm.close()


@pytest.mark.asyncio
async def test_malformed_json_is_accounted_before_retry():
    seen=[]
    def handler(req):
        name=json.loads(req.content)['model']; seen.append(name)
        return answer('not JSON') if name=='openrouter/free' else answer('{"intent":"faq"}',.001)
    llm,db=await make(handler)
    try:
        assert json.loads(await llm.chat('classify',[],json_mode=True))['intent']=='faq'
        assert len(seen)==2 and db.add_spend.await_count==2
    finally: await llm.close()


@pytest.mark.asyncio
async def test_paid_budget_does_not_disable_free():
    def handler(req):
        assert json.loads(req.content)["model"] == "openrouter/free"
        return answer()
    llm,_=await make(handler,spent=1)
    try:
        assert await llm.chat('reply',[]) == 'hello'
        assert not await llm.over_budget()
    finally: await llm.close()


@pytest.mark.asyncio
async def test_reserve_prevents_paid_overshoot():
    seen=[]
    def handler(req): seen.append(json.loads(req.content)['model']); return httpx.Response(503)
    llm,_=await make(handler,spent=.999999)
    try:
        with pytest.raises(LLMError): await llm.chat('reply',[{'role':'user','content':'x'*1000}])
        assert seen==['openrouter/free']
    finally: await llm.close()


@pytest.mark.asyncio
async def test_bounded_attempts():
    seen=[]
    def handler(req): seen.append(req); return httpx.Response(503)
    llm,_=await make(handler)
    try:
        with pytest.raises(LLMError): await llm.chat('reply',[])
        assert len(seen)==2
    finally: await llm.close()


@pytest.mark.asyncio
async def test_oversized_prompt_never_calls_provider():
    def handler(_): raise AssertionError('No request expected')
    llm,_=await make(handler,max_input_bytes=10)
    try:
        with pytest.raises(LLMError,match='input size'):
            await llm.chat('reply',[{'role':'user','content':'a'*100}])
    finally: await llm.close()
