import streamlit as st

from services.auth.login_wall import render_login_wall
from services.state.session_defaults import initial_session_defaults
from services.config.workout_config import EXERCISE_OPTIONS


def main():
    st.set_page_config(
        page_title="FitMentor AI",
        initial_sidebar_state="expanded",
        layout="centered"
    )

    if not render_login_wall():
        return

    initial_session_defaults()

    workout_started = st.session_state.get("workout_started", False)

    with st.sidebar:
        st.title("FitMentor AI Coach")
        if st.session_state.get("username"):
            st.caption(f"Logged in as: {st.session_state['username']}")   

        st.divider()

        st.subheader("Workout Plan")

        if not workout_started:
            st.selectbox("Exercise", options=EXERCISE_OPTIONS, key="plan_exercise")
            st.number_input("Sets", min_value=0, max_value=50, key="plan_sets, step=1")
            st.number_input("Reps Per Set", min_value=0, max_value=50, key="plan_reps, step=1")
            st.markdown(" ")
            start_session_button =st.button("Start Session", width="stretch", key="start_session_button")

            if 


        

    st.write(f"Hello {st.session_state['username']}, welcome to FitMentor AI! ")


if __name__ == "__main__":
    main()
    

# st.set_page_config(page_title="FitMentor AI")
# st.title("FitMentor AI")
# st.subheader("Analyze your exercise form, receive real-time feedback, and improve your workout technique with FitMentor AI.")

