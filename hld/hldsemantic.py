#!/usr/bin/env python3

from hldast import *
from functools import cache, singledispatchmethod
from enum import Enum, IntFlag

class ValueType(Enum):
    Int = 'int'
    Bool = 'bool'

class ContextType(IntFlag):
    Code = 0b0001
    Metacond = 0b0010
    Postcond = 0b0110
    Assignment = 0b1001

def check_program(decls: list[Declaration]) -> tuple[dict[str, dict[str, ValueType]], dict[str, set[str]]]:
    ctx = __Context()
    return ctx.check_program(decls)

class __Context:
    def __init__(self):
        self.decls: dict[str, Declaration] = {}
        self.params: set[str] = set()
        self.variables: dict[str, ValueType] = {}
        self.ctx_type: ContextType = ContextType.Code
        self.callees: set[str] = set()

    def _ctx_is(self, ctx_type: ContextType) -> bool:
        return self.ctx_type & ctx_type == ctx_type

    def typeof_with_ctx(self, expr: Expr, ctx_type: ContextType) -> ValueType:
        prev = self.ctx_type
        self.ctx_type = ctx_type
        type = self.typeof(expr)
        self.ctx_type = prev
        return type

    def typecheck_with_ctx(self, expr: Expr, expected: ValueType, ctx_type: ContextType):
        prev = self.ctx_type
        self.ctx_type = ctx_type
        self.typecheck(expr, expected)
        self.ctx_type = prev

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
        if expr.op in { '/', '%' } and not self._ctx_is(ContextType.Metacond) and not self._ctx_is(ContextType.Assignment):
            expr.error(f'`{expr.op}` can only occur directly in an assignment or in a metacondition')
        prev = self.ctx_type
        if self._ctx_is(ContextType.Assignment):
            self.ctx_type = ContextType.Code
        self.typecheck(expr.left, ValueType.Int)
        self.typecheck(expr.right, ValueType.Int)
        self.ctx_type = prev
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

    @typeof.register
    def _(self, call: CallExpr) -> ValueType:
        if self._ctx_is(ContextType.Metacond):
            return self._typeof_metacond(call)
        assert self._ctx_is(ContextType.Code)
        return self._typeof_code(call)

    def _typeof_metacond(self, call: CallExpr) -> ValueType:
        assert self._ctx_is(ContextType.Metacond)
        name = call.callee.value
        try:
            decl = self.decls[name]
            if isinstance(decl, Proc):
                call.error(f'proc `{name} cannot be called in metacondition')
            fn = decl
            assert isinstance(fn, Fn)
            expected = len(fn.params)
            actual = len(call.args)
            if expected != actual:
                call.error(f'fn `{name}` expects {expected} arguments, but was given {actual}')
        except KeyError:
            call.error(f'fn `{name}` not defined')
        for arg in call.args:
            self.typecheck(arg, ValueType.Int)
        return ValueType.Int

    def _typeof_code(self, call: CallExpr) -> ValueType:
        assert self._ctx_is(ContextType.Code)
        name = call.callee.value
        if not self._ctx_is(ContextType.Assignment):
            call.error('call expressions must be directly assigned to local variables')
        try:
            decl = self.decls[name]
            if isinstance(decl, Fn):
                call.error(f'fn `{name} cannot be called in code')
            proc = decl
            assert isinstance(proc, Proc)
            expected = len(proc.params)
            actual = len(call.args)
            if expected != actual:
                call.error(f'proc `{name}` expects {expected} arguments, but was given {actual}')
        except KeyError:
            call.error(f'proc `{name}` not defined')
        self.ctx_type = ContextType.Code
        for arg in call.args:
            self.typecheck(arg, ValueType.Int)
        self.ctx_type = ContextType.Assignment
        return ValueType.Int

    @typeof.register
    def _(self, result: ResultExpr) -> ValueType:
        if not self._ctx_is(ContextType.Postcond):
            result.error('result expression are not allowed outside of postconditions')
        return ValueType.Int

    @singledispatchmethod
    def check_statement(self, _: Statement):
        raise NotImplementedError

    @check_statement.register
    def _(self, assignment: Assignment):
        dest = assignment.dest.value
        value = assignment.value
        if dest in self.params:
            value.error(f'cannot assign to parameter {dest}')
        if isinstance(value, CallExpr):
            etype = self.typeof_with_ctx(value, ContextType.Assignment)
            self.callees.add(value.callee.value)
        elif isinstance(value, InfixArithmeticExpr) and value.op in { '/', '%'}:
            etype = self.typeof_with_ctx(value, ContextType.Assignment)
        else:
            etype = self.typeof(value)
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
            self.typecheck_with_ctx(while_.invariant, ValueType.Bool, ContextType.Metacond)
        if while_.variant != None:
            self.typecheck_with_ctx(while_.variant, ValueType.Int, ContextType.Metacond)
        self.typecheck(while_.cond, ValueType.Bool)
        self.check_statement(while_.body)

    @check_statement.register
    def _(self, block: Block):
        n = len(block.statements)
        for i, statement in enumerate(block.statements):
            self.check_statement(statement)
            if isinstance(statement, Return) and i != n - 1:
                block.statements[i+1].error('statements after return are unreachable')

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
            self.typecheck_with_ctx(proc.pre, ValueType.Bool, ContextType.Metacond)
        if proc.post != None:
            self.typecheck_with_ctx(proc.post, ValueType.Bool, ContextType.Postcond)
        self.check_statement(proc.body)
        self.check_return_end(proc.body)

    @check_declaration.register
    def _(self, fn: Fn):
        self.check_params(fn)
        self.typecheck_with_ctx(fn.expr, ValueType.Int, ContextType.Metacond)

    def check_return_end(self, block: Block):
        statements = block.statements
        if len(statements) == 0 or not isinstance(statements[-1], (IfElse, Return)):
            block.error('block has no return statement')
        last = statements[-1]
        if isinstance(last, IfElse):
            self.check_return_end(last.then_block)
            self.check_return_end(last.else_block)
        else:
            assert isinstance(last, Return)

    def check_params(self, decl: Fn | Proc):
        for param in decl.params:
            value = param.value
            if value in self.variables:
                param.error(f'duplicate parameter `{value}`')
            self.variables[value] = ValueType.Int
        assert len(self.variables) == len(decl.params)
        self.params = set(self.variables.keys())

    def check_program(self, decls: list[Declaration]) -> tuple[dict[str, dict[str, ValueType]], dict[str, set[str]]]:
        symtab: dict[str, dict[str, ValueType]] = {}
        call_graph: dict[str, set[str]] = {}
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
            call_graph[value] = self.callees
            self.callees = set()
        return symtab, call_graph
