"""
Configuration module for Blog Writing Agent.
Loads environment variables and initializes LLM model.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq

# Load environment variables from .env file
load_dotenv()

# ============================================================================
# LLM Configuration
# ============================================================================
# Using GPT-4o
model = ChatGroq(
            # model="llama-3.3-70b-versatile",
            model="llama-3.1-8b-instant",
            temperature=0.4,
            api_key=os.getenv("GROQ_API_KEY")
)
# ============================================================================
# Application Configuration
# ============================================================================
CONFIG = {
    "configurable": {"thread_id": "blog-1"},
    "run_name": "blog-writing-agent"
}
