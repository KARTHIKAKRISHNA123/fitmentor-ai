import streamlit as st


def render_login_wall():
    if st.session_state.get("user_id") is not None:
        return True

    st.title("Welcome to FitMentor AI")

    st.markdown("### Welcome! Please Enter Your Credentials to Log In")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Name (unique)", placeholder="Unique Name e. g. Karthika Krishna M", key="username")
        submit_button = st.form_submit_button("Start Session", width="stretch")

    return False

