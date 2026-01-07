import traceback
from litellm import completion
from json_repair import repair_json
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from human_eval.execution import check_correctness
from bigcodebench.eval import untrusted_check

from collaborativeagents.prompts import accuracy_prompt_qa, answer_extraction_prompt_humaneval, answer_extraction_prompt_bigcodebench
from collaborativeagents.utils import get_conversation_string

class ConversationEvaluator:
    def __init__(
        self,
        dataset_name,
        num_retries=10,
        model_name=None,
        api_base=None,
        api_key=None
    ):
        self.num_retries = num_retries

        self.dataset_name = dataset_name
        self.model_name = model_name
        self.kwargs = {"temperature": 0.0, "max_tokens": 1024}
        if api_base and api_key:
            self.kwargs["api_base"] = api_base
            self.kwargs["api_key"] = api_key

    def completion(self, messages):
        return completion(model=self.model_name, messages=messages, num_retries=self.num_retries, **self.kwargs).choices[0].message.content

    def evaluate_conversation_acc(self, sample_and_conversation):
        sample,conversation = sample_and_conversation["sample"],sample_and_conversation["conversation"]
        problem,solution = sample['problem'],sample['solution']
        if "draft_answer" in sample_and_conversation["full_conversation_log"][-1]:
            draft_answer = sample_and_conversation["full_conversation_log"][-1]["draft_answer"]
        else:
            draft_answer = sample_and_conversation["full_conversation_log"][-2]["draft_answer"]

        accuracy_prompt = accuracy_prompt_qa.format(
            problem=problem,
            correct_answer=solution,
            draft_answer=draft_answer
        )
        messages = [{"role": "user", "content": accuracy_prompt}]
        judge_response = self.completion(messages)
        judge_response = repair_json(judge_response, return_objects=True)
        
        # Validate judge response has required keys
        for key in ["reasoning", "accuracy"]:
            if key not in judge_response:
                raise ValueError(f"Judge response is missing key: {key}")

        try:
            judge_response["accuracy"] = int(judge_response["accuracy"])
        except ValueError:
            raise ValueError(f"Judge response accuracy cannot be converted to int: {judge_response['accuracy']}")

        sample_and_conversation["evaluation"] = {
            "final_answer": draft_answer,
            "accuracy": judge_response,
            "conversation_length": len(conversation)
        }

        return sample_and_conversation

    def evaluate_conversations(self, conversations):
        evaluated_conversations = []
        batch_size = 50
        total_successes,total_failures = len(evaluated_conversations),0

        # with tqdm(total=len(conversations), desc="Evaluating conversations") as progress_bar:
        for i in range(0, len(conversations), batch_size):
            batch = conversations[i:i+batch_size]
            
            with ThreadPoolExecutor(max_workers=min(batch_size, len(batch))) as executor:
                futures_to_index = {
                    executor.submit(self.evaluate_conversation, sample): sample for sample in batch
                }

                for future in as_completed(futures_to_index):                        
                    curr_result = future.result()
                    if curr_result == None:
                        total_failures += 1
                        continue                        
                    evaluated_conversations.append(curr_result)

                    total_successes += 1
                        # progress_bar.update(1)

        print(f"\n\n\nEvaluation complete!")
        print(f"    # succeeded conversations: {total_successes}")
        print(f"    # failed conversations: {total_failures}")

        return {
            "evaluated_conversations": evaluated_conversations,
            "average_accuracy": sum([float(conversation['evaluation']['accuracy']['accuracy']) for conversation in evaluated_conversations]) / len(evaluated_conversations),
            "average_conversation_length": sum([conversation['evaluation']['conversation_length'] for conversation in evaluated_conversations]) / len(evaluated_conversations),
        }