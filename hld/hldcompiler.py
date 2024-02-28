#!/usr/bin/env python3

from functools import singledispatchmethod
from hldast import *
from hldinterpreter import Opcode, Inst

class __Context:
    __bin_arith_opcodes = {
        '*': Opcode.MUL,
        '+': Opcode.ADD,
        '-': Opcode.SUB,
    }
    __bin_rel_opcodes = {
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
        self.procs: dict[str, int] = {}
        self.calls: dict[int, str] = {}
        self.strtab: list[str] = []

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

    @singledispatchmethod
    def compile(self, _: ASTNode):
        raise NotImplementedError

    @compile.register
    def _(self, expr: BoolLiteral):
        self.emit(Opcode.CONST, int(expr.value))

    @compile.register
    def _(self, expr: IntLiteral):
        self.emit(Opcode.CONST, expr.value)

    @compile.register
    def _(self, expr: Identifier):
        src = self.get_variable(expr.value)
        self.emit(Opcode.LOAD, src)

    @compile.register
    def _(self, pref: PrefixArithmeticExpr):
        if pref.op == '+':
            self.compile(pref.expr)
        else:
            assert pref.op == '-'
            self.compile(pref.expr)
            self.emit(Opcode.NEG)

    @compile.register
    def _(self, pref: PrefixLogicalExpr):
        assert pref.op == '!'
        self.compile(pref.expr)
        self.emit(Opcode.NOT)

    @compile.register
    def _(self, expr: InfixArithmeticExpr):
        self.compile(expr.left)
        self.compile(expr.right)
        opcode = self.__bin_arith_opcodes[expr.op]
        self.emit(opcode)

    @compile.register
    def _(self, expr: InfixRelationalExpr):
        self.compile(expr.left)
        self.compile(expr.right)
        opcode = self.__bin_rel_opcodes[expr.op]
        self.emit(opcode)

    @compile.register
    def _(self, expr: InfixLogicalExpr):
        if expr.op == '||':
            self.compile(expr.left)
            l = len(self.prog)
            self.emit(Opcode.JMP_IF)
            self.compile(expr.right)
            self.backpatch(l)
        else:
            assert expr.op == '&&'
            self.compile(expr.left)
            l = len(self.prog)
            self.emit(Opcode.JMP_UNLESS)
            self.compile(expr.right)
            self.backpatch(l)

    @compile.register
    def _(self, ternary: TernaryExpr):
        self.compile(ternary.cond)
        l0 = len(self.prog)
        self.emit(Opcode.JMP_UNLESS)
        self.compile(ternary.then_expr)
        l1 = len(self.prog)
        self.emit(Opcode.JMP)
        self.backpatch(l0)
        self.compile(ternary.else_expr)
        self.backpatch(l1)

    @compile.register
    def _(self, call: CallExpr):
        for arg in reversed(call.args):
            self.compile(arg)
        callee = call.callee.value
        try:
            self.emit(Opcode.FRAME, len(call.args))
            self.emit(Opcode.CALL, self.procs[callee])
        except KeyError:
            self.emit(Opcode.CALL)
            self.calls[len(self.prog)-1] = callee

    @compile.register
    def _(self, assignment: Assignment):
        self.compile(assignment.value)
        dest = self.get_variable(assignment.dest.value)
        self.emit(Opcode.STORE, dest)

    @compile.register
    def _(self, ifelse: IfElse):
        self.compile(ifelse.cond)
        l0 = len(self.prog)
        self.emit(Opcode.JMP_UNLESS)
        self.compile(ifelse.then_block)
        l1 = len(self.prog)
        self.emit(Opcode.JMP)
        self.backpatch(l0)
        self.compile(ifelse.else_block)
        self.backpatch(l1)

    @compile.register
    def _(self, while_: While):
        l0 = len(self.prog)
        self.compile(while_.cond)
        l1 = len(self.prog)
        self.emit(Opcode.JMP_UNLESS)
        self.compile(while_.body)
        self.emit(Opcode.JMP, l0)
        self.backpatch(l1)

    @compile.register
    def _(self, block: Block):
        for statement in block.statements:
            self.compile(statement)

    @compile.register
    def _(self, assert_: Assert):
        self.compile(assert_.expr)
        self.emit(Opcode.ASSERT, len(self.strtab))
        lineno = pyparsing.lineno(assert_.loc, assert_.src)
        col = pyparsing.col(assert_.loc, assert_.src)
        line = pyparsing.line(assert_.loc, assert_.src)
        ptr = f'{" " * (col-1)}^'
        self.strtab.append(f'{lineno}:{col}: error: assertion failed\n{line}\n{ptr}')

    @compile.register
    def _(self, return_: Return):
        self.compile(return_.expr)
        self.emit(Opcode.RET)

    @compile.register
    def _(self, proc: Proc):
        start = len(self.prog)
        self.procs[proc.name.value] = start
        self.emit(Opcode.ENTER)
        for param in proc.params:
            self.allocate_variable(param.value)
        self.compile(proc.body)
        self.prog[start] = Inst(Opcode.ENTER, len(self.vars))

    def compile_program(self, decls: list[Declaration]) -> tuple[dict[str, int], list[Inst], list[str]]:
        for decl in decls:
            if isinstance(decl, Proc):
                self.compile(decl)
                self.vars = {}
        for i, callee in self.calls.items():
            assert self.prog[i].op == Opcode.CALL
            self.prog[i] = Inst(Opcode.CALL, self.procs[callee])
        return self.procs, self.prog, self.strtab

    def backpatch(self, inst: int, to: int | None = None):
        if to == None:
            to = len(self.prog)
        self.prog[inst] = Inst(self.prog[inst].op, to)

def compile_program(decls: list[Declaration]) -> tuple[dict[str, int], list[Inst], list[str]]:
    ctx = __Context()
    return ctx.compile_program(decls)
