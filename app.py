"""Streamlit UI: display and trigger scraper."""

import streamlit as st
import database

st.title("Google Map Scraper")

if st.button("Load Results"):
    df = database.load_results()
    st.dataframe(df)
