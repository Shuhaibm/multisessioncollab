import os
import json
from datasets import load_dataset


class MATH500():
    def __init__(self, dataset_name="HuggingFaceH4/MATH-500", eval_size=20, seed=42, cache_dir=os.path.join(os.path.dirname(__file__), "cache"), training=False):
        self.dataset_name = dataset_name
        self.eval_size = eval_size
        self.seed = seed
        self.cache_dir = os.path.join(cache_dir, "math-500")
        self.training = training

    def get_trainset(self):
        testset = self.get_testset()
        test_problems = set(item['problem'] for item in testset)

        os.makedirs(self.cache_dir, exist_ok=True)
        cache_file = os.path.join(self.cache_dir, f"trainset_size{self.eval_size}_seed{self.seed}.json")

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)

        ds = load_dataset(self.dataset_name)
        ds_shuffled = ds["test"].shuffle(seed=self.seed)

        processed_trainset = []
        for item in ds_shuffled:
            problem = item['problem']
            if problem not in test_problems:
                solution = item['solution']
                level = item['level']
                type = item['subject']

                processed_trainset.append({
                    'problem': problem,
                    'solution': solution,
                    'level': level,
                    'type': type
                })
                
                if len(processed_trainset) >= self.eval_size:
                    break

        with open(cache_file, 'w') as f:
            json.dump(processed_trainset, f, indent=2)

        return processed_trainset

    def get_testset(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        cache_file = os.path.join(self.cache_dir, f"testset_size{self.eval_size}_seed{self.seed}.json")

        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                return json.load(f)

        ds = load_dataset(self.dataset_name)
        testset = ds["test"].shuffle(seed=self.seed).select(range(self.eval_size))

        processed_testset = []
        for item in testset:
            problem = item['problem']
            solution = item['solution']
            level = item['level']
            type = item['subject']

            processed_testset.append({
                'problem': problem,
                'solution': solution,
                'level': level,
                'type': type
            })

        with open(cache_file, 'w') as f:
            json.dump(processed_testset, f, indent=2)

        return processed_testset

    def get_dataset(self):
        if self.training:
            return self.get_trainset()
        else:
            return self.get_testset()