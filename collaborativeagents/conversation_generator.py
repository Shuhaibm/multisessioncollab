import os
import json
import copy
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from collaborativeagents.agents import UserAgent,CollaboratorAgent
from collaborativeagents.prompts import termination_signal


class ConversationGenerator:
    def __init__(
        self,
        user_task_description,
        user_persona,
        user_preferences,
        max_turns,
        with_proper_scaffolding=False,
        num_retries=3,
        batch_size=20,
        user_model_name=None,
        user_api_base=None,
        user_api_key=None,
        collaborator_model_name=None,
        collaborator_api_base=None,
        collaborator_api_key=None
    ):
        self.user_task_description = user_task_description
        self.user_persona = user_persona
        self.user_preferences = user_preferences
        self.max_turns = max_turns
        self.with_proper_scaffolding = with_proper_scaffolding
        self.num_retries = num_retries
        self.batch_size = batch_size

        self.user_model_name = user_model_name
        self.user_api_base = user_api_base
        self.user_api_key = user_api_key
        self.collaborator_model_name = collaborator_model_name
        self.collaborator_api_base = collaborator_api_base
        self.collaborator_api_key = collaborator_api_key

    def generate_conversation(self, sample):
        problem,solution = sample['problem'],sample['solution']

        for retry in range(self.num_retries):
            try:
                user_agent = UserAgent(
                    user_task_description=self.user_task_description,
                    problem=problem,
                    user_persona=self.user_persona,
                    user_preferences=self.user_preferences,
                    model_name=self.user_model_name,
                    api_base=self.user_api_base,
                    api_key=self.user_api_key
                )
                collaborator_agent = CollaboratorAgent(
                    model_name=self.collaborator_model_name,
                    api_base=self.collaborator_api_base,
                    api_key=self.collaborator_api_key,
                )

                full_conversation_log = []
                conversation = [{"role": "assistant", "content": "How can I help you?"}]
                for _ in range(self.max_turns):
                    user_response = user_agent.generate_user_response(conversation)
                    if user_response is None:
                        raise ValueError("User agent failed to generate a valid response")
                    conversation.append({"role": "user", "content": str(user_response["response"])})
                    full_conversation_log.append(user_response)

                    if termination_signal in user_response["response"]:
                        break

                    collaborator_response = collaborator_agent.generate_collaborator_response(conversation)
                    if collaborator_response is None:
                        raise ValueError("Collaborator agent failed to generate a valid response")
                    conversation.append({"role": "assistant", "content": str(collaborator_response["response"])})
                    full_conversation_log.append(collaborator_response)

                return {
                    "sample": sample,
                    "conversation": conversation,
                    "full_conversation_log": full_conversation_log
                }
            except Exception as e:
                print(f"An error occurred: {e}")
                print(traceback.format_exc())
                print(f"Retrying {retry+1} times")

        return None
    
    def generate_conversations_parallel(self, samples):
        generated_conversations = []

        batch_size = self.batch_size
        total_successes,total_failures = len(generated_conversations),0

        # with tqdm(total=len(samples), desc="Generating user conversation sessions") as progress_bar:
        for i in range(0, len(samples), batch_size):
            batch = samples[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=min(batch_size, len(batch))) as executor:
                futures_to_index = {
                    executor.submit(self.generate_conversation, sample): sample for sample in batch
                }

                for future in as_completed(futures_to_index):                        
                    curr_result = future.result()
                    if curr_result == None:
                        total_failures += 1
                        continue
                    else:
                        generated_conversations.append(curr_result)
                        total_successes += 1
                        # progress_bar.update(1)

        print(f"Generation complete!")
        print(f"    # succeeded user conversation sessions: {total_successes}")
        print(f"    # failed user conversation sessions: {total_failures}")

        return generated_conversations

    def generate_conversation_with_reflective_agent(self, sample, collaborator_agent):
        problem,solution = sample['problem'],sample['solution']

        for retry in range(self.num_retries):
            try:
                user_agent = UserAgent(
                    user_task_description=self.user_task_description,
                    problem=problem,
                    user_persona=self.user_persona,
                    user_preferences=self.user_preferences,
                    model_name=self.user_model_name,
                    api_base=self.user_api_base,
                    api_key=self.user_api_key
                )

                full_conversation_log = []
                conversation = [{"role": "assistant", "content": "How can I help you?"}]
                for _ in range(self.max_turns):
                    user_response = user_agent.generate_user_response(conversation)
                    if user_response is None:
                        raise ValueError("User agent failed to generate a valid response")
                    conversation.append({"role": "user", "content": str(user_response["response"])})
                    full_conversation_log.append(user_response)

                    if termination_signal in user_response["response"]:
                        break

                    collaborator_response = collaborator_agent.generate_collaborator_response(conversation)
                    if collaborator_response is None:
                        raise ValueError("Collaborator agent failed to generate a valid response")
                    conversation.append({"role": "assistant", "content": str(collaborator_response["response"])})
                    full_conversation_log.append(collaborator_response)

                return {
                    "sample": sample,
                    "conversation": conversation,
                    "full_conversation_log": full_conversation_log
                }
            except Exception as e:
                print(f"An error occurred: {e}")
                print(traceback.format_exc())
                print(f"Retrying {retry+1} times")

        return None
  
    def generate_conversations_with_reflective_agent(self, samples, training=False):
        generated_conversations = []
        agent_notes = ""
        for sample in samples:
            if training:
                agent_notes = ""
            for retry in range(self.num_retries):
                try:
                    collaborator_agent = CollaboratorAgent(
                        model_name=self.collaborator_model_name,
                        agent_notes=agent_notes,
                        with_proper_scaffolding=self.with_proper_scaffolding,
                        api_base=self.collaborator_api_base,
                        api_key=self.collaborator_api_key,
                    )
                    curr_result = self.generate_conversation_with_reflective_agent(sample, collaborator_agent)

                    agent_notes = collaborator_agent.update_agent_notes(agent_notes, curr_result["conversation"])
                    curr_result["agent_notes"] = agent_notes
                    generated_conversations.append(curr_result)

                    agent_notes = agent_notes["agent_notes"]

                    break
                except Exception as e:
                    print(f"An error occurred: {e}")
                    print(traceback.format_exc())
                    print(f"Retrying {retry+1} times for sample {sample}")
        
        print(f"Generation complete!")
        print(f"    # succeeded user conversation sessions: {len(generated_conversations)}")
        print(f"    # failed user conversation sessions: {len(samples) - len(generated_conversations)}")

        return generated_conversations