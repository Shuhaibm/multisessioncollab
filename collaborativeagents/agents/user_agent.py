from json_repair import repair_json
from litellm import completion as llm_completion, batch_completion as llm_batch_completion
from copy import deepcopy

from collaborativeagents.prompts import user_system_prompt_profile_with_preferences,user_system_prompt_profile_without_preferences,user_system_prompt_no_preferences,termination_signal

class UserAgent():
    def __init__(
        self,
        user_task_description,
        problem,
        user_persona,
        user_preferences,
        model_name=None,
        api_base=None,
        api_key=None,
        num_retries=10
    ):
        self.system_prompt = user_system_prompt_profile_with_preferences.format(user_persona=user_persona, user_task_description=user_task_description, problem=problem, user_preferences=user_preferences, termination_signal=termination_signal)
        self.num_retries = num_retries

        self.model_name = model_name
        self.kwargs = {"temperature": 1.0, "max_tokens": 1024, "timeout": 36000000}
        if api_base and api_key:
            self.kwargs["api_base"] = api_base
            self.kwargs["api_key"] = api_key

    def get_system_prompt(self):
        return self.system_prompt

    def completion(self, messages):
        response = llm_completion(model=self.model_name, messages=messages, num_retries=self.num_retries, **self.kwargs).choices[0].message.content
        return response

    def batch_completion(self, messages):
        try:
            responses = llm_batch_completion(model=self.model_name, messages=messages, num_retries=self.num_retries, **self.kwargs)
            return responses
        except Exception as e:
            print(f"Failed to generate batch responses: {e}")
            return [None for _ in range(len(messages))]

    def reverse_roles(self, conversation):
        conversation = deepcopy(conversation)
        return [{"role": "user", "content": message["content"]} if message["role"] == "assistant" else {"role": "assistant", "content": message["content"]} for message in conversation]

    def generate_user_response(self, conversation):
        for _ in range(self.num_retries):
            messages = [{"role": "system", "content": self.system_prompt}] + self.reverse_roles(conversation)
            response = self.completion(messages)
            processed_response = repair_json(response, return_objects=True)

            missing_keys = [key for key in ["reasoning", "draft_answer", "should_terminate", "response"] if key not in processed_response]
            if missing_keys:
                print(f"Missing keys: {missing_keys}. Got: {processed_response}")
                continue

            return processed_response

        print(f"Failed to generate user response after {self.num_retries} retries")
        return None