import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def test_openai_api():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API key from environment
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("No OpenAI API key found in .env file")
        return False
    
    logger.info(f"Found API key: {api_key[:5]}...{api_key[-4:]}")
    
    try:
        # Initialize ChatOpenAI with the API key
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        # Make a simple API call
        logger.info("Making test API call...")
        response = llm.invoke("Say hello!")
        
        # Check if the response is valid
        if response:
            logger.info(f"API call successful! Response: {response}")
            return True
        else:
            logger.error("API call returned empty response")
            return False
    except Exception as e:
        logger.error(f"API call failed with error: {e}")
        return False

if __name__ == "__main__":
    logger.info("Testing OpenAI API key...")
    success = test_openai_api()
    if success:
        logger.info("API key is working correctly!")
    else:
        logger.error("API key test failed. Please check your API key and network connection.")
