# EchoWorld — Submission Notes

## Project summary (150 words)

EchoWorld is a browser-playable RPG village where conversations become social consequences. Four villagers remember interactions, form attitudes, exchange gossip overnight, respond to confessions, and hold the player accountable for broken promises. Cognee provides the memory lifecycle: recall retrieves relevant context before dialogue, remember stores new interactions, improve consolidates each day, and forget supports bribery with dataset rotation as a fallback. A semantic analyzer separates verified facts from tone, preventing suspicious or hostile attitudes from inventing history. The Pygame world is packaged for browsers with Pygbag, while a FastAPI service keeps Cognee and OpenAI credentials server-side. Judges follow a tutorial that demonstrates fair trade, aggressive bargaining, deceptive denial, hearsay, confession, a no-trouble promise, promise violation, and Captain Mira's eventual callout. Visible Recall cards, Night Reports, attitude icons, and a village gathering animation make an invisible memory pipeline understandable, playable, and easy to evaluate in one session from a single public link.

## Five-step demo script

1. Follow the guide to praise Gareth and offer full price, then confront Petra over her prices.
2. Deny causing trouble when Mira questions you; inspect each temporary Recall card.
3. Press **N** to watch memory consolidation, village gossip, and the Night Report.
4. Ask Elder Voss what he has heard, then confess to Mira and make the no-trouble promise.
5. Trouble Petra again, end the day, and return to Mira to trigger the broken-promise consequence.

## Tech stack

- Python, Pygame CE, and Pygbag
- FastAPI and Uvicorn
- Cognee memory engine
- OpenAI dialogue and semantic interaction classification
- Render single-service deployment
- Local JSON/JSONL demo state

## Cognee usage

- `recall()` supplies relevant context before NPC speech.
- `remember()` persists conversations and analyzed interaction facts.
- `improve()` consolidates memory during the animated End Day sequence.
- `forget()` supports Bribe / Forget, with dataset rotation when Cloud deletion is unavailable.
- Recalled evidence is combined with attitudes, hearsay, confession, and promises while strict guards prevent fabricated personal memories.

## Judging highlights

- One public link; no local setup or browser-exposed secrets.
- Memory is visible through Recall notifications, attitude icons, gossip, and Night Reports.
- The promise flow demonstrates memory becoming a specific gameplay consequence.
- First-meeting, hearsay-gating, and verified-memory guards reduce hallucinated continuity.
- The guided tutorial reliably demonstrates the complete Cognee lifecycle in a few minutes.
