from art_styles import art_styles_collection
from prompt import initial_prompt
import random

    
def get_prompt(bot_name, streamer_name, art_styles = None, test = False):
    if art_styles is None:
        art_styles = random.sample(art_styles_collection, k=3) #gets 3 random artstyle
    elif type(art_styles) is int :
        k = art_styles
        art_styles = random.sample(art_styles_collection, k) #gets k random artstyle
    elif len(art_styles) > 0:
        art_styles = art_styles  #if custom artstyles are provided
    else: raise ValueError("Art Style type not supported")
    arts = ""
    for art in art_styles:
        arts = arts + art + ", "
    if test:
        prompt = test_prompt
    else: prompt = initial_prompt
    return prompt.replace("STREAMER_NAME", streamer_name).replace("BOT_NAME", bot_name).replace("ART_STYLES", arts)


test_prompt = "You are called BOT_NAME, your client is called STREAMER_NAME, and he likes ART_STYLES"