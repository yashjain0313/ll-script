import streamlit as st
import asyncio
import os
import sys

# Import agents
from agents.linkedin_connector import run_outreach
from agents.linkedin_messenger import run_dm_campaign

st.set_page_config(page_title="LinkedIn Outreach AI", page_icon="🤖", layout="wide")

st.title("🤖 LinkedIn Outreach Agent")
st.markdown("Automate your SDE Fresher Job Hunt")

tab1, tab2 = st.tabs(["🤝 Agent 1: Auto Connect", "✉️ Agent 2: DM 1st Degree Connections"])

# ── Agent 1: Auto Connect ──────────────────────────────────────────
with tab1:
    st.header("Auto Connect with People at a Company")
    st.markdown("""
    **How it works**: Give it a company URL, and the bot will go to the company's People tab and automatically send connection requests to employees.
    """)
    
    company_urls_input = st.text_area(
        "Company LinkedIn URLs (one per line)",
        placeholder="https://www.linkedin.com/company/google/\nhttps://www.linkedin.com/company/microsoft/"
    )
    
    if st.button("Start Auto Connect", type="primary"):
        urls = [url.strip() for url in company_urls_input.split('\n') if url.strip()]
        if not urls:
            st.error("Please enter at least one company URL.")
        else:
            st.info("🚀 Launching Chrome to send requests. Please check the terminal for detailed logs!")
            with st.spinner("Automation running in background..."):
                try:
                    asyncio.run(run_outreach(urls))
                    st.success("✅ Automation completed! Check data/outreach_tracker.csv for results.")
                except Exception as e:
                    st.error(f"❌ Automation failed: {e}")


# ── Agent 2: DM 1st Degree Connections ─────────────────────────────
with tab2:
    st.header("Message Your Existing Connections")
    st.markdown("""
    **How it works**: Enter a company name. The bot will search your 1st-degree connections who work there and send them a personalized DM (e.g. asking for a referral).
    """)
    
    company_name = st.text_input(
        "Company Name",
        placeholder="e.g. Google, Amazon, Mastercard"
    )
    
    st.markdown("*(Tip: Use `{name}` in your message to automatically insert their first name!)*")
    dm_text = st.text_area(
        "Personalized DM Template",
        height=200,
        placeholder="Hi {name}, hope you're doing well!\n\nI'm reaching out because I saw an open SDE Fresher role at your company. Here is my resume: [link]\n\nWould you be open to referring me?"
    )
    
    if st.button("Start DM Campaign", type="primary"):
        if not company_name:
            st.error("Please enter a company name.")
        elif not dm_text:
            st.error("Please enter a message to send.")
        else:
            st.info(f"🚀 Launching Chrome to message connections at {company_name}. Please check the terminal for logs!")
            with st.spinner("Messaging connections in background..."):
                try:
                    asyncio.run(run_dm_campaign(company_name, dm_text))
                    st.success("✅ DM Campaign completed! Check data/dm_tracker.csv for results.")
                except Exception as e:
                    st.error(f"❌ Campaign failed: {e}")
