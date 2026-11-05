import os

# Unit tests must never touch the network, speakers, or the user's real API key.
os.environ["AURA_OFFLINE"] = "1"
os.environ["AURA_TTS_BACKEND"] = "none"
