# Private local-model chat interface

Open WebUI is the selected first interface: it connects to existing Ollama,
supports conversation history and streaming responses, and adds no required
paid inference provider. It is a chat interface; it does not by itself show
Hermes task execution or implement durable agent coordination.

The optional `compose.webui.yml` pins official release v0.12.5 and uses the
already installed `qwen2.5:1.5b`. The small CPU model is a starting point;
Bengali quality and latency require acceptance testing. Cloud-provider access
is disabled in this UI; complex-task paid escalation is not implemented here.
Existing sales routing and Hermes remain independent and unchanged.

## Install and onboard

1. Run `sudo bash scripts/setup-webui.sh` from the committed source clone.
   It backs up first, refuses existing containers or occupied ports, and adds
   only `sakir_ai_001_webui` with persistent data under the existing backup tree.
2. Verify `curl --fail http://127.0.0.1:8082/health` and confirm the listener is
   loopback-only. Host networking reaches the existing loopback Ollama API.
3. Use a private SSH tunnel to server port 8082, then open the forwarded local
   address. The owner must create the first administrator account privately.
   Do not publish an unclaimed first-admin signup page.
4. Disable further signups in the administrator settings after account creation.
5. Test a Bengali and an English conversation and refresh to verify history.
6. Only after onboarding, configure an approved HTTPS hostname with NGINX
   WebSocket forwarding and verify login. Do not overwrite existing webhook
   routes or expose Ollama directly. Container updates need approval because
   recreation removes the prior container.

## Remaining work

- [ ] Deploy and verify UI health and local model discovery.
- [ ] Owner creates administrator; disable subsequent signups.
- [ ] Authenticated HTTPS access through NGINX.
- [ ] Bengali text quality and CPU latency acceptance.
- [ ] Repair existing STT before connecting Bengali voice input.
- [ ] Test existing TTS and browser microphone consent.
- [ ] Add actual Hermes task progress and cancellation through bounded APIs.
- [ ] Implement explicit complex-task routing without routine paid requests.

References: [official installation guide](https://docs.openwebui.com/getting-started/quick-start/),
[official container startup](https://github.com/open-webui/open-webui/blob/v0.12.5/backend/start.sh).
