"""
Agent 1 — Message Generator
Uses Claude API to write personalized LinkedIn connection notes
per person (300 char LinkedIn limit on notes)
"""

import openai
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import YOUR_NAME, YOUR_ROLE, RESUME_LINK, GROK_API_KEY


def generate_connection_note(person_name: str, person_title: str, company: str) -> str:
    """Generate a personalized 300-char LinkedIn connection note."""

    client = openai.OpenAI(
        api_key=GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )

    prompt = f"""Write a LinkedIn connection request note. STRICT rules:
- Under 300 characters total (LinkedIn hard limit)
- Friendly, not desperate
- Mention their company: {company}
- Mention I'm a fresher looking for {YOUR_ROLE} role
- My name: {YOUR_NAME}
- Include resume link: {RESUME_LINK}
- Address them as {person_name} ({person_title})
- No hashtags, no emojis
- Sound human, not like a template

Output ONLY the message text, nothing else."""

    try:
        response = client.chat.completions.create(
            model="grok-2-latest",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        note = response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating note: {e}")
        note = f"Hi {person_name}, I'm a fresher looking for {YOUR_ROLE} roles. I admire {company} and would love to connect! {RESUME_LINK}"

    # Safety check — LinkedIn hard limit
    if len(note) > 300:
        note = note[:297] + "..."

    return note


def generate_followup_message(person_name: str, company: str, days_since_connect: int) -> str:
    """Generate a follow-up message after connection is accepted."""

    client = openai.OpenAI(
        api_key=GROK_API_KEY,
        base_url="https://api.x.ai/v1",
    )

    prompt = f"""Write a LinkedIn follow-up message after a connection was accepted.
Context:
- Connected {days_since_connect} days ago
- Person: {person_name} at {company}
- I am: {YOUR_NAME}, a fresher seeking {YOUR_ROLE} role
- Resume: {RESUME_LINK}

Rules:
- Under 500 characters
- Polite, brief, not pushy
- Ask if there are any openings or if they can refer
- Sound genuine

Output ONLY the message, nothing else."""

    try:
        response = client.chat.completions.create(
            model="grok-2-latest",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating follow-up: {e}")
        return f"Hi {person_name}, thanks for connecting! I'm actively looking for {YOUR_ROLE} opportunities at {company}. Let me know if you are hiring!"


if __name__ == "__main__":
    # Test it
    note = generate_connection_note("Priya Sharma", "Senior Recruiter", "Google")
    print(f"Generated note ({len(note)} chars):\n{note}")
    print()
    followup = generate_followup_message("Priya Sharma", "Google", 3)
    print(f"Follow-up message:\n{followup}")
