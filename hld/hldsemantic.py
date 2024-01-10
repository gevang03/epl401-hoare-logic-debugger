#!/usr/bin/env python3

import hldast
from functools import cache
from enum import IntEnum, auto

class ValueType(IntEnum):
    Int = auto()
    Bool = auto()

def check_proc(src: str, proc: hldast.Proc):
    ctx = __Context(src)
    return ctx.check_proc(proc)

class __Context:
    def __init__(self, src: str):
        self.variables: dict[str, ValueType] = {}
        self.src = src

    @cache
    def typeof(self, expr) -> ValueType:
        ty = type(expr)
        if ty == str:
            return self.variables[expr]
        if ty == int:
            return ValueType.Int
        if ty == bool:
            return ValueType.Bool
        if ty == hldast.Prefix:
            inner = self.typeof(expr.expr)
            if expr.op in ['+', '-']:
                if inner != ValueType.Int:
                    raise
                return ValueType.Int
            assert expr.op == '!'
            if inner != ValueType.Bool:
                raise
            return ValueType.Bool
        if ty == hldast.Infix:
            left = self.typeof(expr.left)
            right = self.typeof(expr.right)
            if expr.op in ['||', '&&']:
                if left != ValueType.Bool:
                    raise
                if right != ValueType.Bool:
                    raise
                return ValueType.Bool
            assert expr.op in ['+', '-', '*', '<', '<=', '>', '>=', '!=', '==']
            if left != ValueType.Int:
                raise
            if right != ValueType.Int:
                raise
            return ValueType.Int if expr.op in ['+', '-', '*'] else ValueType.Bool
        assert False, 'unreachable'

    def check_statement(self, statement):
        ty = type(statement)
        if ty == hldast.Assignment:
            etype = self.typeof(statement.expr)
            old = self.variables.get(statement.dest)
            if old == None:
                self.variables[statement.dest] = etype
                return
            if old != etype:
                raise
            return
        if ty == hldast.IfElse:
            if self.typeof(statement.cond) != ValueType.Bool:
                raise
            self.check_block(statement.truthy)
            self.check_block(statement.falsey)
            return
        if ty == hldast.While:
            if statement.invariant != None and self.typeof(statement.invariant) != ValueType.Bool:
                raise
            if statement.variant != None and self.typeof(statement.variant) != ValueType.Int:
                raise
            if self.typeof(statement.cond) != ValueType.Bool:
                raise
            self.check_block(statement.body)
            return
        assert False, 'unreachable'

    def check_block(self, block):
        for statement in block:
            self.check_statement(statement)

    def check_proc(self, proc: hldast.Proc):
        for param in proc.params:
            if param in self.variables:
                raise
            self.variables[param] = ValueType.Int
        if proc.pre != None and self.typeof(proc.pre) != ValueType.Bool:
            raise
        self.check_block(proc.body)
        if proc.post != None and self.typeof(proc.post) != ValueType.Bool:
            raise
