import argparse
import json
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

from collaborativeagents.conversation_generator import ConversationGenerator
from collaborativeagents.conversation_evaluator import ConversationEvaluator
from collaborativeagents.datasets import datasets_info
from collaborativeagents.agents import CollaboratorAgent,UserAgent
from collaborativeagents.prompts import agent_system_prompt_no_user



def load_dataset(dataset_name, eval_size):
    if dataset_name not in datasets_info:
        raise ValueError(f"Dataset '{dataset_name}' not found. Available datasets: {list(datasets_info.keys())}")

    dataset_class,user_task_description = datasets_info[dataset_name]['class'],datasets_info[dataset_name]['task_description']
    dataset_instance = dataset_class(eval_size=eval_size)
    dataset = dataset_instance.get_dataset()
    print(f"Loaded {len(dataset)} samples from {dataset_name}")

    return dataset,user_task_description

def load_user_profiles():
    script_dir = os.path.dirname(__file__)
    user_profiles_path = os.path.join(script_dir, "collaborativeagents", "user_profiles", "user_profiles.json")

    with open(user_profiles_path, 'r') as f:
        return json.load(f)

def run_user_profiles(
    dataset_name="math-hard",
    user_profiles=None,
    agent_with_reflection=False,
    with_proper_scaffolding=False,
    eval_size=20,
    max_turns=10,
    batch_size=100,
    user_model_name=None,
    user_api_base=None,
    user_api_key=None,
    collaborator_model_name=None,
    collaborator_api_base=None,
    collaborator_api_key=None,
    judge_model_name=None,
    judge_api_base=None,
    judge_api_key=None,
    output_file=None
    ):
    dataset,user_task_description = load_dataset(dataset_name, eval_size)

    generated_user_sessions = []
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            seen_users = set()
            for line in f:
                if line.strip() == "":
                    continue
                curr_result = json.loads(line)
                seen_users.add(curr_result["i"])
                generated_user_sessions.append(curr_result)
            user_profiles = [user_profile_elem for user_profile_elem in user_profiles if user_profile_elem["i"] not in seen_users]

    def generate_and_evaluate_single_user_profile(user_profile_elem):
        user_profile_i = user_profile_elem["i"]
        user_persona = user_profile_elem["persona"]
        user_preferences = "\n".join([f"{i+1}. {pref}" for i, pref in enumerate(user_profile_elem["preferences"])])

        # Generate conversations
        if agent_with_reflection:
            print(f"Starting generation conversation sessions for User {user_profile_i}")
            conversationGenerator = ConversationGenerator(
                user_task_description=user_task_description,
                user_persona=user_persona,
                user_preferences=user_preferences,
                max_turns=max_turns,
                with_proper_scaffolding=with_proper_scaffolding,
                batch_size=batch_size,
                user_model_name=user_model_name,
                user_api_base=user_api_base,
                user_api_key=user_api_key,
                collaborator_model_name=collaborator_model_name,
                collaborator_api_base=collaborator_api_base,
                collaborator_api_key=collaborator_api_key
            )
            generated_conversations = conversationGenerator.generate_conversations_with_reflective_agent(dataset)
            print(f"Finished generation conversation sessions for User {user_profile_i}")
            print(f"    # succeeded user conversation sessions: {len(generated_conversations)}")
            print(f"    # failed user conversation sessions: {len(dataset) - len(generated_conversations)}")
        else:
            print(f"Starting generation conversation sessions for User {user_profile_i}")
            conversationGenerator = ConversationGenerator(
                user_task_description=user_task_description,
                user_persona=user_persona,
                user_preferences=user_preferences,
                max_turns=max_turns,
                with_proper_scaffolding=with_proper_scaffolding,
                batch_size=batch_size,
                user_model_name=user_model_name,
                user_api_base=user_api_base,
                user_api_key=user_api_key,
                collaborator_model_name=collaborator_model_name,
                collaborator_api_base=collaborator_api_base,
                collaborator_api_key=collaborator_api_key
            )
            generated_conversations = conversationGenerator.generate_conversations_parallel(dataset)
            print(f"Finished generation conversation sessions for User {user_profile_i}")
            print(f"    # succeeded user conversation sessions: {len(generated_conversations)}")
            print(f"    # failed user conversation sessions: {len(dataset) - len(generated_conversations)}")
    
        # Evaluate conversations
        conversationEvaluator = ConversationEvaluator(
            dataset_name=dataset_name,
            model_name=judge_model_name,
            api_base=judge_api_base,
            api_key=judge_api_key
        )
        evaluation_results = conversationEvaluator.evaluate_conversations(generated_conversations)
        user_profile_elem["generated_conversations"] = generated_conversations
        user_profile_elem["evaluation"] = evaluation_results

        return user_profile_elem


    with open(output_file, 'a') as f:
        with tqdm(total=len(user_profiles), desc="Processing user profiles") as progress_bar:
            for i in range(0, len(user_profiles), batch_size):
                batch = user_profiles[i:i+batch_size]
                
                with ThreadPoolExecutor(max_workers=min(batch_size, len(batch))) as executor:
                    futures_to_profile = {
                        executor.submit(generate_and_evaluate_single_user_profile, user_profile_elem): user_profile_elem 
                        for user_profile_elem in batch
                    }

                    for future in as_completed(futures_to_profile):
                        curr_result = future.result()
                        generated_user_sessions.append(curr_result)
                        
                        f.write(json.dumps(curr_result) + "\n")
                        f.flush()
                        
                        progress_bar.update(1)

    # Aggregate evaluation results from all user sessions
    avg_accuracy = sum([user_session['evaluation']['average_accuracy'] for user_session in generated_user_sessions]) / len(generated_user_sessions)
    avg_length = sum([user_session['evaluation']['average_conversation_length'] for user_session in generated_user_sessions]) / len(generated_user_sessions)

    num_enforced_preferences_per_conversation = []
    for generated_user_session in generated_user_sessions:
        for generated_conversation in generated_user_session['generated_conversations']:
            curr_num_enforced_preferences = 0
            for message in generated_conversation['full_conversation_log']:
                if 'enforce_preferences' in message:
                    if message["enforce_preferences"] == True or message["enforce_preferences"] == "True":
                        curr_num_enforced_preferences += 1
            num_enforced_preferences_per_conversation.append(curr_num_enforced_preferences)

    print(f"\n\n\nAll user profiles generation and evaluation complete!")
    print(f"    # Total user profiles processed: {len(generated_user_sessions)}")
    print(f"    # Total conversations: {sum([len(user_session['generated_conversations']) for user_session in generated_user_sessions])}")
    print("\nEvaluation Results:")
    print(f"    # Overall average accuracy: {avg_accuracy}")
    print(f"    # Overall average conversation length (# messages): {avg_length}")
    print(f"    # Overall average number of enforced preferences: {sum(num_enforced_preferences_per_conversation) / len(num_enforced_preferences_per_conversation)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment_type", type=str)
    parser.add_argument("--dataset", type=str)
    parser.add_argument("--eval_size", type=int)
    parser.add_argument("--output_file", type=str)
    parser.add_argument("--max_turns", type=int)
    parser.add_argument("--batch_size", type=int)
    parser.add_argument("--user_model_name", type=str)
    parser.add_argument("--user_api_base", type=str)
    parser.add_argument("--user_api_key", type=str)
    parser.add_argument("--collaborator_model_name", type=str)
    parser.add_argument("--collaborator_api_base", type=str)
    parser.add_argument("--collaborator_api_key", type=str)
    parser.add_argument("--judge_model_name", type=str)
    parser.add_argument("--judge_api_base", type=str)
    parser.add_argument("--judge_api_key", type=str)
    args = parser.parse_args()

    if args.experiment_type == "agent_without_memory":
        user_profiles = load_user_profiles()
        run_user_profiles(
            dataset_name=args.dataset,
            user_profiles=user_profiles,
            agent_with_reflection=False,
            with_proper_scaffolding=False,
            eval_size=args.eval_size,
            max_turns=args.max_turns,
            batch_size=args.batch_size,
            user_model_name=args.user_model_name, user_api_base=args.user_api_base, user_api_key=args.user_api_key,
            collaborator_model_name=args.collaborator_model_name, collaborator_api_base=args.collaborator_api_base, collaborator_api_key=args.collaborator_api_key,
            judge_model_name=args.judge_model_name, judge_api_base=args.judge_api_base, judge_api_key=args.judge_api_key,
            output_file=args.output_file
        )
    elif args.experiment_type == "agent_with_memory":
        user_profiles = load_user_profiles()
        run_user_profiles(
            dataset_name=args.dataset,
            user_profiles=user_profiles,
            agent_with_reflection=True,
            with_proper_scaffolding=True,
            eval_size=args.eval_size,
            max_turns=args.max_turns,
            batch_size=args.batch_size,
            user_model_name=args.user_model_name, user_api_base=args.user_api_base, user_api_key=args.user_api_key,
            collaborator_model_name=args.collaborator_model_name, collaborator_api_base=args.collaborator_api_base, collaborator_api_key=args.collaborator_api_key,
            judge_model_name=args.judge_model_name, judge_api_base=args.judge_api_base, judge_api_key=args.judge_api_key,
            output_file=args.output_file
        )
    else:
        raise ValueError(f"Invalid experiment type: {args.experiment_type}")