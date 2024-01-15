#!/usr/bin/env python3

from hldast import *
from functools import cache, singledispatchmethod
from enum import IntEnum, auto

class ValueType(IntEnum):
    Int = auto()
    Bool = auto()

def check_declaration(declaration: Declaration):
    ctx = __Context()
    return ctx.check_declaration(declaration)

class __Context:
    def __init__(self):
        self.variables: dict[str, ValueType] = {}

    @singledispatchmethod
    @cache
    def typeof(self, _: Expr) -> ValueType:
        raise NotImplementedError

    @typeof.register
    def _(self, _: BoolLiteral) -> ValueType: 
        return ValueType.Bool

    @typeof.register
    def _(self, _: IntLiteral) -> ValueType:
        return ValueType.Int

    @typeof.register
    def _(self, expr: Identifier) -> ValueType:
        return self.variables[expr.value]

    @typeof.register
    def _(self, pref: PrefixArithmeticExpr) -> ValueType:
        if self.typeof(pref.expr) != ValueType.Int:
            raise RuntimeError(pref.error('Type error'))
        return ValueType.Int

    @typeof.register
    def _(self, pref: PrefixLogicalExpr) -> ValueType:
        if self.typeof(pref.expr) != ValueType.Bool:
            raise RuntimeError(pref.error('Type error'))
        return ValueType.Bool

    @typeof.register
    def _(self, expr: InfixArithmeticExpr) -> ValueType:
        if self.typeof(expr.left) != ValueType.Int \
            or self.typeof(expr.right) != ValueType.Int:
            raise RuntimeError(expr.error('Type error'))
        return ValueType.Int

    @typeof.register
    def _(self, expr: InfixRelationalExpr) -> ValueType:
        if self.typeof(expr.left) != ValueType.Int \
            or self.typeof(expr.right) != ValueType.Int:
            raise RuntimeError(expr.error('Type error'))
        return ValueType.Bool

    @typeof.register
    def _(self, expr: InfixLogicalExpr) -> ValueType:
        if self.typeof(expr.left) != ValueType.Bool \
            or self.typeof(expr.right) != ValueType.Bool:
            raise RuntimeError(expr.error('Type error'))
        return ValueType.Bool

    @singledispatchmethod
    def check_statement(self, _: Statement):
        raise NotImplementedError

    @check_statement.register
    def _(self, assignment: Assignment):
        etype = self.typeof(assignment.value)
        dest = assignment.dest.value
        old = self.variables.get(dest)
        if old == None:
            self.variables[dest] = etype
        elif old != etype:
            raise RuntimeError(assignment.error('Type error'))

    @check_statement.register
    def _(self, ifelse: IfElse):
        if self.typeof(ifelse.cond) != ValueType.Bool:
            raise RuntimeError(ifelse.error('Type error'))
        self.check_statement(ifelse.then_block)
        self.check_statement(ifelse.else_block)

    @check_statement.register
    def _(self, while_: While):
        if while_.invariant != None and self.typeof(while_.invariant) != ValueType.Bool:
            raise RuntimeError(while_.error('Type error'))
        if while_.variant != None and self.typeof(while_.variant) != ValueType.Int:
            raise RuntimeError(while_.error('Type error'))
        if self.typeof(while_.cond) != ValueType.Bool:
            raise RuntimeError(while_.error('Type error'))
        self.check_statement(while_.body)

    @check_statement.register
    def _(self, block: Block):
        for statement in block.statements:
            self.check_statement(statement)

    @singledispatchmethod
    def check_declaration(self, _: Declaration):
        raise NotImplementedError

    @check_declaration.register
    def _(self, proc: Proc):
        for param in proc.params:
            value = param.value
            if value in self.variables:
                raise RuntimeError(param.error('Duplicate parameter variable'))
            self.variables[value] = ValueType.Int
        if proc.pre != None and self.typeof(proc.pre) != ValueType.Bool:
            raise RuntimeError(proc.pre.error('Type error'))
        self.check_statement(proc.body)
        if proc.post != None and self.typeof(proc.post) != ValueType.Bool:
            raise RuntimeError(proc.post.error('Type error'))
