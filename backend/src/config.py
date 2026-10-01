"""
Configuration module for Blog Writing Agent.
Loads environment variables and initializes LLM model.
"""
from __future__ import annotations
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
load_dotenv()

groq_key = os.getenv("GROQ_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")

if tavily_key:
    os.environ["TAVILY_API_KEY"] = tavily_key

# LLM Configuration
model = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.3,
    api_key=groq_key,
    # Retry temporary DNS, socket, timeout, rate-limit, and upstream failures.
    max_retries=5,
    timeout=60,
)

# Application Configuration
CONFIG = {
    "configurable": {"thread_id": "blog-1"},
    "run_name": "blog-writing-agent"
}
