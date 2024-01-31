#!/usr/bin/env python3

import operator
import z3
from enum import Enum
from functools import cache, singledispatchmethod
from hldast import *
from hldsemantic import ValueType

_infix_arith_ops = { '*': operator.mul, '+': operator.add, '-': operator.sub }
_infix_logical_ops = { '&&': z3.And,'||': z3.Or }
_infix_rel_ops = {
    '<=': operator.le, '<': operator.lt,
    '>=': operator.ge, '>': operator.gt,
    '==': operator.eq, '!=': operator.ne
}

def simplify(expr: z3.BoolRef | z3.ArithRef) -> z3.BoolRef | z3.ArithRef:
    ret = z3.Tactic('ctx-solver-simplify').apply(expr).as_expr()
    # ret = z3.simplify(expr, arith_lhs=True)
    assert isinstance(ret, (z3.BoolRef, z3.ArithRef))
    return ret

class Correctness(Enum):
    PARTIAL = 'partial'
    TOTAL = 'total'

class __Context:
    def __init__(self, correctness: Correctness, variables: dict[str, ValueType]):
        self.correctness = correctness
        self.variables = variables

    @singledispatchmethod
    @cache
    def expr_to_z3(self, _: Expr) -> z3.BoolRef | z3.ArithRef:
        raise NotImplementedError

    @expr_to_z3.register
    def _(self, expr: BoolLiteral) -> z3.BoolRef:
        return z3.BoolVal(expr.value)

    @expr_to_z3.register
    def _(self, expr: IntLiteral) -> z3.IntNumRef:
        return z3.IntVal(expr.value)

    @expr_to_z3.register
    def _(self, expr: Identifier) -> z3.BoolRef | z3.ArithRef:
        if self.variables[expr.value] == ValueType.Int:
            return z3.Int(expr.value)
        else:
            return z3.Bool(expr.value)

    @expr_to_z3.register
    def _(self, pref: PrefixArithmeticExpr) -> z3.ArithRef:
        expr = self.expr_to_z3(pref.expr)
        assert isinstance(expr, z3.ArithRef)
        if pref.op == '+':
            return +expr
        else:
            assert pref.op == '-'
            return -expr

    @expr_to_z3.register
    def _(self, pref: PrefixLogicalExpr) -> z3.BoolRef:
        expr = self.expr_to_z3(pref.expr)
        assert isinstance(expr, z3.BoolRef)
        assert pref.op == '!'
        res = z3.Not(expr)
        assert isinstance(res, z3.BoolRef)
        return res

    @expr_to_z3.register
    def _(self, expr: InfixArithmeticExpr) -> z3.ArithRef:
        left = self.expr_to_z3(expr.left)
        assert isinstance(left, z3.ArithRef)
        right = self.expr_to_z3(expr.right)
        assert isinstance(right, z3.ArithRef)
        res = _infix_arith_ops[expr.op](left, right)
        assert isinstance(res, z3.ArithRef)
        return res

    @expr_to_z3.register
    def _(self, expr: InfixLogicalExpr) -> z3.BoolRef:
        left = self.expr_to_z3(expr.left)
        assert isinstance(left, z3.BoolRef)
        right = self.expr_to_z3(expr.right)
        assert isinstance(right, z3.BoolRef)
        res = _infix_logical_ops[expr.op](left, right)
        assert isinstance(res, z3.BoolRef)
        return res

    @expr_to_z3.register
    def _(self, expr: InfixRelationalExpr) -> z3.BoolRef:
        left = self.expr_to_z3(expr.left)
        assert isinstance(left, z3.ArithRef)
        right = self.expr_to_z3(expr.right)
        assert isinstance(right, z3.ArithRef)
        res = _infix_rel_ops[expr.op](left, right)
        assert isinstance(res, z3.BoolRef)
        return res

    @singledispatchmethod
    def propagate(self, _: Statement, _post: z3.BoolRef) -> z3.BoolRef:
        raise NotImplementedError

    @propagate.register
    def _(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        dest = self.expr_to_z3(assignment.dest)
        value = self.expr_to_z3(assignment.value)
        res = z3.substitute(post, (dest, value))
        assert isinstance(res, z3.BoolRef)
        return res

    @propagate.register
    def _(self, ifelse: IfElse, post: z3.BoolRef) -> z3.BoolRef:
        then_block = self.propagate(ifelse.then_block, post)
        else_block = self.propagate(ifelse.else_block, post)
        cond = self.expr_to_z3(ifelse.cond)
        res = z3.And(z3.Implies(cond, then_block), z3.Implies(z3.Not(cond), else_block))
        assert isinstance(res, z3.BoolRef)
        return res

    @propagate.register
    def _(self, block: Block, post: z3.BoolRef) -> z3.BoolRef:
        assertion = post
        for statement in reversed(block.statements):
            assertion = self.propagate(statement, assertion)
            s = z3.Solver()
            s.add(assertion)
            if s.check() == z3.unsat:
                statement.error(f'precondition {assertion} found at statement is unsatisfiable')
        return assertion

    @propagate.register
    def _(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        if self.correctness == Correctness.PARTIAL:
            return self._partial_while(while_, post)
        else:
            assert self.correctness == Correctness.TOTAL
            return self._total_while(while_, post)

    @propagate.register
    def _(self, assert_: Assert, post: z3.BoolRef) -> z3.BoolRef:
        s = z3.Solver()
        assertion = self.expr_to_z3(assert_.expr)
        s.add(z3.And(post, z3.Not(assertion)))
        if s.check() != z3.unsat:
            assert_.error(f'assertion does not hold, condition found at assertion: {simplify(post)}\ncounter-example: {s.model()}')
        return post

    def _partial_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        invariant = self.expr_to_z3(while_.invariant)
        assert isinstance(invariant, z3.BoolRef)
        cond = self.expr_to_z3(while_.cond)
        s = z3.Solver()
        # (invariant && !cond) -> post
        s.add(z3.And(invariant, z3.Not(cond), z3.Not(post)))
        if s.check() != z3.unsat:
            supplementary = f'\tpost: {simplify(post)}'
            while_.body.error(f'invariant and guard negation do not imply post condition.\n{supplementary}\ncounter-example: {s.model()}')
        body_pre = self.propagate(while_.body, invariant)
        s.reset()
        # (invariant && cond) -> body_pre
        s.add(z3.And(invariant, cond, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            supplementary = f'\tbody pre: {simplify(body_pre)}'
            while_.body.error(f'invariant and guard do not imply while loop body precondition.\n{supplementary}\ncounter-example: {s.model()}')
        return invariant

    def _total_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        invariant = self.expr_to_z3(while_.invariant)
        variant = self.expr_to_z3(while_.variant)
        assert isinstance(variant, z3.ArithRef)
        assert isinstance(invariant, z3.BoolRef)
        cond = self.expr_to_z3(while_.cond)
        pre = z3.And(invariant, 0 <= variant)
        assert isinstance(pre, z3.BoolRef)
        s = z3.Solver()
        # (invariant && !cond) -> post
        s.add(z3.And(invariant, z3.Not(cond), z3.Not(post)))
        if s.check() != z3.unsat:
            supplementary = f'\tpost: {simplify(post)}'
            while_.body.error(f'invariant and guard negation do not imply postcondition.\n{supplementary}')
        upper = z3.FreshInt('e')
        body_post = z3.And(pre, variant < upper)
        body_pre = self.propagate(while_.body, body_post)
        s.reset()
        # (invariant && cond && 0 <= variant = upper) -> body_pre
        s.add(z3.And(pre, cond, variant == upper, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            supplementary = f'\tbody pre: {simplify(body_pre)}'
            while_.body.error(f'invariant and guard and variant do not imply while body precondition.\n{supplementary}')
        return pre

def get_pre(proc: Proc, correctness: Correctness, variables: dict[str, ValueType]):
    ctx = __Context(correctness, variables)
    post = ctx.expr_to_z3(proc.post)
    assertion = ctx.propagate(proc.body, post)
    s = z3.Solver()
    s.add(assertion)
    if s.check() == z3.unsat:
        proc.error(f'precondition {simplify(assertion)} found is unsatisfiable')
    if proc.pre != None:
        s = z3.Solver()
        pre = ctx.expr_to_z3(proc.pre)
        s.add(z3.Not(z3.Implies(pre, assertion)))
        if s.check() != z3.unsat:
            proc.pre.error(f'precondition {pre} does not imply assertion found {simplify(assertion)}')
    return simplify(assertion)

# NOTE: unused
def _prove(p: z3.BoolRef) -> bool:
    s = z3.Solver()
    s.set(auto_config=False, mbqi=False)
    s.add(z3.Not(p))
    res = s.check()
    assert res != z3.unknown
    return res == z3.unsat
