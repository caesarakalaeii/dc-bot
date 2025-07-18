import json
import os

import requests


def list_conversations(bot_name: str):
    return os.listdir(f"persistence/{bot_name}_conversations")


def load_conversation(name: str, number: int | None, bot_name):
    dir_path = f"persistence/{bot_name}_conversations"
    if number is None:
        if os.path.exists(os.path.join(dir_path, f"{name}.json")):
            with open(os.path.join(dir_path, f"{name}.json"), "r") as f:
                return json.loads(f.read())
        else:
            raise FileNotFoundError
    else:
        if os.path.exists(os.path.join(dir_path, f"{name}_{number}.json")):
            with open(os.path.join(dir_path, f"{name}_{number}.json"), "r") as f:
                return json.loads(f.read())
        else:
            raise FileNotFoundError


def save_media(name: str, medias):
    dir_path = f"persistence/media/{name}_media"
    try:
        os.makedirs(dir_path, exist_ok=True)  # Create directory if it doesn't exist
    except OSError as e:
        print(f"Error creating directory: {e}")
        return

    for media in medias:
        file_path = os.path.join(dir_path, media.filename)
        if not os.path.exists(file_path):
            try:
                r = requests.get(media.url, allow_redirects=True)
                with open(file_path, "wb") as file:
                    file.write(r.content)
            except Exception as e:
                print(f"Error saving media: {e}")
        else:
            i = 0
            while True:
                filename: str = media.filename
                filename_split = filename.split(".")
                new_name = ""
                for j in range(len(filename_split) - 1):
                    new_name += filename_split[j]
                new_name += f"_{i}.{filename_split[-1]}"
                file_path = os.path.join(dir_path, new_name)
                if not os.path.exists(file_path):
                    try:
                        r = requests.get(media.url, allow_redirects=True)
                        with open(file_path, "wb") as file:
                            file.write(r.content)
                        break
                    except Exception as e:
                        print(f"Error saving media: {e}")
                        break
                i += 1


async def unpack_message(message_object):
    files = []
    attachments = message_object.attachments

    for a in attachments:
        files.append(await a.to_file())
    return message_object.content, message_object.author, files


def handle_args(message: str):
    message_splits = message.split(sep=" ")
    handling_name = False
    handling_value = False
    name = ""
    value = ""
    values = []
    for s in message_splits:
        if s.endswith('"') and handling_value:
            value += " " + s.replace('"', "")
            values.append(value)
            value = ""
        elif s.startswith('"') and handling_name:
            handling_value = True
            value += s.replace('"', "")
            if s.endswith('"'):
                values.append(value)
                value = ""
        elif handling_value:
            value += " " + s
        elif handling_name:
            if s.endswith('"'):
                name += " " + s.replace('"', "")
                continue
            name += " " + s
        elif s.startswith('"') and not handling_value:
            handling_name = True
            if s.endswith('"'):
                name = s.replace('"', "")
                continue
            name += s.replace('"', "")

    return name, values


def ensure_persistence_dir_exists(subfolder=None):
    if subfolder:
        dir_path = os.path.join("persistence", subfolder)
    else:
        dir_path = "persistence"
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"Created {dir_path} directory.")
    else:
        print(f"{dir_path} directory already exists.")
