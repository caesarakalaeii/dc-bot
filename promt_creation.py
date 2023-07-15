from art_styles import art_styles_collection
from prompt import initial_prompt
import random

    
def get_prompt(bot_name, streamer_name, art_styles = None, test = False):
    
    arts = ""
    for art in art_styles:
        arts = arts + art + ", "
    if test:
        prompt = test_prompt
    else: prompt = initial_prompt
    return prompt.replace("STREAMER_NAME", streamer_name).replace("BOT_NAME", bot_name).replace("ART_STYLES", arts)
def get_art_styles(amount = 3):
    return random.sample(art_styles_collection, k=3) #gets 3 random artstyle
    

test_prompt = "You are called BOT_NAME, your client is called STREAMER_NAME, and he likes ART_STYLES"