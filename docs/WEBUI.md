# Private local-model chat interface

Open WebUI is the selected first interface: it connects to existing Ollama,
supports conversation history and streaming responses, and adds no required
paid inference provider. It is a chat interface; it does not by itself show
Hermes task execution or implement durable agent coordination.

The optional `compose.webui.yml` pins official release v0.12.5 and uses the
already installed `qwen2.5:1.5b`. The small CPU model is a starting point;
Bengali quality and latency require acceptance testing. Cloud-provider access
starts disabled. The owner can enable OpenAI-compatible connections in Admin
Settings → Connections and privately configure OpenRouter/OpenAI or another
supported provider. Ollama remains the default; selecting paid models incurs
provider charges. Automatic complex-task paid escalation is not implemented here.
Existing sales routing and Hermes remain independent and unchanged.

## Install and onboard

1. Run `sudo bash scripts/setup-webui.sh` from the committed source clone.
   It backs up first, refuses existing containers or occupied ports, and adds
   only `sakir_ai_001_webui` with persistent data under the existing backup tree.
2. Verify `curl --fail http://127.0.0.1:8082/health` and confirm the listener is
   loopback-only. Host networking reaches the existing loopback Ollama API.
3. The owner can run `python3 scripts/create-webui-admin.py` directly in the
   connected server terminal and enter their email/password privately. Alternatively,
   use a private SSH tunnel to server port 8082 and create the first account there.
   Do not publish an unclaimed first-admin signup page.
4. Disable further signups in the administrator settings after account creation.
5. Test a Bengali and an English conversation and refresh to verify history.
6. Only after onboarding, run `sudo python3 scripts/publish-webui.py ai001.sakir.bd`
   to add NGINX WebSocket forwarding to the existing HTTPS site, then verify login. Do not overwrite existing webhook
   routes or expose Ollama directly. Container updates need approval because
   recreation removes the prior container.

## Remaining work

- [x] Deploy and verify UI health and local model discovery.
- [x] Owner creates administrator; disable subsequent signups.
- [x] HTTPS login page published through NGINX; authenticated chat acceptance remains pending.
- [ ] Bengali text quality and CPU latency acceptance.
- [ ] Repair existing STT before connecting Bengali voice input.
- [ ] Test existing TTS and browser microphone consent.
- [ ] Add actual Hermes task progress and cancellation through bounded APIs.
- [ ] Implement explicit complex-task routing without routine paid requests.

References: [official installation guide](https://docs.openwebui.com/getting-started/quick-start/),
[official container startup](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/start.sh).

## Live evidence — 2026-11-02

- Encrypted 167 MB backup completed before deployment; off-site copy remains deferred.
- Official image v0.12.5 pulled and `sakir_ai_001_webui` started.
- UI page returned HTTP 200; `/health` returned `{"status": true}`.
- Listener verified on `127.0.0.1:8082` only.
- Live NGINX `server_name ai001.sakir.bd` and certificate paths confirmed;
  `nginx -t` passed. Existing webhook/media routes remain unchanged.
- Owner created administrator privately in Termius. Public `/api/config` confirms
  onboarding false, auth true and signup false; unauthenticated model requests return 401.
- NGINX root now proxies to Open WebUI with WebSocket support. Public root and
  all linked application assets returned HTTP 200 with appropriate content types;
  invalid-token Meta webhook still returned 403. User reported seeing the login form.
- Independently observed signed-in browser with qwen2.5:1.5b selected; the
  owner greeting received a completed response. UI timing reported total 23.68 s,
  model load 4.22 s, prompt evaluation 15.17 s (2,050 tokens), generation 1.22 s
  (17 tokens, 13.99 tokens/s). This was a completed CPU request, not a stalled proxy.
- Voice quality, other-provider credentials and automatic escalation remain unverified.
