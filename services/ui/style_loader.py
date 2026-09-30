import os
import streamlit as st


def load_css(path: str) -> None:
    """Injects a local CSS file into the Streamlit page, if it exists."""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def inject_local_font(font_path: str, font_family: str) -> None:
    """Optionally embeds a local font file via @font-face (skipped if missing)."""
    if not os.path.exists(font_path):
        return
    import base64
    with open(font_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    st.markdown(
        f"""
        <style>
        @font-face {{
            font-family: '{font_family}';
            src: url(data:font/otf;base64,{encoded}) format('opentype');
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def inject_webrtc_styles() -> None:
    """Light styling tweaks for the streamlit-webrtc video widget."""
    st.markdown(
        """
        <style>
        video { border-radius: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
