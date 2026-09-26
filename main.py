import streamlit as st

from services.auth.login_wall import render_login_wall

def main():
    st.set_page_config(
        page_title="FitMentor AI",
        initial_sidebar_state="expanded",
        layout="centered"
    )

    if not render_login_wall():
        return


if __name__ == "__main__":
    main()
    

# st.set_page_config(page_title="FitMentor AI")
# st.title("FitMentor AI")
# st.subheader("Analyze your exercise form, receive real-time feedback, and improve your workout technique with FitMentor AI.")

