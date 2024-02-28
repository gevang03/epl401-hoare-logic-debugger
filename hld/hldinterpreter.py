#!/usr/bin/env python3

from typing import NamedTuple
from enum import IntEnum, auto, unique

@unique
class Opcode(IntEnum):
    NOP = 0             # nop
    NEG = auto()        # stack[-1] < -stack[-1]
    NOT = auto()        # stack[-1] <- !stack[-1]
    ADD = auto()        # stack[-1] <- stack[-1] + value
    SUB = auto()        # stack[-1] <- stack[-1] - value
    MUL = auto()        # stack[-1] <- stack[-1] * value
    LT = auto()         # stack[-1] <- stack[-1] < value
    LE = auto()         # stack[-1] <- stack[-1] <= value
    EQ = auto()         # stack[-1] <- stack[-1] == value
    NE = auto()         # stack[-1] <- stack[-1] != value
    GE = auto()         # stack[-1] <- stack[-1] >= value
    GT = auto()         # stack[-1] <- stack[-1] > value
    LOAD = auto()       # stack[-1] <- stack[arg]
    STORE = auto()      # stack[arg] <- stack[-1]
    CONST = auto()      # stack[-1] <- arg
    JMP = auto()        # goto arg
    JMP_IF = auto()     # if stack[-1] != 0 goto y
    JMP_UNLESS = auto() # if stack[-1] == 0 goto y
    ASSERT = auto()     # if stack[-1] == 0 die
    ENTER = auto()      # len(stack) += arg
    FRAME = auto()
    CALL = auto()       # calls[-1] = ip+1; ip = arg
    RET = auto()        # calls[-1] = ip

Inst = NamedTuple('Inst', op=Opcode, arg=int)

class Vm:
    def __init__(self, prog: list[Inst], strtab: list[str]):
        self.prog = prog
        self.strtab = strtab

    def run(self, start: int, args: list[int]) -> int:
        prog = self.prog
        stack = args[:]
        calls: list[int] = []
        frames: list[list[int]] = []
        ip = start
        length = len(prog)
        def nop():
            pass
        def neg():
            stack[-1] = -stack[-1]
        def not_():
            stack[-1] = 1 if stack[-1] == 0 else 0
        def add():
            value = stack.pop()
            stack[-1] = stack[-1] + value
        def sub():
            value = stack.pop()
            stack[-1] = stack[-1] - value
        def mul():
            value = stack.pop()
            stack[-1] = stack[-1] * value
        def lt():
            value = stack.pop()
            stack[-1] = int(stack[-1] < value)
        def le():
            value = stack.pop()
            stack[-1] = int(stack[-1] <= value)
        def eq():
            value = stack.pop()
            stack[-1] = int(stack[-1] == value)
        def ne():
            value = stack.pop()
            stack[-1] = int(stack[-1] != value)
        def ge():
            value = stack.pop()
            stack[-1] = int(stack[-1] >= value)
        def gt():
            value = stack.pop()
            stack[-1] = int(stack[-1] > value)
        def load():
            value = stack[inst.arg]
            stack.append(value)
        def store():
            value = stack.pop()
            stack[inst.arg] = value
        def const():
            stack.append(inst.arg)
        def jmp():
            nonlocal ip
            ip = inst.arg - 1
        def jmp_if():
            nonlocal ip
            if stack.pop() != 0:
                ip = inst.arg - 1
        def jmp_unless():
            nonlocal ip
            if stack.pop() == 0:
                ip = inst.arg - 1
        def assert_():
            nonlocal ip
            if stack.pop() == 0:
                raise RuntimeError(self.strtab[inst.arg])
        def enter():
            n = inst.arg - len(stack)
            if n > 0:
                stack.extend(0 for _ in range(n))
        def frame():
            nonlocal stack
            tmp = stack
            frames.append(tmp[:-inst.arg])
            stack = stack[-inst.arg:]
        def call():
            nonlocal ip
            calls.append(ip)
            ip = inst.arg - 1
        def ret():
            nonlocal ip
            nonlocal stack
            try:
                ip = calls.pop()
                value = stack.pop()
                stack = frames.pop()
                stack.append(value)
            except IndexError:
                ip = length
        code: list = [None] * len(Opcode)
        code[Opcode.NOP] = nop
        code[Opcode.NEG] = neg
        code[Opcode.NOT] = not_
        code[Opcode.ADD] = add
        code[Opcode.SUB] = sub
        code[Opcode.MUL] = mul
        code[Opcode.LT] = lt
        code[Opcode.LE] = le
        code[Opcode.EQ] = eq
        code[Opcode.NE] = ne
        code[Opcode.GE] = ge
        code[Opcode.GT] = gt
        code[Opcode.LOAD] = load
        code[Opcode.STORE] = store
        code[Opcode.CONST] = const
        code[Opcode.JMP] = jmp
        code[Opcode.JMP_IF] = jmp_if
        code[Opcode.JMP_UNLESS] = jmp_unless
        code[Opcode.ASSERT] = assert_
        code[Opcode.ENTER] = enter
        code[Opcode.FRAME] = frame
        code[Opcode.CALL] = call
        code[Opcode.RET] = ret
        while ip < length:
            inst = prog[ip]
            code[inst.op]()
            ip += 1
        return stack[-1]
