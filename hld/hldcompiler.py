#!/usr/bin/env python3

import hldast
from hldinterpreter import Opcode, Inst

class __Context:
    __bin_opcodes = {
        '*': Opcode.MUL,
        '+': Opcode.ADD,
        '-': Opcode.SUB,
        '<=': Opcode.LE,
        '<': Opcode.LT,
        '>=': Opcode.GE,
        '>': Opcode.GT,
        '==': Opcode.EQ,
        '!=': Opcode.NE,
    }

    def __init__(self):
        self.vars: dict[str, int] = {}
        self.prog: list[Inst] = []

    def allocate_variable(self, id: str) -> int:
        i = len(self.vars)
        assert not id in self.vars
        self.vars[id] = i
        return i

    def get_variable(self, id: str) -> int:
        if not id in self.vars:
            return self.allocate_variable(id)
        return self.vars[id]

    def emit(self, opcode: Opcode, x=0):
        self.prog.append(Inst(opcode, x))

    def compile_expr(self, expr):
        ty = type(expr)
        if ty == str:
            src = self.get_variable(expr)
            self.emit(Opcode.LOAD, src)
        elif ty == int:
            self.emit(Opcode.CONST, expr)
        elif ty == bool:
            self.emit(Opcode.CONST, int(expr))
        elif ty == hldast.Prefix:
            op = expr.op
            if op == '+':
                self.compile_expr(expr.expr)
            elif op == '-':
                self.compile_expr(expr.expr)
                self.emit(Opcode.NEG)
            else:
                assert op == '!'
                self.compile_expr(expr.expr)
                self.emit(Opcode.NOT)
        else:
            assert ty == hldast.Infix
            self.compile_expr(expr.left)
            self.compile_expr(expr.right)
            op = expr.op
            opcode = self.__bin_opcodes.get(op, None)
            if opcode != None:
                self.emit(opcode)
                return
            if op == '||':
                self.compile_expr(expr.left)
                l = len(self.prog)
                self.emit(Opcode.JMP_IF)
                self.compile_expr(expr.right)
                self.backpatch(l)
            else:
                assert op == '&&'
                self.compile_expr(expr.left)
                l = len(self.prog)
                self.emit(Opcode.JMP_UNLESS)
                self.compile_expr(expr.right)
                self.backpatch(l)

    def backpatch(self, inst: int, to: int | None = None):
        if to == None:
            to = len(self.prog)
        self.prog[inst] = Inst(self.prog[inst].op, to)

    def compile_proc(self, proc: hldast.Proc):
        for param in proc.params:
            self.allocate_variable(param)
        self.compile_block(proc.body)
        self.emit(Opcode.NOP)

    def compile_statement(self, statement):
        ty = type(statement)
        if ty == hldast.Assignment:
            self.compile_expr(statement.expr)
            dest = self.get_variable(statement.dest)
            self.emit(Opcode.STORE, dest)
        elif ty == hldast.IfElse:
            self.compile_expr(statement.cond)
            l0 = len(self.prog)
            self.emit(Opcode.JMP_UNLESS)
            self.compile_block(statement.truthy)
            l1 = len(self.prog)
            self.emit(Opcode.JMP)
            self.backpatch(l0)
            self.compile_block(statement.falsey)
            self.backpatch(l1)
        else:
            assert ty == hldast.While
            l0 = len(self.prog)
            self.compile_expr(statement.cond)
            l1 = len(self.prog)
            self.emit(Opcode.JMP_UNLESS)
            self.compile_block(statement.body)
            self.emit(Opcode.JMP, l0)
            self.backpatch(l1)

    def compile_block(self, block):
        for statement in block:
            self.compile_statement(statement)

def compile_proc(proc: hldast.Proc) -> tuple[dict[str, int], list[Inst]]:
    ctx = __Context()
    ctx.compile_proc(proc)
    return ctx.vars, ctx.prog
