import asyncio
import threading
from pathlib import Path
from uuid import uuid4

import streamlit as st

from event_log import build_elder_hearsay_from_events, get_all_events
from map_state import DEFAULT_PLAYER_POS, get_nearby_npc, map_to_text, move_player
from npcs import npc_speak
from world import bribe_npc, end_day


st.set_page_config(page_title="EchoWorld", layout="wide")

NPC_DISPLAY_NAMES = {
    "blacksmith": "Gareth the Blacksmith",
    "guard": "Captain Mira the Guard",
    "merchant": "Petra the Merchant",
    "elder": "Elder Voss",
}


@st.cache_resource
def get_async_loop():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    return loop


def run_async(coro):
    loop = get_async_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def reset_demo_run():
    st.session_state.dialogue_log = []
    st.session_state.player_pos = DEFAULT_PLAYER_POS.copy()
    st.session_state.day = 1
    st.session_state.session_id = "echoworld_streamlit_day_1"
    st.session_state.last_api_event = (
        "Demo state reset. Cognee memories are isolated through dataset rotation / "
        "existing backend."
    )
    st.session_state.player_input = ""

    try:
        Path(".echoworld_events.jsonl").unlink(missing_ok=True)
    except OSError as exc:
        st.session_state["_demo_reset_error"] = (
            f"Demo UI state reset, but the local event log could not be cleared: {exc}"
        )
        st.session_state.pop("_demo_reset_success", None)
    else:
        st.session_state["_demo_reset_success"] = True
        st.session_state.pop("_demo_reset_error", None)


if "player_pos" not in st.session_state:
    st.session_state.player_pos = DEFAULT_PLAYER_POS.copy()
if "day" not in st.session_state:
    st.session_state.day = 1
if "session_id" not in st.session_state:
    st.session_state.session_id = "echoworld_streamlit_day_1"
if "dialogue_log" not in st.session_state:
    st.session_state.dialogue_log = []
if "last_api_event" not in st.session_state:
    st.session_state.last_api_event = "No Cognee API used yet."
if "player_input" not in st.session_state:
    st.session_state.player_input = ""

st.markdown(
    """
    <style>
        .stApp {
            background: linear-gradient(145deg, #111713 0%, #1b2119 55%, #211914 100%);
            color: #eee6d2;
        }
        [data-testid="stHeader"] {
            background: rgba(17, 23, 19, 0.75);
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: rgba(38, 43, 33, 0.82);
            border: 1px solid #6e6546;
            border-radius: 12px;
            box-shadow: 0 5px 16px rgba(0, 0, 0, 0.22);
        }
        [data-testid="stCodeBlock"] code {
            font-family: "Cascadia Mono", "Courier New", monospace;
            font-size: 1.5rem;
            line-height: 1.75;
        }
        .stButton > button {
            min-height: 2.6rem;
            border: 1px solid #8d7b4f;
            border-radius: 8px;
            background: #3b3929;
            color: #fff6dc;
            font-weight: 650;
        }
        .stButton > button:hover {
            border-color: #d6b96d;
            color: #fff4c5;
        }
        .echo-subtitle {
            margin-top: -0.8rem;
            margin-bottom: 1.25rem;
            color: #c9bea4;
            font-size: 1.05rem;
        }
        .dialogue-entry {
            margin: 0.45rem 0;
            padding: 0.7rem 0.85rem;
            border-left: 3px solid #aa8f51;
            border-radius: 5px;
            background: rgba(20, 24, 19, 0.72);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("EchoWorld")
st.markdown(
    '<p class="echo-subtitle">A tiny RPG village where NPCs remember, gossip, and forget using Cognee.</p>',
    unsafe_allow_html=True,
)
st.info(
    "For demo stability, Show Memory uses the fast local debug log. Live NPC "
    "behavior still uses the EchoWorld memory engine and Cognee lifecycle calls."
)

with st.sidebar:
    st.header("Demo Controls")
    st.button(
        "Reset Demo Run",
        type="primary",
        use_container_width=True,
        on_click=reset_demo_run,
    )
    st.caption(
        "Resets the UI and local event log only. Remote Cognee datasets are left "
        "untouched."
    )
    if st.session_state.pop("_demo_reset_success", False):
        st.success("Demo run reset. Local event history cleared.")
    reset_error = st.session_state.pop("_demo_reset_error", None)
    if reset_error:
        st.error(reset_error)

    st.divider()
    st.subheader("Suggested Judge Flow")
    st.markdown(
        "1. Walk to Gareth and buy a sword fairly.\n"
        "2. Walk to Petra and demand a discount rudely.\n"
        "3. Walk to Mira and deny arguing with Petra.\n"
        "4. Click **End Day** to run `improve()` and gossip.\n"
        "5. Walk to Elder Voss and ask what he thinks of you.\n"
        "6. Bribe Mira so she forgets.\n"
        "7. Ask Mira if she remembers accusing you.\n"
        "8. Ask Elder what he has heard."
    )

left_col, center_col, right_col = st.columns([1.15, 1, 0.9], gap="large")

with left_col:
    with st.container(border=True):
        st.subheader("Village Map")
        st.code(map_to_text(st.session_state.player_pos), language=None)

        st.markdown("##### Movement")
        up_left, up_col, up_right = st.columns(3)
        with up_col:
            move_up = st.button("⬆️ Up", use_container_width=True)

        left_move_col, spacer_col, right_move_col = st.columns(3)
        with left_move_col:
            move_left = st.button("⬅️ Left", use_container_width=True)
        with spacer_col:
            st.markdown("<div style='height: 2.6rem'></div>", unsafe_allow_html=True)
        with right_move_col:
            move_right = st.button("Right ➡️", use_container_width=True)

        down_left, down_col, down_right = st.columns(3)
        with down_col:
            move_down = st.button("⬇️ Down", use_container_width=True)

        direction = None
        if move_up:
            direction = "up"
        elif move_left:
            direction = "left"
        elif move_right:
            direction = "right"
        elif move_down:
            direction = "down"

        if direction:
            st.session_state.player_pos = move_player(
                st.session_state.player_pos, direction
            )
            st.rerun()

        st.markdown(
            "**Legend**  \n"
            "🧍 player · ⚒️ Gareth · 🛡️ Mira  \n"
            "🏪 Petra · 🧙 Elder Voss"
        )

nearby_npc = get_nearby_npc(st.session_state.player_pos)
nearby_name = NPC_DISPLAY_NAMES.get(nearby_npc, "None")

with center_col:
    with st.container(border=True):
        st.subheader("Nearby NPC")
        if nearby_npc is None:
            st.info("Walk up to an NPC to interact.")
        else:
            st.success(f"Nearby: {nearby_name}")
            with st.form("talk_form", clear_on_submit=True):
                player_message = st.text_input(
                    f"Say something to {nearby_name}",
                    key="player_input",
                )
                talk_selected = st.form_submit_button(
                    "Send / Talk",
                    use_container_width=True,
                )

            if talk_selected:
                message = player_message.strip()
                if not message:
                    st.warning("Enter a message before talking to the NPC.")
                else:
                    st.session_state.dialogue_log.append(
                        f"You → {nearby_name}: {message}"
                    )
                    try:
                        with st.spinner(f"{nearby_name} is remembering and replying..."):
                            reply = run_async(
                                npc_speak(
                                    nearby_npc,
                                    message,
                                    st.session_state.session_id,
                                )
                            )
                    except Exception as exc:
                        error_message = f"Talk failed for {nearby_name}: {exc}"
                        st.error(error_message)
                        st.session_state.dialogue_log.append(error_message)
                        st.session_state.last_api_event = (
                            "Talk failed before the Cognee memory cycle completed."
                        )
                    else:
                        st.session_state.dialogue_log.append(
                            f"{nearby_name}: {reply}"
                        )
                        st.session_state.last_api_event = (
                            "recall() retrieved NPC memory; remember() stored "
                            "the new interaction."
                        )

            bribe_col, memory_col = st.columns(2)
            with bribe_col:
                if st.button("Bribe", use_container_width=True):
                    try:
                        with st.spinner(f"Attempting to alter {nearby_name}'s memory..."):
                            bribe_result = run_async(bribe_npc(nearby_npc))
                    except Exception as exc:
                        error_message = f"Bribe failed for {nearby_name}: {exc}"
                        st.error(error_message)
                        st.session_state.dialogue_log.append(error_message)
                        st.session_state.last_api_event = (
                            "Bribe failed before forget() or dataset rotation completed."
                        )
                    else:
                        st.session_state.dialogue_log.append(str(bribe_result))
                        st.session_state.session_id = (
                            f"echoworld_after_bribe_{uuid4().hex[:8]}"
                        )
                        st.session_state.last_api_event = (
                            "forget() was attempted; if Cloud deletion failed, dataset "
                            "rotation isolated a fresh NPC memory."
                        )
            with memory_col:
                if st.button("Show Memory", use_container_width=True):
                    try:
                        if nearby_npc == "elder":
                            elder_memory = build_elder_hearsay_from_events()
                            st.session_state.dialogue_log.append(
                                elder_memory
                                or "No local debug memory found for this NPC."
                            )
                            st.session_state.last_api_event = (
                                "Fast debug memory shown from event log; Elder dialogue "
                                "still uses Cognee + deterministic hearsay context."
                            )
                        else:
                            direct_events = [
                                event
                                for event in get_all_events()
                                if event.get("npc_key") == nearby_npc
                            ]
                            if not direct_events:
                                memory_message = (
                                    "No local debug memory found for this NPC."
                                )
                            else:
                                recent_interactions = []
                                for event in direct_events[-5:]:
                                    event_message = str(
                                        event.get("player_message") or ""
                                    ).strip()
                                    event_reply = str(
                                        event.get("npc_reply") or ""
                                    ).strip()
                                    recent_interactions.append(
                                        f"**You:** {event_message}\n\n"
                                        f"**{nearby_name}:** {event_reply}"
                                    )
                                memory_message = (
                                    f"Recent local interactions with {nearby_name}:\n\n"
                                    + "\n\n---\n\n".join(recent_interactions)
                                )
                            st.session_state.dialogue_log.append(memory_message)
                            st.session_state.last_api_event = (
                                "Fast local debug memory shown."
                            )
                    except Exception as exc:
                        error_message = (
                            f"Local memory display failed for {nearby_name}: {exc}"
                        )
                        st.error(error_message)
                        st.session_state.dialogue_log.append(error_message)

        st.divider()
        if st.button("End Day", type="primary", use_container_width=True):
            st.session_state.dialogue_log.append(
                "End day started. Running Cognee improve() and gossip propagation..."
            )
            try:
                with st.spinner("Consolidating memories and spreading village gossip..."):
                    run_async(end_day(st.session_state.session_id))
            except Exception as exc:
                error_message = f"End day failed: {exc}"
                st.error(error_message)
                st.session_state.dialogue_log.append(error_message)
                st.session_state.last_api_event = (
                    "End day failed before improve() and gossip completed."
                )
            else:
                st.session_state.day += 1
                st.session_state.session_id = (
                    f"echoworld_streamlit_day_{st.session_state.day}"
                )
                st.session_state.last_api_event = (
                    "improve() consolidated session memory; gossip propagation "
                    "updated NPC context."
                )
                st.session_state.dialogue_log.append(
                    f"Day {st.session_state.day} started."
                )

    with st.container(border=True):
        st.subheader("Dialogue Log")
        if st.session_state.dialogue_log:
            st.caption("Showing the latest 12 messages.")
            recent_messages = st.session_state.dialogue_log[-12:]
            for message in recent_messages:
                message_role = "user" if message.startswith("You →") else "assistant"
                with st.chat_message(message_role):
                    st.markdown(message)
        else:
            st.caption("No actions selected yet.")

with right_col:
    with st.container(border=True):
        st.subheader("Memory / API Activity")
        st.metric("Current day", st.session_state.day)
        st.write(f"**Session ID:** `{st.session_state.session_id}`")
        st.write(
            "**Player position:** "
            f"row {st.session_state.player_pos['row']}, "
            f"col {st.session_state.player_pos['col']}"
        )
        st.write(f"**Nearby NPC:** {nearby_name}")
        st.write(
            f"**Last Cognee/API event:** {st.session_state.last_api_event}"
        )

    with st.container(border=True):
        st.subheader("Cognee lifecycle demo")
        st.markdown(
            "- `remember()`: NPC stores interactions\n"
            "- `recall()`: NPC retrieves memory before speaking\n"
            "- `improve()`: endday consolidates memory\n"
            "- `forget()`: bribe wipes or rotates one NPC memory\n"
            "- `gossip`: hearsay propagates between NPCs"
        )
