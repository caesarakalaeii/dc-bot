import time
import discord


class QueueItem:
    message: discord.Message
    timestamp: float

    def __init__(self, message: discord.Message) -> None:
        self.message = message
        self.timestamp = time.time()
