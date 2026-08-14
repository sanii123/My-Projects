"""
app.py

The dashboard. Two jobs only:
    1. Show Luna's current stats and let you manually feed/walk/play/ignore
       her, because sometimes you don't need an agent, you just need a
       walk.
    2. Let you ask a natural-language question and watch Gemini investigate
       before it answers, tool call by tool call, instead of guessing.

Run with: streamlit run app.py
"""

import streamlit as st

import dog_state
from gemini_client import ask_about_luna_sync

st.set_page_config(page_title="Good Boy Protocol", page_icon="🐾", layout="centered")

if "history" not in st.session_state:
    st.session_state.history = []  # list of AgentResponse-shaped dicts


def render_state(state: dict) -> None:
    st.subheader(f"{state['name']}'s current state")

    col1, col2, col3 = st.columns(3)
    col1.metric("Energy", f"{state['energy']}/100")
    col2.metric("Boredom", f"{state['boredom']}/100")
    col3.metric("Tail wag", f"{state['tail_wag']}/100")

    col4, col5 = st.columns(2)
    col4.metric("Minutes since last meal", dog_state.minutes_since_last_meal())
    col5.metric("Minutes since last walk", dog_state.minutes_since_last_walk())

    st.caption(f"Treats today: {state['treats_today']}  |  Last action: {state['last_action']}")


def render_action_buttons() -> None:
    st.subheader("Direct intervention (skip the agent, just act)")
    c1, c2, c3, c4, c5 = st.columns(5)
    if c1.button("Feed"):
        dog_state.feed()
        st.rerun()
    if c2.button("Give treat"):
        dog_state.give_treat()
        st.rerun()
    if c3.button("Take for walk"):
        dog_state.take_for_walk()
        st.rerun()
    if c4.button("Play (10 min)"):
        dog_state.play(10)
        st.rerun()
    if c5.button("Ignore"):
        dog_state.ignore()
        st.rerun()


def render_trace(trace) -> None:
    if not trace:
        st.caption("Gemini reached a verdict without needing to check anything further.")
        return
    st.markdown("**Investigation:**")
    for i, step in enumerate(trace, start=1):
        args_str = f"({step.arguments})" if step.arguments else "()"
        st.markdown(f"`{i}.` `{step.tool_name}{args_str}` → `{step.result}`")


def render_ask_agent() -> None:
    st.subheader("Ask the agent")
    st.caption("It has to check before it's allowed to have an opinion.")

    question = st.text_input(
        "e.g. \"Why is Luna staring at me?\"",
        key="question_input",
    )

    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Investigating..."):
            try:
                response = ask_about_luna_sync(question)
            except Exception as exc:  # noqa: BLE001 - surfacing to the user directly
                st.error(
                    "The agent couldn't complete its investigation. "
                    f"Details: {exc}"
                )
                return

        st.session_state.history.insert(
            0, {"question": question, "verdict": response.verdict, "trace": response.trace}
        )

    for entry in st.session_state.history:
        with st.container(border=True):
            st.markdown(f"**Q: {entry['question']}**")
            render_trace(entry["trace"])
            st.markdown(f"**Verdict:** {entry['verdict']}")


def main() -> None:
    st.title("Good Boy Protocol")
    st.caption(
        "Every dog owner is a confident narrator with zero evidence. "
        "This agent has to show its work before it's allowed an opinion."
    )

    state = dog_state.get_state()
    render_state(state)
    render_action_buttons()
    st.divider()
    render_ask_agent()

    with st.sidebar:
        st.markdown("### Reset")
        st.caption("If the demo goes sideways, start Luna over.")
        if st.button("Reset Luna to defaults"):
            dog_state.reset()
            st.session_state.history = []
            st.rerun()


if __name__ == "__main__":
    main()
