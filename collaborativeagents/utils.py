def get_conversation_string(messages):
    return "\n".join([f"{message['role'].capitalize()}: {message['content']}" for message in messages])