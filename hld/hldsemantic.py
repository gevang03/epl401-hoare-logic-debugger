#!/usr/bin/env python3

from hldast import *
from functools import cache, singledispatchmethod
from enum import Enum

class ValueType(Enum):
    Int = 'int'
    Bool = 'bool'

def check_declaration(declaration: Declaration):
    ctx = __Context()
    return ctx.check_declaration(declaration)

class __Context:
    def __init__(self):
        self.variables: dict[str, ValueType] = {}
        self.in_metacond = False

    def typecheck_meta(self, expr: Expr, expected: ValueType):
        prev = self.in_metacond
        self.in_metacond = True
        self.typecheck(expr, expected)
        self.in_metacond = prev

    def typecheck(self, expr: Expr, expected: ValueType):
        actual = self.typeof(expr)
        if actual != expected:
            expr.error(f'expected {expected.value}, got {actual.value}')

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
        if expr.value[0] == '$':
            if not self.in_metacond:
                expr.error(f'symbolic variable `{expr.value}` is not allowed outside of meta conditions')
            return ValueType.Int
        try:
            return self.variables[expr.value]
        except:
            expr.error(f'variable `{expr.value}` not defined')

    @typeof.register
    def _(self, pref: PrefixArithmeticExpr) -> ValueType:
        self.typecheck(pref.expr, ValueType.Int)
        return ValueType.Int

    @typeof.register
    def _(self, pref: PrefixLogicalExpr) -> ValueType:
        self.typecheck(pref.expr, ValueType.Bool)
        return ValueType.Bool

    @typeof.register
    def _(self, expr: InfixArithmeticExpr) -> ValueType:
        self.typecheck(expr.left, ValueType.Int)
        self.typecheck(expr.right, ValueType.Int)
        return ValueType.Int

    @typeof.register
    def _(self, expr: InfixRelationalExpr) -> ValueType:
        self.typecheck(expr.left, ValueType.Int)
        self.typecheck(expr.right, ValueType.Int)
        return ValueType.Bool

    @typeof.register
    def _(self, expr: InfixLogicalExpr) -> ValueType:
        self.typecheck(expr.left, ValueType.Bool)
        self.typecheck(expr.right, ValueType.Bool)
        return ValueType.Bool

    @singledispatchmethod
    def check_statement(self, _: Statement):
        raise NotImplementedError

    @check_statement.register
    def _(self, assignment: Assignment):
        etype = self.typeof(assignment.value)
        dest = assignment.dest.value
        if dest[0] == '$':
            assignment.error(f'cannot assign to symbolic variable `{dest}`')
        try:
            old = self.variables[dest]
            if old != etype:
                assignment.error(f'expected {old}, got {etype}')
        except KeyError:
            self.variables[dest] = etype

    @check_statement.register
    def _(self, ifelse: IfElse):
        self.typecheck(ifelse.cond, ValueType.Bool)
        self.check_statement(ifelse.then_block)
        self.check_statement(ifelse.else_block)

    @check_statement.register
    def _(self, while_: While):
        if while_.invariant != None:
            self.typecheck_meta(while_.invariant, ValueType.Bool)
        if while_.variant != None:
            self.typecheck_meta(while_.variant, ValueType.Int)
        self.typecheck(while_.cond, ValueType.Bool)
        self.check_statement(while_.body)

    @check_statement.register
    def _(self, block: Block):
        for statement in block.statements:
            self.check_statement(statement)

    @check_statement.register
    def _(self, assert_: Assert):
        self.typecheck(assert_.expr, ValueType.Bool)

    @singledispatchmethod
    def check_declaration(self, _: Declaration):
        raise NotImplementedError

    @check_declaration.register
    def _(self, proc: Proc):
        for param in proc.params:
            value = param.value
            if value in self.variables:
                param.error(f'duplicate parameter `{value}`')
            self.variables[value] = ValueType.Int
        if proc.pre != None:
            self.typecheck_meta(proc.pre, ValueType.Bool)
        self.check_statement(proc.body)
        if proc.post != None:
            self.typecheck_meta(proc.post, ValueType.Bool)
