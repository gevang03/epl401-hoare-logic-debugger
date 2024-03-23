#!/usr/bin/env python3

import sys
import openai

_assistant_behavior = '''\
You are an assistant for a procedural programming language where \
each procedure is verified using Hoare logic and backwards inferences. \
Hoare Logic clauses are prefixed by '#'. \
fn functions are used to describe specifications. \
Values prefixed by `e!` refer to variant bounds. \
Comments starting with `///` are user hints about what they think the error is. \
Users provide the program and an error message trying to figure out \
what is wrong with their program. Either some statement or expression in the program, \
or some precondition, postcondition, variant, invariant may be wrong. \
'''

def ask_assistant(filename: str, err: str) -> str:
    model = 'gpt-3.5-turbo'
    prog = open(filename, 'r').read()
    print(f'{filename}:{err}', file=sys.stderr)
    print(f'Asking AI ({model}) assistant...\n', file=sys.stderr)
    completion = openai.chat.completions.create(model=model, messages=[
        {
            'role': 'system',
            'content': _assistant_behavior
        },
        {
            'role': 'user',
            'content': f'What is wrong with the following program: ```{prog}```\n\
The compiler gives the following error message: {err}.'
        }
    ])
    response = completion.choices[0].message.content
    assert response is not None
    return response
