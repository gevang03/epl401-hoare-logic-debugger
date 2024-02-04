#!/usr/bin/env python3

from hldast import *
from functools import cache, singledispatchmethod
from enum import Enum

class ValueType(Enum):
    Int = 'int'
    Bool = 'bool'

def check_program(decls: list[Declaration]) -> dict[str, dict[str, ValueType]]:
    ctx = __Context()
    return ctx.check_program(decls)

class __Context:
    def __init__(self):
        self.decls: dict[str, Declaration] = {}
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
            self.variables[expr.value] = ValueType.Int
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

    @typeof.register
    def _(self, expr: TernaryExpr) -> ValueType:
        self.typecheck(expr.cond, ValueType.Bool)
        then_type = self.typeof(expr.then_expr)
        self.typecheck(expr.else_expr, then_type)
        return then_type

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

    @check_statement.register
    def _(self, return_: Return):
        self.typecheck(return_.expr, ValueType.Int)

    @singledispatchmethod
    def check_declaration(self, _: Declaration):
        raise NotImplementedError

    @check_declaration.register
    def _(self, proc: Proc):
        self.check_params(proc)
        if proc.pre != None:
            self.typecheck_meta(proc.pre, ValueType.Bool)
        self.check_statement(proc.body)
        if proc.post != None:
            self.typecheck_meta(proc.post, ValueType.Bool)

    @check_declaration.register
    def _(self, fn: Fn):
        self.check_params(fn)
        if fn.pre != None:
            self.typecheck_meta(fn.pre, ValueType.Bool)
        self.typecheck(fn.expr, ValueType.Int)

    def check_params(self, decl: Fn | Proc):
        for param in decl.params:
            value = param.value
            if value in self.variables:
                param.error(f'duplicate parameter `{value}`')
            if value[0] == '$':
                param.error(f'parameter `{value}` cannot be a symbolic value')
            self.variables[value] = ValueType.Int

    def check_program(self, decls: list[Declaration]) -> dict[str, dict[str, ValueType]]:
        symtab: dict[str, dict[str, ValueType]] = {}
        for decl in decls:
            assert isinstance(decl, (Fn, Proc))
            value = decl.name.value
            if value in self.decls:
                decl.error(f'duplicate declaration `{value}`')
            self.decls[decl.name.value] = decl
        for decl in decls:
            assert isinstance(decl, (Fn, Proc))
            value = decl.name.value
            self.check_declaration(decl)
            symtab[value] = self.variables
            self.variables = {}
        return symtab
