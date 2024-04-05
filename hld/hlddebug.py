#!/usr/bin/env python3

import operator
import z3
from enum import Enum
from functools import cache, singledispatchmethod
from typing import Union

from hldast import *
from hldsemantic import ValueType

_infix_arith_ops = {
    '*': operator.mul, '+': operator.add, '-': operator.sub,
    '/': operator.truediv, '%': operator.mod
}

_infix_logical_ops = { '&&': z3.And, '||': z3.Or }
_infix_rel_ops = {
    '<=': operator.le, '<': operator.lt,
    '>=': operator.ge, '>': operator.gt,
    '==': operator.eq, '!=': operator.ne
}

_ValRef = Union[z3.BoolRef, z3.ArithRef]

def simplify(expr: _ValRef) -> _ValRef:
    ret = z3.Tactic('ctx-solver-simplify').apply(expr).as_expr()
    ret = z3.simplify(ret)
    assert isinstance(ret, (z3.BoolRef, z3.ArithRef))
    return ret

class Correctness(Enum):
    PARTIAL = 'partial'
    TOTAL = 'total'

class __Context:
    result = z3.Int('result')

    def __init__(self, correctness: Correctness, symtab: dict[str, dict[str, ValueType]], call_graph: dict[str, set[str]]):
        self.correctness = correctness
        self.call_graph = call_graph
        self.symtab = symtab
        self.current: Declaration
        self.variables: dict[str, ValueType] = {}
        self.fns: dict[str, z3.FuncDeclRef] = {}
        self.procs: dict[str, Proc] = {}

    def declare_fn_or_pred(self, fn_or_pred: Union[Fn, Pred]):
        name = fn_or_pred.name.value
        sig = (z3.IntSort() for _ in fn_or_pred.params)
        rettype = z3.IntSort() if isinstance(fn_or_pred, Fn) else z3.BoolSort()
        self.fns[name] = z3.RecFunction(name, *sig, rettype)

    def define_fn_or_pred(self, fn_or_pred: Union[Fn, Pred]):
        self.current = fn_or_pred
        name = fn_or_pred.name.value
        f = self.fns[name]
        self.variables = self.symtab[name]
        params = [z3.Int(param.value) for param in fn_or_pred.params]
        expr = self.expr_to_z3(fn_or_pred.expr)
        z3.RecAddDefinition(f, params, expr)

    def _get_model(self, solver: z3.Solver) -> str:
        model = solver.model()
        assigns = (f'{sym} = {model[sym]}'
                   for sym in model if sym.name() in self.variables) # type: ignore
        return f'[{", ".join(assigns)}]'

    @singledispatchmethod
    @cache
    def expr_to_z3(self, _: Expr) -> _ValRef:
        raise NotImplementedError

    @expr_to_z3.register
    def _(self, expr: BoolLiteral) -> z3.BoolRef:
        return z3.BoolVal(expr.value)

    @expr_to_z3.register
    def _(self, expr: IntLiteral) -> z3.IntNumRef:
        return z3.IntVal(expr.value)

    @expr_to_z3.register
    def _(self, expr: Identifier) -> _ValRef:
        value = expr.value
        type = self.variables[value]
        if type == ValueType.Int:
            return z3.Int(value)
        else:
            assert type == ValueType.Bool
            return z3.Bool(value)

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

    @expr_to_z3.register
    def _(self, expr: TernaryExpr) -> _ValRef:
        cond = self.expr_to_z3(expr.cond)
        then_expr = self.expr_to_z3(expr.then_expr)
        else_expr = self.expr_to_z3(expr.else_expr)
        res = z3.If(cond, then_expr, else_expr)
        assert isinstance(res, (z3.BoolRef, z3.ArithRef))
        return res

    @expr_to_z3.register
    def _(self, call: CallExpr) -> _ValRef:
        name = call.callee.value
        args = (self.expr_to_z3(arg) for arg in call.args)
        f = self.fns[name]
        res = f(*args)
        assert isinstance(res, (z3.BoolRef, z3.ArithRef))
        return res

    @expr_to_z3.register
    def _(self, _: ResultExpr) -> z3.ArithRef:
        return self.result

    @expr_to_z3.register
    def _(self, quantified: QuantifiedExpr) -> z3.BoolRef:
        cur = self.variables.copy()
        vars = [z3.Int(var.value) for var in quantified.bindings]
        for var in quantified.bindings:
            self.variables[var.value] = ValueType.Int
        quantifier = z3.ForAll if quantified.quantifier == 'forall' else z3.Exists
        e = quantifier(vars, self.expr_to_z3(quantified.expr))
        self.variables = cur
        return e

    @singledispatchmethod
    def propagate(self, _: Statement, _post: z3.BoolRef) -> z3.BoolRef:
        raise NotImplementedError

    @propagate.register
    def _(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        if isinstance(assignment.value, CallExpr):
            return self._assignment_call(assignment, post)
        elif isinstance(assignment.value, InfixArithmeticExpr) and assignment.value.op in { '/', '%'}:
            return self._assignment_divmod(assignment, post)
        else:
            return self._assignment_value(assignment, post)

    def _assignment_value(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        dest = self.expr_to_z3(assignment.dest)
        value = self.expr_to_z3(assignment.value)
        res = z3.substitute(post, (dest, value))
        assert isinstance(res, z3.BoolRef)
        return res

    def _assignment_divmod(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        assert isinstance(assignment.value, InfixArithmeticExpr) and assignment.value.op in { '/', '%' }
        dest = self.expr_to_z3(assignment.dest)
        value = self.expr_to_z3(assignment.value)
        res = z3.substitute(post, (dest, value))
        divisor = self.expr_to_z3(assignment.value.right)
        res = z3.And(res, divisor != 0)
        assert isinstance(res, z3.BoolRef)
        return res

    @cache
    def call_is_recursive(self, callee: str, caller: str) -> bool:
        call_graph = self.call_graph
        visited = set()
        search_set = {callee}
        while len(search_set) > 0:
            cur = search_set.pop()
            if cur == caller:
                return True
            visited.add(cur)
            search_set.update(c for c in call_graph[cur] if c not in visited)
        return False

    def _assignment_call(self, assignment: Assignment, post: z3.BoolRef) -> z3.BoolRef:
        call = assignment.value
        assert isinstance(call, CallExpr)
        dest = self.expr_to_z3(assignment.dest)
        callee = call.callee.value
        proc = self.procs[callee]
        args = map(self.expr_to_z3, call.args)
        params = map(self.expr_to_z3, proc.params)
        subs = [*zip(params, args)]
        assert isinstance(self.current, Proc)
        caller = self.current.name.value
        if self.correctness == Correctness.TOTAL and self.call_is_recursive(callee, caller):
            if self.current.variant == None:
                self.current.error('missing variant expression')
            if proc.variant == None:
                proc.error('missing variant expression')
            cur_variant = self.expr_to_z3(self.current.variant)
            callee_variant = self.expr_to_z3(proc.variant)
            callee_variant = z3.substitute(callee_variant, subs)
            assert isinstance(callee_variant, z3.ArithRef)
            variant_cond = cur_variant > callee_variant
        else:
            variant_cond = True
        if proc.pre == None:
            proc_pre = True
        else:
            proc_pre = self.expr_to_z3(proc.pre)
            proc_pre = z3.substitute(proc_pre, *subs)
        if proc.post == None:
            proc.error('missing postcondition')
        proc_post = self.expr_to_z3(proc.post)
        proc_post = z3.substitute(proc_post, *subs, (self.result, dest))
        res = z3.And(proc_pre, variant_cond, z3.ForAll(dest, z3.Implies(proc_post, post)))
        assert isinstance(res, z3.BoolRef)
        return res

    @propagate.register
    def _(self, ifelse: IfElse, post: z3.BoolRef) -> z3.BoolRef:
        then_block = self.propagate(ifelse.then_block, post)
        else_block = self.propagate(ifelse.else_block, post)
        cond = self.expr_to_z3(ifelse.cond)
        res = z3.If(cond, then_block, else_block)
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
                statement.error(f'precondition `{assertion}` found is unsatisfiable')
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
            assert_.error(f'assertion does not hold, condition found at assertion: {simplify(post)}\ncounter-example: {self._get_model(s)}')
        return post

    @propagate.register
    def _(self, return_: Return, _: z3.BoolRef) -> z3.BoolRef:
        proc = self.current
        assert isinstance(proc, Proc)
        post = self.expr_to_z3(proc.post)
        assert isinstance(post, z3.BoolRef)
        expr = self.expr_to_z3(return_.expr)
        res = z3.substitute(post, (self.result, expr))
        assert isinstance(res, z3.BoolRef)
        return res

    def _partial_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        if while_.invariant == None:
            while_.error('missing invariant condition')
        invariant = self.expr_to_z3(while_.invariant)
        assert isinstance(self.current, Proc)
        if self.current.pre != None:
            invariant = z3.And(invariant, self.expr_to_z3(self.current.pre))
        assert isinstance(invariant, z3.BoolRef)
        cond = self.expr_to_z3(while_.cond)
        s = z3.Solver()
        # (invariant && !cond) -> post
        s.add(z3.And(invariant, z3.Not(cond), z3.Not(post)))
        if s.check() != z3.unsat:
            supplementary = f'\tpost: {simplify(post)}'
            while_.body.error(f'invariant and guard negation do not imply post condition.\n{supplementary}\ncounter-example: {self._get_model(s)}')
        body_pre = self.propagate(while_.body, invariant)
        s.reset()
        # (invariant && cond) -> body_pre
        s.add(z3.And(invariant, cond, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            supplementary = f'\tbody pre: {simplify(body_pre)}'
            while_.body.error(f'invariant and guard do not imply while loop body precondition.\n{supplementary}\ncounter-example: {self._get_model(s)}')
        return invariant

    def _total_while(self, while_: While, post: z3.BoolRef) -> z3.BoolRef:
        if while_.invariant == None:
            while_.error('missing invariant condition')
        if while_.variant == None:
            while_.error('missing variant expression')
        invariant = self.expr_to_z3(while_.invariant)
        assert isinstance(self.current, Proc)
        if self.current.pre != None:
            invariant = z3.And(invariant, self.expr_to_z3(self.current.pre))
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
            while_.body.error(f'invariant and guard negation do not imply postcondition.\n{supplementary}\ncounter-example: {self._get_model(s)}')
        upper = z3.FreshInt('e')
        body_post = z3.And(pre, variant < upper)
        body_pre = self.propagate(while_.body, body_post)
        s.reset()
        # (invariant && cond && 0 <= variant = upper) -> body_pre
        s.add(z3.And(pre, cond, variant == upper, z3.Not(body_pre)))
        if s.check() != z3.unsat:
            supplementary = f'\tbody pre: {simplify(body_pre)}'
            while_.body.error(f'invariant and guard and variant do not imply while body precondition.\n{supplementary}\ncounter-example: {self._get_model(s)}')
        return pre

    def declare_proc(self, decl):
        self.procs[decl.name.value] = decl

    def is_recursive(self, proc: Proc) -> bool:
        caller = proc.name.value
        callees = self.call_graph[caller]
        return any(self.call_is_recursive(callee, caller) for callee in callees)

    def verify(self, proc: Proc) -> z3.BoolRef:
        name = proc.name.value
        self.procs[name] = proc
        self.current = proc
        self.variables = self.symtab[name]
        if proc.post == None:
            proc.error('missing postcondition')
        post = self.expr_to_z3(proc.post)
        assertion = self.propagate(proc.body, post)
        if self.correctness == Correctness.TOTAL and self.is_recursive(proc):
            if proc.variant == None:
                proc.error('missing variant expression')
            variant = self.expr_to_z3(proc.variant)
            assert isinstance(variant, z3.ArithRef)
            assertion = z3.And(assertion, 0 <= variant)
            assert isinstance(assertion, z3.BoolRef)
        if proc.pre != None:
            s = z3.Solver()
            pre = self.expr_to_z3(proc.pre)
            s.add(z3.Not(z3.Implies(pre, assertion)))
            if s.check() != z3.unsat:
                proc.pre.error(f'precondition {pre} does not imply assertion found {simplify(assertion)}')
        assertion = simplify(assertion)
        assert isinstance(assertion, z3.BoolRef)
        return assertion

def get_pre(decls: list[Declaration], correctness: Correctness, symtab: dict[str, dict[str, ValueType]], callees: dict[str, set[str]]) -> dict[str, z3.BoolRef]:
    ctx = __Context(correctness, symtab, callees)
    pres = {}
    for decl in decls:
        if isinstance(decl, Proc):
            ctx.declare_proc(decl)
        else:
            assert isinstance(decl, (Pred, Fn))
            ctx.declare_fn_or_pred(decl)
    for decl in decls:
        if isinstance(decl, (Pred, Fn)):
            ctx.define_fn_or_pred(decl)
    for decl in decls:
        if isinstance(decl, Proc):
            pres[decl.name.value] = ctx.verify(decl)
    return pres

# NOTE: unused
def _prove(p: z3.BoolRef) -> bool:
    s = z3.Solver()
    s.set(auto_config=False, mbqi=False)
    s.add(z3.Not(p))
    res = s.check()
    assert res != z3.unknown
    return res == z3.unsat
