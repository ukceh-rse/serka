from haystack_integrations.components.generators.amazon_bedrock import (
	AmazonBedrockGenerator,
)
from dotenv import load_dotenv

load_dotenv()

generator = AmazonBedrockGenerator(model="meta.llama3-8b-instruct-v1:0")
result = generator.run("What is the purpose of a 'hello world' program?")
print(result)
