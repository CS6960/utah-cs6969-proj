import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from tools.tools import TOOLS
import logging

logging.basicConfig(level=logging.INFO)

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct")

# Use ChatOpenAI wrapper even for non-OpenAI models
# if your provider supports OpenAI-compatible API
model = ChatOpenAI(
    model=MODEL_NAME,
    api_key=API_KEY,
    base_url=BASE_URL,
)

agent = create_agent(
    model,
    tools=TOOLS,
    system_prompt="You are a helpful AI assistant. Use the provided tools to answer user queries. If you don't know the answer, say you don't know instead of making something up.",
)

def run_agent(query: str):
    result = agent.invoke({
        "messages": [HumanMessage(content=query)]
    })

    return result["messages"][-1].content