"""
Use this Script to print Conversations in .json format, as printing it through discord can crash the pi
"""
from bot import ConversationHandler, GPTBot


if __name__ == '__main__':
    
    name = "freyacampbell"
    number = 0
    bot_name = "Alex"
    
    conversation = ConversationHandler.loadConversation(name, number, bot_name)
    for c in conversation:
        if c["role"] == "system":
            continue
        elif c["role"] == "user":
            print(f"{name}: {c['content']}")
        else:
            print(f"{bot_name}: {c['content']}")