import streamlit as st
from services.persistence.exercise_repository import get_or_create_user


def render_login_wall():
    """
    Minimal username-only session gate. No password: a real, unique username
    is enough to identify a returning user and give them their own workout
    history. This is an explicit, documented scope decision for this
    academic prototype - see the README for how to harden it later.
    """
    if st.session_state.get("user_id") is not None:
        return True

    st.title("Welcome to FitMentor AI")
    st.markdown("### Enter a unique name to start your session")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Name (unique)", placeholder="e.g. karthika_krishna")
        submit_button = st.form_submit_button("Start Session", width="stretch")

    if submit_button:
        if not username:
            st.error("Name cannot be empty. Please enter a valid name.")
            return False

        user = get_or_create_user(username.strip())
        st.session_state["user_id"] = user["id"]
        st.session_state["username"] = user["username"]
        st.rerun()

    return False
