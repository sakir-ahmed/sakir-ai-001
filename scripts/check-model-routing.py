#!/usr/bin/env python3
"""Check OpenRouter key limits and optionally make a zero-price synthetic probe.

Run inside a service that already has OPENROUTER_API_KEY. Never prints credentials,
account identifiers, response bodies, private prompts or application conversations.
"""
import argparse
import json
import os
import urllib.error
import urllib.request


def request(path, body=None):
    key = os.environ.get('OPENROUTER_API_KEY')
    if not key:
        raise SystemExit('OPENROUTER_API_KEY is not configured in this process')
    req = urllib.request.Request('https://openrouter.ai/api/v1/' + path,
          data=json.dumps(body).encode() if body is not None else None,
          headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise SystemExit(f'OpenRouter HTTP {error.code}; response body omitted') from None
    except (urllib.error.URLError, ValueError):
        raise SystemExit('OpenRouter request/response failed; details omitted') from None


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--smoke',action='store_true',help='Consumes one free request, no paid fallback')
    args=parser.parse_args()
    data=request('key')['data']
    print(json.dumps({k:data.get(k) for k in ['is_free_tier','limit','limit_remaining','usage_daily','usage_monthly']}))
    if args.smoke:
        result=request('chat/completions',{'model':'openrouter/free',
            'messages':[{'role':'user','content':'Reply only with OK.'}], 'max_tokens':64,
            'provider':{'data_collection':'deny','require_parameters':True,
                        'max_price':{'prompt':0,'completion':0,'request':0}}, 'usage':{'include':True}})
        if 'error' in result:
            raise SystemExit('Free probe returned an error payload; details omitted')
        cost=(result.get('usage') or {}).get('cost')
        content=((result.get('choices') or [{}])[0].get('message') or {}).get('content')
        print(json.dumps({'selected_model':result.get('model'), 'cost_usd':cost, 'nonempty_response':bool(content)}))
        if cost is None or float(cost)!=0 or not content:
            raise SystemExit('Free probe did not establish usable zero-cost inference')
