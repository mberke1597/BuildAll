import google.generativeai as genai
import os

# Configure with your API key
genai.configure(api_key="AIzaSyDqVyyL-e-h8xJPK6FbRk6N5JdR5YRQUo4")

print("Available Gemini Models:\n")
print("-" * 80)

for model in genai.list_models():
    print(f"\nModel: {model.name}")
    print(f"  Display Name: {model.display_name}")
    print(f"  Description: {model.description}")
    print(f"  Supported Methods: {model.supported_generation_methods}")
    print("-" * 80)

print("\n\nEmbedding Models (embedContent support):\n")
for model in genai.list_models():
    if 'embedContent' in model.supported_generation_methods:
        print(f"✅ {model.name}")
