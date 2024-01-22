#!/usr/bin/env python3

import operator
import z3
from enum import Enum
from functools import cache, singledispatch, singledispatchmethod
from hldast import *

@singledispatch
@cache
def expr_to_z3(_: Expr) -> z3.BoolRef | z3.ArithRef:
    raise NotImplementedError

@expr_to_z3.register
def _(expr: BoolLiteral) -> z3.BoolRef:
    return z3.BoolVal(expr.value)

@expr_to_z3.register
def _(expr: IntLiteral) -> z3.IntNumRef:
    return z3.IntVal(expr.value)

@expr_to_z3.register
def _(expr: Identifier) -> z3.ArithRef:
    return z3.Int(expr.value)

@expr_to_z3.register
def _(pref: PrefixArithmeticExpr) -> z3.ArithRef:
    expr = expr_to_z3(pref.expr)
    assert isinstance(expr, z3.ArithRef)
    if pref.op == '+':
        return +expr
    else:
        assert pref.op == '-'
        return -expr

@expr_to_z3.register
def _(pref: PrefixLogicalExpr) -> z3.BoolRef:
    expr = expr_to_z3(pref.expr)
    assert isinstance(expr, z3.BoolRef)
    assert pref.op == '!'
    res = z3.Not(expr)
    assert isinstance(res, z3.BoolRef)
    return res

_infix_arith_ops = { '*': operator.mul, '+': operator.add, '-': operator.sub }

@expr_to_z3.register
def _(expr: InfixArithmeticExpr) -> z3.ArithRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    res = _infix_arith_ops[expr.op](left, right)
    assert isinstance(res, z3.ArithRef)
    return res

_infix_logical_ops = { '&&': z3.And, '||': z3.Or }

@expr_to_z3.register
def _(expr: InfixLogicalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.BoolRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.BoolRef)
    res = _infix_logical_ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res

_infix_rel_ops = {
    '<=': operator.le, '<': operator.lt,
    '>=': operator.ge, '>': operator.gt,
    '==': operator.eq, '!=': operator.ne
}

@expr_to_z3.register
def _(expr: InfixRelationalExpr) -> z3.BoolRef:
    left = expr_to_z3(expr.left)
    assert isinstance(left, z3.ArithRef)
    right = expr_to_z3(expr.right)
    assert isinstance(right, z3.ArithRef)
    res = _infix_rel_ops[expr.op](left, right)
    assert isinstance(res, z3.BoolRef)
    return res

class Correctness(Enum):
    PARTIAL = 'partial'
    TOTAL = 'total'

class __Context:
    def __init__(self, correctness: Correctness):
        self.correctness = correctness

    @singledispatchmethod
    def propagate(self, _: Statement, _post: z3.BoolRef) -> z3.BoolRef:
        raise NotImplementedError

    @propagate.register
    def _(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        dest = expr_to_z3(assignment.dest)
        value = expr_to_z3(assignment.value)
        res = z3.substitute(post, (dest, value))
        assert isinstance(res, z3.BoolRef)
        return res

    @propagate.register
    def _(self, ifelse: IfElse, post: z3.BoolRef) -> z3.BoolRef:
        then_block = self.propagate(ifelse.then_block, post)
        else_block = self.propagate(ifelse.else_block, post)
        cond = expr_to_z3(ifelse.cond)
        res = z3.And(z3.Implies(cond, then_block), z3.Implies(z3.Not(cond), else_block))
        assert isinstance(res, z3.BoolRef)
        return res

    @propagate.register
    def _(self, block: Block, post: z3.BoolRef) -> z3.BoolRef:
        assertion = post
        for statement in reversed(block.statements):
            assertion = self.propagate(statement, assertion)
        return assertion

    @propagate.register
    def _(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        if self.correctness == Correctness.PARTIAL:
            return self._partial_while(while_, post)
        else:
            assert self.correctness == Correctness.TOTAL
            return self._total_while(while_, post)

    def _partial_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        invariant = expr_to_z3(while_.invariant)
        assert isinstance(invariant, z3.BoolRef)
        cond = expr_to_z3(while_.cond)
        s = z3.Solver()
        # (invariant && !cond) -> post
        s.add(z3.And(invariant, z3.Not(cond), z3.Not(post)))
        if s.check() != z3.unsat:
            raise RuntimeError(f'invariant and guard negation, does not imply postcondition')
        body_pre = self.propagate(while_.body, invariant)
        s.reset()
        # (invariant && cond) -> body_pre
        s.add(z3.And(invariant, cond, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            raise RuntimeError('invariant and guard does not imply precondition')
        return invariant

    def _total_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        invariant = expr_to_z3(while_.invariant)
        variant = expr_to_z3(while_.variant)
        assert isinstance(variant, z3.ArithRef)
        assert isinstance(invariant, z3.BoolRef)
        cond = expr_to_z3(while_.cond)
        pre = z3.And(invariant, 0 <= variant)
        assert isinstance(pre, z3.BoolRef)
        s = z3.Solver()
        # (invariant && !cond) -> post
        s.add(z3.And(invariant, z3.Not(cond), z3.Not(post)))
        if s.check() != z3.unsat:
            raise RuntimeError(f'invariant and guard negation, does not imply postcondition')
        upper = z3.FreshInt('e')
        body_post = z3.And(pre, variant < upper)
        body_pre = self.propagate(while_.body, body_post)
        s.reset()
        # (invariant && cond && 0 <= variant = upper) -> body_pre
        s.add(z3.And(pre, cond, variant == upper, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            raise RuntimeError('invariant and guard and variant does not imply precondition')
        return pre

def get_pre(proc: Proc, correctness: Correctness):
    ctx = __Context(correctness)
    post = expr_to_z3(proc.post)
    assertion = ctx.propagate(proc.body, post)
    if proc.pre != None:
        s = z3.Solver()
        pre = expr_to_z3(proc.pre)
        s.add(z3.Not(z3.Implies(pre, assertion)))
        if s.check() != z3.unsat:
            print('precondition cannot hold')
    s = z3.Solver()
    s.add(assertion)
    if s.check() == z3.unsat:
        print('precondition found cannot hold')
    return z3.simplify(assertion, arith_lhs=True)

def _prove(p: z3.BoolRef) -> bool:
    s = z3.Solver()
    s.set(auto_config=False, mbqi=False)
    s.add(z3.Not(p))
    res = s.check()
    assert res != z3.unknown
    return res == z3.unsat
