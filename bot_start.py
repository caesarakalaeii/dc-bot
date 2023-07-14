from streamer_collection import streamers
from api_secrets import *
from bot import GPTBot
from multiprocessing import Process




def main():
    bots = []
    for streamer_name,v in streamers.items():
        bots.append(GPTBot(v["bot_token"], OPENAI_API_KEY, v["bot_name"], streamer_name))
    
    processes = []
    for bot in bots:
        proc = Process(target=bot.runBot())
        proc.start()
        processes.append(proc)
    for proc in processes:
        proc.join()
        
            
main()