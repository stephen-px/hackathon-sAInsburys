import streamlit as st
import store

st.set_page_config(page_title="sAInsburys", layout="wide")
st.title("sAInsburys — Waste the Difference")

# TODO: replace stubs with real store calls

col1, col2, col3 = st.columns(3)
col1.metric("£ Saved", "—")
col2.metric("This week rescued", "—")
col3.metric("This week wasted", "—")

st.subheader("Rescue board")
st.info("TODO: render leftovers from store.leftovers()")

st.subheader("Leaderboard")
st.info("TODO: render store.leaderboard()")
