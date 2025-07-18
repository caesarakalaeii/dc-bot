import json
import os


class ConversationHandler:

    def __init__(
        self, user, bot_name, init_prompt=None, conversation=None, author=None
    ):
        self.user = user
        self.bot_name = bot_name
        self.dir_path = f"persistence/{self.bot_name}_conversations"
        self.file_path = os.path.join(self.dir_path, f"{self.user}.json")
        self.init_prompt = init_prompt
        self.author = author
        self.base_prompt = {"role": "system", "content": self.init_prompt}

        if conversation is not None:
            self.conversation = conversation
        else:
            try:
                self.check_dir()
                self.fetch_conversation()
            except FileNotFoundError:
                self.conversation = [self.base_prompt]

    def awaiting_response(self):
        return self.conversation[-1]["role"] == "user"

    def update_gpt(self, message):
        self.conversation.append({"role": "assistant", "content": message})

    def update_user(self, message):
        self.conversation.append({"role": "user", "content": message})

    def append_user_message(self, message: str):
        self.conversation[-1]["content"] = (
            self.conversation[-1]["content"] + "\n" + message
        )

    def check_dir(self):
        try:
            os.mkdir(self.dir_path)
        except FileExistsError:
            return

    def write_conversation(self):
        with open(self.file_path, "w") as f:
            f.write(json.dumps(self.conversation))

    def save_conversation(self):
        for i in range(100):
            if os.path.exists(os.path.join(self.dir_path, f"{self.user}_{i}.json")):
                continue
            else:
                with open(
                    os.path.join(self.dir_path, f"{self.user}_{i}.json"), "w"
                ) as f:
                    f.write(json.dumps(self.conversation))
                break

    def fetch_conversation(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, "r") as f:
                self.conversation = json.loads(f.read())
        else:
            raise FileNotFoundError

    def delete_conversation(self):
        self.save_conversation()
        if os.path.exists(self.file_path):
            os.remove(self.file_path)
        else:
            raise FileNotFoundError
