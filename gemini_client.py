from google import genai

class googleClient():
    def __init__(self, api_key):
        self.api_key = api_key
        self.client = genai.client(api_key= self.api_key)