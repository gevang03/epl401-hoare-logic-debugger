#!/usr/bin/env python3

from typing import NamedTuple
from enum import IntEnum, auto

class Opcode(IntEnum):
    NEG = 0             # a <- -x
    NOT = auto()        # a <- !x
    ADD = auto()        # a <- x + y
    SUB = auto()        # a <- x - y
    MUL = auto()        # a <- x * y
    LT = auto()         # a <- x < y
    LE = auto()         # a <- x <= y
    EQ = auto()         # a <- x == y
    NE = auto()         # a <- x != y
    GE = auto()         # a <- x >= y
    GT = auto()         # a <- x > y
    LOAD = auto()       # a <- var[x]
    STORE = auto()      # var[x] <- a
    CONST = auto()      # a <- x
    JMP = auto()        # goto x
    JMP_IF = auto()     # if a goto x
    JMP_UNLESS = auto() # if !a goto x

Inst = NamedTuple('Inst', op=Opcode, x=int, y=int)

class Vm:
    def __init__(self, prog: list[Inst], regcount: int):
        self.prog = prog
        self.regcount = regcount

    def run(self):
        prog = self.prog
        regs: list[int] = [0] * self.regcount
        ip = 0
        acc: int = 0
        length = len(prog)
        def neg():
            nonlocal ip; nonlocal acc
            acc = -regs[inst.x]
        def not_():
            nonlocal ip; nonlocal acc
            acc = 1 if regs[inst.x] == 0 else 0
        def add():
            nonlocal ip; nonlocal acc
            acc = regs[inst.x] + regs[inst.y]
        def sub():
            nonlocal ip; nonlocal acc
            acc = regs[inst.x] - regs[inst.y]
        def mul():
            nonlocal ip; nonlocal acc
            acc = regs[inst.x] * regs[inst.y]
        def lt():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] < regs[inst.y])
        def le():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] <= regs[inst.y])
        def eq():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] == regs[inst.y])
        def ne():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] != regs[inst.y])
        def ge():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] >= regs[inst.y])
        def gt():
            nonlocal ip; nonlocal acc
            acc = int(regs[inst.x] > regs[inst.y])
        def load():
            nonlocal ip; nonlocal acc
            acc = regs[inst.x]
        def store():
            nonlocal ip; nonlocal acc
            regs[inst.x] = acc
        def jmp():
            nonlocal ip
            ip = inst.x - 1
        def jmp_if():
            nonlocal ip
            if inst.a:
                ip = inst.x - 1
        def jmp_unless():
            nonlocal ip
            if not inst.a:
                ip = inst.x - 1
        code: list = [None] * len(Opcode)
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
        code[Opcode.JMP] = jmp
        code[Opcode.JMP_IF] = jmp_if
        code[Opcode.JMP_UNLESS] = jmp_unless
        while ip < length:
            inst = prog[ip]
            code[inst.op]()
            ip += 1
        return regs
