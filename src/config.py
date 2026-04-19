"""
Configuration module for Blog Writing Agent.
Loads environment variables and initializes LLM model.
"""
from __future__ import annotations
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
load_dotenv()

# Streamlit secrets fallback for deployment
groq_key = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))
tavily_key = st.secrets.get("TAVILY_API_KEY", os.getenv("TAVILY_API_KEY"))

if tavily_key:
    os.environ["TAVILY_API_KEY"] = tavily_key

# LLM Configuration
model = ChatGroq(
            # model="llama-3.3-70b-versatile",
            model="llama-3.1-8b-instant",
            temperature=0.4,
            api_key=groq_key
)
# Application Configuration
CONFIG = {
    "configurable": {"thread_id": "blog-1"},
    "run_name": "blog-writing-agent"
}
