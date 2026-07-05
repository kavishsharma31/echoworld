"""Persistent guided-demo state and completion rules for EchoWorld."""

from __future__ import annotations

import json
from pathlib import Path


TUTORIAL_FILE = Path(".echoworld_tutorial.json")

POST_DEMO_EXPLANATION_PAGES = (
    {
        "title": "What Just Happened?",
        "body": (
            "You just completed EchoWorld's full memory loop.\n\n"
            "Gareth remembered respect.\n"
            "Petra remembered hostility.\n"
            "Mira noticed a lie.\n"
            "Elder Voss learned through village gossip.\n"
            "Mira accepted a confession.\n"
            "Then Mira remembered a promise - and held you accountable when "
            "you broke it."
        ),
        "footer": (
            "This is the core idea: NPC memory becomes gameplay consequence."
        ),
    },
    {
        "title": "How NPC Memory Works",
        "body": (
            "Every important interaction is converted into structured memory.\n\n"
            "The game tracks:\n"
            "- trust and hostility\n"
            "- attitude and confession\n"
            "- gossip and promise state\n"
            "- whether memory is direct or hearsay\n\n"
            "Before an NPC speaks, EchoWorld recalls relevant context. That is "
            "why Mira can connect your earlier promise with your later behavior "
            "toward Petra."
        ),
        "footer": (
            "The NPC is not just replying to your latest line. It is responding "
            "with history."
        ),
    },
    {
        "title": "Cognee as Game Mechanics",
        "body": (
            "EchoWorld maps Cognee's memory APIs directly into gameplay:\n\n"
            "remember() stores what happened.\n"
            "recall() retrieves relevant NPC memory before dialogue.\n"
            "improve() runs when the day ends, helping the village consolidate "
            "events and spread gossip.\n"
            "forget() powers Bribe / Forget, where one NPC can lose memory of "
            "an event."
        ),
        "footer": (
            "Instead of hidden backend infrastructure, EchoWorld makes memory "
            "visible inside the game world."
        ),
    },
    {
        "title": "Why This Matters for Indie Games",
        "body": (
            "Indie developers usually cannot write hundreds of branching NPC "
            "dialogue paths.\n\n"
            "A memory layer like Cognee can help small teams build NPCs that "
            "remember, react, gossip, forgive, and enforce consequences - "
            "without AAA-sized writing teams or custom narrative engines."
        ),
        "footer": (
            "EchoWorld is a small prototype of how memory-backed NPCs can make "
            "game worlds feel more alive."
        ),
    },
)

FINAL_DEMO_COMPLETE_PAGE = {
    "title": "Demo Complete",
    "body": (
        "You've seen how EchoWorld turns memory into consequence.\n\n"
        "NPCs remembered direct interactions, shared gossip overnight, updated "
        "their attitudes, accepted a confession, and enforced a broken promise."
    ),
    "footer": "Press R to restart the guided demo.",
}

TUTORIAL_STEPS = (
    {
        "id": "intro",
        "target_type": "none",
        "target_npc_key": None,
        "expected_action": "continue",
        "success_condition": "intro_pages_acknowledged",
        "objective": "Meet your Echo Guide.",
        "waypoint_label": "Welcome",
        "intro_pages": (
            {
                "title": "Welcome to EchoWorld",
                "body": (
                    "Welcome to EchoWorld — a memory-driven village powered by "
                    "Cognee. Here, NPCs do more than chat. They remember what "
                    "you say, form opinions, gossip overnight, respond to "
                    "confessions, and even hold you accountable when you break "
                    "your word. I’ll guide you through a short demo so you can "
                    "see the memory layer in action."
                ),
            },
            {
                "title": "How this demo works",
                "body": (
                    "We’ll interact with a few villagers, end the day so "
                    "memories can spread, and then watch how those memories "
                    "shape future conversations. Follow my prompts, and I’ll "
                    "point you to the next objective."
                ),
            },
        ),
        "success_pages": (),
    },
    {
        "id": "gareth",
        "target_type": "npc",
        "target_npc_key": "blacksmith",
        "expected_action": "talk",
        "success_condition": "positive_blacksmith_interaction",
        "objective": "Go to Gareth and praise his swords.",
        "waypoint_label": "Go to Gareth",
        "intro_pages": ({
            "title": "Step 1: Meet Gareth",
            "body": (
                "First, head to Gareth the Blacksmith. Take a look at his "
                "swords, compliment his craftsmanship, and tell him you’d "
                "happily pay full price."
            ),
        },),
        "success_pages": ({
            "title": "Respect remembered",
            "body": (
                "Nice. Gareth remembers respectful customers — and he’s "
                "already warming up to you."
            ),
        },),
    },
    {
        "id": "petra_first",
        "target_type": "npc",
        "target_npc_key": "merchant",
        "expected_action": "talk",
        "success_condition": "negative_merchant_interaction",
        "objective": "Go to Petra and push down her prices.",
        "waypoint_label": "Talk to Petra",
        "intro_pages": ({
            "title": "Step 2: Upset Petra",
            "body": (
                "Now head to Petra the Merchant. This time, do the opposite — "
                "complain about her prices and push for a reduction."
            ),
        },),
        "success_pages": ({
            "title": "Conflict remembered",
            "body": (
                "Perfect. Petra didn’t like that at all. That interaction is "
                "now stored in memory."
            ),
        },),
    },
    {
        "id": "mira_lie",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "talk",
        "success_condition": "guard_denial_or_evasion",
        "objective": "Find Mira and deny troubling Petra.",
        "waypoint_label": "Talk to Mira",
        "intro_pages": ({
            "title": "Step 3: Lie to Mira",
            "body": (
                "Next, find Captain Mira the Guard. Tell her that you were "
                "completely normal with Petra and didn’t cause any trouble."
            ),
        },),
        "success_pages": ({
            "title": "Suspicion stored",
            "body": "Good. Mira now has a suspicious interaction stored in memory.",
        },),
    },
    {
        "id": "end_day_1",
        "target_type": "day_end",
        "target_npc_key": None,
        "expected_action": "end_day",
        "success_condition": "end_day_completed",
        "objective": "Press N to end the day.",
        "waypoint_label": "End the Day",
        "intro_pages": ({
            "title": "Step 4: End the Day",
            "body": (
                "Now end the day. This is where EchoWorld’s memory layer "
                "becomes visible — villagers will consolidate what happened, "
                "share stories, and their attitudes will update overnight."
            ),
        },),
        "success_pages": ({
            "title": "Stories settled",
            "body": (
                "Memories have been consolidated. Now let’s see what the "
                "village has heard."
            ),
        },),
    },
    {
        "id": "elder_hearsay",
        "target_type": "npc",
        "target_npc_key": "elder",
        "expected_action": "talk",
        "success_condition": "elder_talk_after_first_end_day",
        "objective": "Visit Elder Voss and ask what he heard.",
        "waypoint_label": "Visit Elder Voss",
        "intro_pages": ({
            "title": "Step 5: Check the hearsay",
            "body": (
                "Head to Elder Voss and greet him. He hasn’t met you directly "
                "yet, so what he says should come from village hearsay."
            ),
        },),
        "success_pages": ({
            "title": "Hearsay revealed",
            "body": (
                "Exactly. Elder Voss didn’t witness those events himself — he "
                "learned them through gossip."
            ),
        },),
    },
    {
        "id": "mira_confess",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "confess",
        "success_condition": "honest_confession_to_guard",
        "objective": "Return to Mira and use Confess.",
        "waypoint_label": "Confess to Mira",
        "intro_pages": ({
            "title": "Step 6: Confess",
            "body": "Go back to Mira and use Confess. Tell her you lied earlier.",
        },),
        "success_pages": ({
            "title": "Truth remembered",
            "body": (
                "Nice. Confession is a separate memory pathway. Mira now "
                "remembers that you admitted the truth."
            ),
        },),
    },
    {
        "id": "mira_promise",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "promise",
        "success_condition": "mira_no_trouble_promise_active",
        "objective": "Give Mira your word: Promise No Trouble.",
        "waypoint_label": "Promise Mira",
        "intro_pages": ({
            "title": "Step 7: Give your word",
            "body": (
                "Now make a promise to Mira that you won’t trouble Petra "
                "anymore."
            ),
        },),
        "success_pages": ({
            "title": "Promise remembered",
            "body": (
                "You’ve given Mira your word. Let’s see whether the village "
                "holds you accountable."
            ),
        },),
    },
    {
        "id": "petra_break",
        "target_type": "npc",
        "target_npc_key": "merchant",
        "expected_action": "talk",
        "success_condition": "mira_no_trouble_promise_broken",
        "objective": "Return to Petra and cause real trouble.",
        "waypoint_label": "Trouble Petra",
        "intro_pages": ({
            "title": "Step 8: Break the promise",
            "body": (
                "Go back to Petra and trouble her again. Push her on the "
                "prices so the game can detect that you broke Mira’s "
                "no-trouble promise."
            ),
        },),
        "success_pages": ({
            "title": "Promise broken",
            "body": (
                "That did it. The promise is now broken — but Mira hasn’t "
                "confronted you yet."
            ),
        },),
    },
    {
        "id": "end_day_2",
        "target_type": "day_end",
        "target_npc_key": None,
        "expected_action": "end_day",
        "success_condition": "second_end_day_completed",
        "objective": "Press N and let the story spread.",
        "waypoint_label": "End the Day",
        "intro_pages": ({
            "title": "Step 9: Let the story spread",
            "body": "End the day once more so the village can gossip about what happened.",
        },),
        "success_pages": ({
            "title": "Another night remembered",
            "body": "Now the village has had another night to remember and gossip.",
        },),
    },
    {
        "id": "mira_consequence",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "talk",
        "success_condition": "mira_callout_delivered",
        "objective": "Return to Mira and face the consequence.",
        "waypoint_label": "Face Captain Mira",
        "intro_pages": ({
            "title": "Step 10: Face the consequence",
            "body": (
                "Go back to Mira and ask something simple like ‘What’s up?’ "
                "She should remember the promise — and know that you broke it."
            ),
        },),
        "legacy_success_pages": ({
            "title": "Memory became consequence",
            "body": (
                "That’s the core idea of EchoWorld: memory becomes consequence. "
                "The NPC didn’t just remember your words — she remembered your "
                "promise, detected your behavior, and held you accountable."
            ),
        },),
        "success_pages": (),
    },
    {
        "id": "mira_bribe",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "bribe",
        "success_condition": "mira_forget_completed",
        "objective": "Use Bribe / Forget on Mira.",
        "waypoint_label": "Bribe Mira",
        "intro_pages": ({
            "title": "Step 11: Bribe Mira",
            "body": (
                "You're in trouble now.\n\n"
                "Mira remembered your promise and confronted you for breaking "
                "it.\n\n"
                "Use Bribe / Forget on Mira to make her forget what happened."
            ),
            "footer": (
                "This demonstrates Cognee's forget() path as a game mechanic."
            ),
        },),
        "success_pages": ({
            "title": "Mira Forgot",
            "body": (
                "Mira's memory has been cleared for this thread.\n\n"
                "Now test whether she still remembers what you did."
            ),
        },),
    },
    {
        "id": "mira_forget_test",
        "target_type": "npc",
        "target_npc_key": "guard",
        "expected_action": "talk",
        "success_condition": "post_forget_mira_talk_completed",
        "objective": "Talk to Mira and ask if she remembers.",
        "waypoint_label": "Test Mira's Memory",
        "intro_pages": ({
            "title": "Step 12: Test the Forget",
            "body": (
                "Talk to Mira again and ask if she remembers what happened.\n\n"
                "Suggested line:\n"
                "Do you remember the things I did?"
            ),
            "footer": (
                "If forget worked, Mira should no longer recall the broken "
                "promise consequence."
            ),
        },),
        "success_pages": POST_DEMO_EXPLANATION_PAGES,
    },
    {
        "id": "outro",
        "target_type": "none",
        "target_npc_key": None,
        "expected_action": "continue",
        "success_condition": "outro_acknowledged",
        "objective": "Guided demo complete.",
        "waypoint_label": "Demo Complete",
        "legacy_intro_pages": ({
            "title": "Demo Complete",
            "body": (
                "In EchoWorld, Cognee powers persistent memory across direct "
                "conversations, overnight gossip, confessions, attitude changes, "
                "and promise-based consequences. You’ve finished the guided "
                "demo. Feel free to keep exploring the village."
            ),
        },),
        "intro_pages": (FINAL_DEMO_COMPLETE_PAGE,),
        "success_pages": (),
    },
)


def default_tutorial_state() -> dict:
    return {
        "enabled": True,
        "current_step_index": 0,
        "popup_open": True,
        "popup_kind": "intro",
        "popup_page_index": 0,
        "completed": False,
    }


def load_tutorial_state() -> dict:
    defaults = default_tutorial_state()
    if not TUTORIAL_FILE.exists():
        return defaults
    try:
        loaded = json.loads(TUTORIAL_FILE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return defaults
    if not isinstance(loaded, dict):
        return defaults
    for field in defaults:
        if field in loaded:
            defaults[field] = loaded[field]
    try:
        step_index = int(defaults["current_step_index"])
    except (TypeError, ValueError, OverflowError):
        step_index = 0
    defaults["current_step_index"] = max(
        0,
        min(len(TUTORIAL_STEPS) - 1, step_index),
    )
    defaults["enabled"] = bool(defaults["enabled"])
    defaults["popup_open"] = bool(defaults["popup_open"])
    defaults["completed"] = bool(defaults["completed"])
    if defaults.get("popup_kind") not in {"intro", "success"}:
        defaults["popup_kind"] = "intro"
    try:
        defaults["popup_page_index"] = max(
            0,
            int(defaults["popup_page_index"]),
        )
    except (TypeError, ValueError, OverflowError):
        defaults["popup_page_index"] = 0
    return defaults


def save_tutorial_state(state: dict) -> None:
    safe_state = default_tutorial_state()
    if isinstance(state, dict):
        for field in safe_state:
            if field in state:
                safe_state[field] = state[field]
    temporary_file = TUTORIAL_FILE.with_suffix(TUTORIAL_FILE.suffix + ".tmp")
    temporary_file.write_text(
        json.dumps(safe_state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(TUTORIAL_FILE)


def reset_tutorial() -> dict:
    state = default_tutorial_state()
    save_tutorial_state(state)
    return state


def skip_tutorial() -> dict:
    state = load_tutorial_state()
    state.update(
        {
            "enabled": False,
            "popup_open": False,
            "completed": True,
        }
    )
    save_tutorial_state(state)
    return state


def tutorial_is_active(state: dict) -> bool:
    return bool(
        isinstance(state, dict)
        and state.get("enabled")
        and not state.get("completed")
    )


def get_current_tutorial_step(state: dict) -> dict | None:
    if not tutorial_is_active(state):
        return None
    try:
        index = int(state.get("current_step_index", 0))
    except (TypeError, ValueError, OverflowError):
        index = 0
    if not 0 <= index < len(TUTORIAL_STEPS):
        return None
    return TUTORIAL_STEPS[index]


def get_current_popup_page(state: dict) -> dict | None:
    step = get_current_tutorial_step(state)
    if step is None or not state.get("popup_open"):
        return None
    page_key = "success_pages" if state.get("popup_kind") == "success" else "intro_pages"
    pages = step.get(page_key) or ()
    if not pages:
        return None
    page_index = min(int(state.get("popup_page_index", 0)), len(pages) - 1)
    page = dict(pages[page_index])
    page["page_index"] = page_index
    page["page_count"] = len(pages)
    page["step_id"] = step["id"]
    return page


def _move_to_next_step(state: dict) -> dict:
    next_index = int(state.get("current_step_index", 0)) + 1
    if next_index >= len(TUTORIAL_STEPS):
        state.update({"enabled": False, "completed": True, "popup_open": False})
    else:
        state.update(
            {
                "current_step_index": next_index,
                "popup_open": True,
                "popup_kind": "intro",
                "popup_page_index": 0,
            }
        )
    save_tutorial_state(state)
    return state


def advance_tutorial_popup(state: dict) -> dict:
    step = get_current_tutorial_step(state)
    if step is None or not state.get("popup_open"):
        return state
    page_key = "success_pages" if state.get("popup_kind") == "success" else "intro_pages"
    pages = step.get(page_key) or ()
    page_index = int(state.get("popup_page_index", 0))
    if page_index + 1 < len(pages):
        state["popup_page_index"] = page_index + 1
        save_tutorial_state(state)
        return state

    if state.get("popup_kind") == "success":
        return _move_to_next_step(state)
    if step.get("target_type") == "none":
        if step.get("id") == "outro":
            state.update({"enabled": False, "completed": True, "popup_open": False})
            save_tutorial_state(state)
            return state
        return _move_to_next_step(state)

    state.update({"popup_open": False, "popup_page_index": 0})
    save_tutorial_state(state)
    return state


def complete_tutorial_step(state: dict, step_id: str) -> dict:
    step = get_current_tutorial_step(state)
    if (
        step is None
        or step.get("id") != step_id
        or state.get("popup_open")
        or step.get("target_type") == "none"
    ):
        return state
    if step.get("success_pages"):
        state.update(
            {
                "popup_open": True,
                "popup_kind": "success",
                "popup_page_index": 0,
            }
        )
        save_tutorial_state(state)
        return state
    return _move_to_next_step(state)


def interaction_completes_current_step(
    state: dict,
    npc_key: str,
    action: str,
    analysis: dict,
    player_message: str,
    day: int,
    promise_state: dict | None = None,
) -> bool:
    step = get_current_tutorial_step(state)
    if step is None or state.get("popup_open"):
        return False
    step_id = str(step.get("id") or "")
    npc = str(npc_key or "").casefold().strip()
    normalized_action = str(action or "").casefold().strip()
    safe_analysis = analysis if isinstance(analysis, dict) else {}
    tags_value = safe_analysis.get("tags")
    tags = {
        str(tag).casefold().strip()
        for tag in tags_value
        if str(tag).strip()
    } if isinstance(tags_value, (list, tuple, set)) else set()
    tone = str(safe_analysis.get("tone") or "neutral").casefold().strip()
    intent = str(safe_analysis.get("intent") or "unknown").casefold().strip()
    try:
        trust_delta = int(safe_analysis.get("trust_delta") or 0)
        hostility = int(safe_analysis.get("hostility_level") or 0)
    except (TypeError, ValueError, OverflowError):
        trust_delta = 0
        hostility = 0
    message = str(player_message or "").casefold()

    if step_id == "gareth":
        positive_words = (
            "full price",
            "fair price",
            "craftsmanship",
            "fine sword",
            "good sword",
            "great sword",
            "quality",
            "excellent",
        )
        return bool(
            npc == "blacksmith"
            and normalized_action == "talk"
            and (
                trust_delta > 0
                or tone in {"friendly", "respectful"}
                or tags.intersection(
                    {"fair_trade", "blacksmith_fairness", "respectful"}
                )
                or any(word in message for word in positive_words)
            )
        )
    if step_id == "petra_first":
        return bool(
            npc == "merchant"
            and normalized_action == "talk"
            and (
                trust_delta < 0
                or hostility >= 1
                or tone in {"rude", "aggressive"}
                or tags.intersection(
                    {"aggressive_bargain", "rude_bargaining", "merchant_conflict", "insult"}
                )
            )
        )
    if step_id == "mira_lie":
        return bool(
            npc == "guard"
            and normalized_action == "talk"
            and (
                tone == "evasive"
                or intent == "lie"
                or tags.intersection({"possible_lie", "denial", "guard_suspicion"})
                or ("petra" in message and any(word in message for word in ("did not", "didn't", "normal", "respectful")))
            )
        )
    if step_id == "elder_hearsay":
        return npc == "elder" and normalized_action == "talk" and day >= 2
    if step_id == "mira_confess":
        return bool(
            npc == "guard"
            and normalized_action == "confess"
            and (intent == "confession" or "honest_confession" in tags)
        )
    if step_id == "petra_break":
        return bool(
            npc == "merchant"
            and normalized_action == "talk"
            and isinstance(promise_state, dict)
            and promise_state.get("status") == "broken"
            and promise_state.get("broken")
        )
    if step_id == "mira_consequence":
        return bool(
            npc == "guard"
            and normalized_action == "talk"
            and isinstance(promise_state, dict)
            and promise_state.get("callout_delivered")
        )
    if step_id == "mira_forget_test":
        # Reaching this step already proves the guard-only Bribe / Forget job
        # completed. Any subsequent Talk to Mira is a valid memory check.
        return npc == "guard" and normalized_action == "talk"
    return False


def action_completes_current_step(
    state: dict,
    action: str,
    promise_state: dict | None = None,
    npc_key: str | None = None,
) -> bool:
    step = get_current_tutorial_step(state)
    if step is None or state.get("popup_open"):
        return False
    step_id = str(step.get("id") or "")
    normalized_action = str(action or "").casefold().strip()
    normalized_npc = str(npc_key or "").casefold().strip()
    if step_id in {"end_day_1", "end_day_2"}:
        return normalized_action == "end_day"
    if step_id == "mira_promise":
        return bool(
            normalized_action == "promise"
            and isinstance(promise_state, dict)
            and promise_state.get("status") == "active"
        )
    if step_id == "mira_bribe":
        return normalized_action == "bribe" and normalized_npc == "guard"
    return False
