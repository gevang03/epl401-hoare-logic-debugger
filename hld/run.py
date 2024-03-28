#!/usr/bin/env python3

import hldast
import hldcompiler
import hldparser
import hldsemantic

import optparse
import pyparsing
import sys

from typing import Optional

def parse_args(argv: list[str]) -> tuple[optparse.Values, list[str]]:
    usage = 'usage: %prog [options] filename'
    p = optparse.OptionParser(usage=usage)
    p.add_option('--total',
                 action='store_const',
                 default='partial',
                 const='total',
                 dest='correctness',
                 help='enforce total correctness instead of partial'
                 )
    p.add_option('--trace',
                 action='store_true',
                 default=False,
                 help='display inferences step by step'
                 )
    p.add_option('--run',
                 metavar='\'FN [ARGS...]\'',
                 action='store',
                 type='string',
                 help='run program with entry point FN with ARGS'
                 )
    p.add_option('--dis',
                 action='store_true',
                 default=False,
                 help='disassemble vm'
                 )
    p.add_option('--ai',
                 action='store_true',
                 default=False,
                 help='ask ai assistant in case of an error'
                 )
    p.add_option('--interactive',
                action='store_true',
                default=False,
                help='interactively apply changes made by the assistant'
    )
    return p.parse_args(argv)

def run(filename: str, call: str) -> Optional[int]:
    import hldinterpreter
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    hldsemantic.check_program(decls)
    try:
        proc, *args = call.split()
        args = list(map(int, args))
    except ValueError:
        print('error: malformed entry point argument', file=sys.stderr)
        exit(1)
    procs, prog, strtab = hldcompiler.compile_program(decls)
    try:
        start = procs[proc]
    except KeyError:
        print(f'error: proc `{proc}` is not defined', file=sys.stderr)
        return 1
    vm = hldinterpreter.Vm(prog, strtab)
    try:
        result = vm.run(start, args)
        print(result)
    except RuntimeError as e:
        print(f'{filename}:{e.args[0]}', file=sys.stderr)
        return 1

def dis(filename: str) -> Optional[int]:
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    hldsemantic.check_program(decls)
    _, prog, _ = hldcompiler.compile_program(decls)
    for i, (opcode, arg) in enumerate(prog):
        print(f'{i:04x} {opcode.name} {arg:04x}')

def debug(filename: str, correctness_str: str):
    import hlddebug
    correctness = hlddebug.Correctness(correctness_str)
    decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
    assert isinstance(decls, list)
    symtab, call_graph = hldsemantic.check_program(decls)
    pres = hlddebug.get_pre(decls, correctness, symtab, call_graph)
    for sym, pre in pres.items():
        print(f'proc {sym}(...) {{...}} requires `{pre}`')


def ai(filename: str, correctness_str: str, interactive: bool) -> Optional[int]:
    import hldai
    import hlddebug
    import openai

    def ask(filename: str, err: str) -> Optional[str]:
        try:
            return hldai.ask_assistant(filename, err)
        except openai.APIConnectionError as e:
            print('The openai server could not be reached', file=sys.stderr)
            print(e.__cause__, file=sys.stderr)  # an underlying Exception, likely raised within httpx.
        except openai.RateLimitError as e:
            print('A 429 status code was received; rate limit error.', file=sys.stderr)
        except openai.APIStatusError as e:
            print(f'openai: {e.status_code}: {e.response}', file=sys.stderr)

    def update_program(response: str, filename: str) -> bool:
        try:
            start = response.index('```')
            end = response.index('```', start + 4)
        except IndexError:
            return False
        new_program = response[start+4:end-1]
        yn = input('Apply proposed changes and retry? (Y/n) ')
        while True:
            if yn in ['y', 'Y']:
                with open(filename, 'w') as f:
                    f.write(new_program)
                return True
            elif yn in ['n', 'N']:
                return False
            else:
                yn = input('invalid input (Y/n) ')

    correctness = hlddebug.Correctness(correctness_str)
    while True:
        decls = hldparser.parser.parse_file(filename, parse_all=True).as_list()
        assert isinstance(decls, list)
        symtab, call_graph = hldsemantic.check_program(decls)
        try:
            pres = hlddebug.get_pre(decls, correctness, symtab, call_graph)
            for sym, pre in pres.items():
                print(f'proc {sym}(...) {{...}} requires `{pre}`')
            return 0
        except hldast.HLDError as e:
            response = ask(filename, e.args[0])
            if response is None:
                return 1
            print(response, file=sys.stderr)
            if not interactive:
                return 1
            if not update_program(response, filename):
                return 1

def main(argv: list[str]) -> Optional[int]:
    options, args = parse_args(argv)
    try:
        filename = args[1]
    except IndexError:
        print('error: no file provided', file=sys.stderr)
        return 1
    try:
        if options.run != None:
            assert isinstance(options.run, str)
            return run(filename, options.run)
        elif options.dis:
            return dis(filename)
        elif options.ai:
            return ai(filename, options.correctness, options.interactive)
        else:
            return debug(filename, options.correctness)
    except OSError as os_err:
        print(f'error: {os_err.filename}: {os_err.strerror}', file=sys.stderr)
        return 1
    except pyparsing.exceptions.ParseBaseException as pe:
        print(pe.explain(depth=0), file=sys.stderr)
        return 1
    except hldast.HLDError as pe:
        print(f'{filename}:{pe.args[0]}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    status = main(sys.argv)
    sys.exit(status)
