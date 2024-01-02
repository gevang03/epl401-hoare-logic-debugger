#!/usr/bin/env python3

from collections import namedtuple

Prefix = namedtuple('Prefix', ['loc', 'op', 'expr'])
Infix = namedtuple('Infix', ['loc', 'op', 'left', 'right'])

Assignment = namedtuple('Assignment', ['loc', 'dest', 'expr'])
IfElse = namedtuple('IfElse', ['loc', 'cond', 'truthy', 'falsey'])
While = namedtuple('While', ['loc', 'invariant', 'variant', 'cond', 'body'])
Proc = namedtuple('Proc', ['loc', 'pre', 'post', 'name', 'params', 'body'])
