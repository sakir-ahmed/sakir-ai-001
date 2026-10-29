---
name: remember
description: Save a fact Sakir tells you into the knowledge inbox for him to review, and search the knowledge base. Use for "/remember", "remember that", "note this", "what do we know about".
---
# Remember and look up

## Save
```bash
python3 /opt/sakir-tools/sakir.py kb remember "<the fact, one line, with date if relevant>"
```
Then tell Sakir: saved to the inbox; agents use it only after he moves it into
the right knowledge file (e.g. a price into products/dt-restora/pricing.md).
Suggest the exact file.

## Search
Collections: `restora` (product, company, sales), `me` (profile, CV, goals), `ops` (servers).
```bash
python3 /opt/sakir-tools/sakir.py kb search restora "<question>"
```
Answer from the returned text and cite the file name. If nothing relevant comes
back, say the knowledge base does not have it yet.
