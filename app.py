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


def load_user_info():
    info = {"NAME": "[Your Name]", "RESUME_LINK": "[Your Resume Link]", "EMAIL": "[Your Email]"}
    try:
        with open("user_info.txt", "r") as f:
            for line in f:
                if "=" in line:
                    key, val = line.strip().split("=", 1)
                    info[key] = val
    except FileNotFoundError:
        pass
    return info

USER_INFO = load_user_info()

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
    
    apply_mode = st.radio("Message Type", ["With Job Link", "With Job ID"])
    
    user_name = USER_INFO.get("NAME", "Your Name")
    resume_link = USER_INFO.get("RESUME_LINK", "Your Resume Link")
    email = USER_INFO.get("EMAIL", "Your Email")
    
    job_link = ""
    job_id = ""
    
    if apply_mode == "With Job Link":
        job_link = st.text_input("Job Link", placeholder="https://careers.slb.com/...")
        
        default_template = f"""Hi {{name}}, hope you're doing well!

I recently came across the {job_link} opportunity at {{company_name}} and wanted to reach out to see if you'd be open to referring me.

I'm {user_name}, a recent Computer Science graduate with experience in full-stack development and AI applications. I recently completed my internship at HCLTech, where I worked on backend and AI-driven solutions. I've also solved 200+ DSA problems and built projects involving Agentic AI, RAG systems, and scalable web applications.

Here's my resume: {{resume_link}}

I'd really appreciate it if you could consider referring me for the role. Thanks for your time, and have a great day!

Warm regards,
{user_name}
Email: {email}"""
    else:
        job_id = st.text_input("Job ID / Role Name", placeholder="e.g., SDE Fresher (Job ID: 12345)")
        
        default_template = f"""Hi {{name}}, hope you're doing well!

I recently came across the {job_id} opportunity at {{company_name}} and wanted to reach out to see if you'd be open to referring me.

I'm {user_name}, a recent Computer Science graduate with experience in full-stack development and AI applications. I recently completed my internship at HCLTech, where I worked on backend and AI-driven solutions. I've also solved 200+ DSA problems and built projects involving Agentic AI, RAG systems, and scalable web applications.

Here's my resume: {{resume_link}}

I'd really appreciate it if you could consider referring me for the role. Thanks for your time, and have a great day!

Warm regards,
{user_name}
Email: {email}"""
        
    st.markdown("*(Tip: The template automatically replaces `{name}`, `{company_name}`, and `{resume_link}` with your inputs!)*")
    dm_text = st.text_area(
        "Personalized DM Template",
        value=default_template,
        height=450
    )
    
    if st.button("Start DM Campaign", type="primary"):
        if not company_name:
            st.error("Please enter a company name.")
        elif not dm_text:
            st.error("Please enter a message to send.")
        else:
            final_dm_text = dm_text.replace("{resume_link}", resume_link).replace("{company_name}", company_name)
            
            st.info(f"🚀 Launching Chrome to message connections at {company_name}. Please check the terminal for logs!")
            with st.spinner("Messaging connections in background..."):
                try:
                    asyncio.run(run_dm_campaign(company_name, final_dm_text))
                    st.success("✅ DM Campaign completed! Check data/dm_tracker.csv for results.")
                except Exception as e:
                    st.error(f"❌ Campaign failed: {e}")
