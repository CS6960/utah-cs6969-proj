import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_community.tools import DuckDuckGoSearchResults
import logging

logging.basicConfig(level=logging.DEBUG)

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

# Use ChatOpenAI wrapper even for non-OpenAI models
# if your provider supports OpenAI-compatible API
model = ChatOpenAI(
    model="meta/llama-3.1-70b-instruct",
    api_key=API_KEY,
    base_url=BASE_URL,
)

agent = create_agent(
    model,
    tools=[DuckDuckGoSearchResults()],
    system_prompt="You are a helpful AI assistant."
)

def run_agent(query: str):
    result = agent.invoke({
        "messages": [HumanMessage(content=query)]
    })

    return result["messages"][-1].content