<div align="center">

# 🧠 MultiSessionCollab

<!-- ### Learning User Preferences Through Interaction for Long-Term Collaboration -->

[![Paper](https://img.shields.io/badge/arXiv-Paper-b31b1b.svg)]()
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

**MultiSessionCollab** is a benchmark for evaluating how well conversational agents learn user preferences and leverage it to meaningfully improve interactions during multi-session collaboration.

**Paper**:
- <u> [Learning User Preferences Through Interaction for Long-Term Collaboration]() </u>


---

## 🚀 Quick Start

### Setup
 1. Clone this repository:
 
```bash
git clone ***
```

2. Create virtual environment:
```bash
python3 -m venv env_multisessioncollab
source env_multisessioncollab/bin/activate
```

3. Install from source:
```bash
pip install -e .
```

### Launch Servers

We recommend using [SGLang](https://github.com/sgl-project/sglang) to host the user simulator, agent, and judge models. Follow their installation instructions.

Once ready, let's launch the servers:

1. **User Simulator and Judge**: for our benchmark, we always use Llama-3.3-70B-Instruct:
```bash
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3.3-70B-Instruct \
    --port 8004 \
    --tp-size 4
```

2. **Conversational Agent**: this is the model we want to evaluate. We will use Llama-3.3-70B-Instruct for the example:
```bash
python -m sglang.launch_server \
    --model-path meta-llama/Llama-3.3-70B-Instruct \
    --port 8003 \
    --tp-size 4
```

---

### Run Evaluations

Now, we can run the evaluation for the conversational agent. Below is a script that runs it for two settings: (1) a standard agent without memory and (2) a long-term collaborative agent equipped with memory.

```bash
#!/bin/bash
BATCH_SIZE=50
EVAL_SIZE=20
mkdir -p outputs

for DATASET in math-hard math-500 logiqa mmlu medqa; do
    DATASET_FILE=$(echo ${DATASET} | tr '-' '_')
    
    echo "Running: ${DATASET}"
    
    # Without memory
    python3 run.py \
        --experiment_type agent_without_memory \
        --dataset ${DATASET} \
        --eval_size ${EVAL_SIZE} \
        --max_turns 10 \
        --batch_size ${BATCH_SIZE} \
        --user_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --user_api_base http://localhost:8004/v1 \
        --user_api_key EMPTY \
        --collaborator_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --collaborator_api_base http://localhost:8003/v1 \
        --collaborator_api_key EMPTY \
        --judge_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --judge_api_base http://localhost:8004/v1 \
        --judge_api_key EMPTY \
        --output_file ./outputs/${DATASET_FILE}_without_memory.jsonl \
        >> ./outputs/${DATASET_FILE}_without_memory.out 2>&1

    # With memory
    python3 run.py \
        --experiment_type agent_with_memory \
        --dataset ${DATASET} \
        --eval_size ${EVAL_SIZE} \
        --max_turns 10 \
        --batch_size ${BATCH_SIZE} \
        --user_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --user_api_base http://localhost:8004/v1 \
        --user_api_key EMPTY \
        --collaborator_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --collaborator_api_base http://localhost:8003/v1 \
        --collaborator_api_key EMPTY \
        --judge_model_name hosted_vllm/meta-llama/Llama-3.3-70B-Instruct \
        --judge_api_base http://localhost:8004/v1 \
        --judge_api_key EMPTY \
        --output_file ./outputs/${DATASET_FILE}_with_memory.jsonl \
        >> ./outputs/${DATASET_FILE}_with_memory.out 2>&1
done
```


Here are the argument descriptions:

| Argument | Description |
|----------|-------------|
| `--experiment_type` | `agent_without_memory` or `agent_with_memory` |
| `--dataset` | Dataset name: `math-hard`, `math-500`, `logiqa`, `mmlu`, `medqa` |
| `--eval_size` | Number of sessions per user |
| `--max_turns` | Maximum conversation turns |
| `--batch_size` | Parallel processing batch size |
| `--user_model_name` | User simulator model |
| `--collaborator_model_name` | Conversational agent model |
| `--judge_model_name` | Model for evaluating accuracy |
| `--output_file` | Output file |

```