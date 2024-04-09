#!/usr/bin/env python3

import sys
import time

from typing import Optional

import openai

def update_program(response: str, filename: str) -> bool:
    try:
        start = response.index('```')
        end = response.index('```', start + 4)
    except ValueError:
        return False
    yn = input('Apply proposed changes and retry? (Y/n) ')
    while True:
        if yn in ['y', 'Y']:
            new_program = response[start+4:end-1]
            with open(filename, 'w') as f:
                f.write(new_program)
            return True
        elif yn in ['n', 'N']:
            return False
        else:
            yn = input('invalid input (Y/n) ')

def _gen_message(filename: str, err: str) -> str:
    prog = open(filename, 'r').read()
    return f'What is wrong with the following program: \n```\n{prog}\n```\n\
The compiler gives the following error message: {err}.'

def ask_assistant(filename: str, err: str, client: openai.Client, assistant, thread) -> str:
    content = _gen_message(filename, err)
    print(f'{filename}:{err}', file=sys.stderr)
    print(f'Asking {assistant.name} ({assistant.model})...\n', file=sys.stderr)
    client.beta.threads.messages.create(thread_id=thread.id, content=content, role='user')
    runs = client.beta.threads.runs.create(thread_id=thread.id, assistant_id=assistant.id)
    while True:
        retr = client.beta.threads.runs.retrieve(run_id=runs.id, thread_id=thread.id)
        if retr.status == 'completed':
            messages = client.beta.threads.messages.list(thread_id=thread.id)
            return messages.data[0].content[0].text.value # type: ignore
        elif retr.status in ['queued', 'in_progress']:
            time.sleep(0.5)
        else:
            raise RuntimeError(retr.last_error)
