from .math_hard import MATHHard
from .math_500 import MATH500
from .logiqa import LogiQA
from .mmlu import MMLU
from .medqa import MedQA

datasets_info = {
    'math-hard': {
        'class': MATHHard,
        'task_description': "Work with the agent to solve this math problem:",
    },
    'math-500': {
        'class': MATH500,
        'task_description': "Work with the agent to solve this math problem:",
    },
    'logiqa': {
        'class': LogiQA,
        'task_description': "Work with the agent to solve this logical reasoning problem:",
    },
    'mmlu': {
        'class': MMLU,
        'task_description': "Work with the agent to solve this multiple choice problem:",
    },
    'medqa': {
        'class': MedQA,
        'task_description': "Work with the agent to solve this medical problem:",
    },
}