"""A small MoLang evaluator, close enough to Cobblemon's (bedrockk) runtime to replay particle expressions.

Used by preview_move.py. Covers what the move generators emit: numbers, v./variable./q./query./t./temp.
names, math.* calls (trig in degrees), unary - and !, * / + -, comparisons, && || ??, the ternary (and the
binary `a ? b` form), assignments and `;`-separated statements. Booleans are 1.0 / 0.0, unknown queries and
unset variables read 0 (as in Cobblemon), and math errors give NaN instead of raising (as Java does).
"""
import math, random, re

_TOKEN = re.compile(r'\s*(?:(\d+\.\d*|\.\d+|\d+)|([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)'
                    r'|(&&|\|\||==|!=|<=|>=|\?\?|[-+*/()?:,;!<>=]))')
_ALIAS = {'variable': 'v', 'query': 'q', 'temp': 't', 'context': 'c'}


def _tokens(src):
    pos, out = 0, []
    src = src.strip()
    while pos < len(src):
        m = _TOKEN.match(src, pos)
        if not m or m.end() == pos:
            raise SyntaxError(f'bad character at {pos}: {src[pos:pos + 20]!r}')
        num, name, op = m.groups()
        if num is not None:
            out.append(('num', float(num)))
        elif name is not None:
            head, _, rest = name.partition('.')
            head = _ALIAS.get(head.lower(), head.lower())
            out.append(('name', head + ('.' + rest.lower() if rest else '')))
        else:
            out.append(('op', op))
        pos = m.end()
        while pos < len(src) and src[pos].isspace():
            pos += 1
    out.append(('eof', None))
    return out


class _Parser:
    def __init__(self, src):
        self.t = _tokens(src)
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def take(self, op=None):
        tok = self.t[self.i]
        if op is not None and tok != ('op', op):
            raise SyntaxError(f'expected {op!r}, got {tok}')
        self.i += 1
        return tok

    def statements(self):
        out = []
        while self.peek()[0] != 'eof':
            if self.peek() == ('op', ';'):
                self.take()
                continue
            out.append(self.assign())
            if self.peek() == ('op', ';'):
                self.take()
        return out

    def assign(self):
        left = self.ternary()
        if self.peek() == ('op', '='):
            self.take()
            if left[0] != 'name':
                raise SyntaxError('assignment to a non-name')
            return ('set', left[1], self.assign())
        return left

    def ternary(self):
        cond = self.binary(0)
        if self.peek() == ('op', '?'):
            self.take()
            a = self.ternary()
            if self.peek() == ('op', ':'):
                self.take()
                b = self.ternary()
            else:
                b = ('num', 0.0)
            return ('if', cond, a, b)
        return cond

    LEVELS = [['??'], ['||'], ['&&'], ['==', '!='], ['<', '<=', '>', '>='], ['+', '-'], ['*', '/']]

    def binary(self, level):
        if level == len(self.LEVELS):
            return self.unary()
        left = self.binary(level + 1)
        while self.peek()[0] == 'op' and self.peek()[1] in self.LEVELS[level]:
            op = self.take()[1]
            left = ('bin', op, left, self.binary(level + 1))
        return left

    def unary(self):
        if self.peek() == ('op', '-'):
            self.take()
            return ('neg', self.unary())
        if self.peek() == ('op', '!'):
            self.take()
            return ('not', self.unary())
        if self.peek() == ('op', '+'):
            self.take()
            return self.unary()
        return self.primary()

    def primary(self):
        kind, val = self.take()
        if kind == 'num':
            return ('num', val)
        if kind == 'op' and val == '(':
            e = self.assign()
            self.take(')')
            return e
        if kind == 'name':
            if self.peek() == ('op', '('):
                self.take()
                args = []
                if self.peek() != ('op', ')'):
                    args.append(self.assign())
                    while self.peek() == ('op', ','):
                        self.take()
                        args.append(self.assign())
                self.take(')')
                return ('call', val, args)
            return ('name', val)
        raise SyntaxError(f'unexpected {kind} {val!r}')


def _nan_guard(fn):
    def wrapped(*a):
        try:
            return float(fn(*a))
        except (ValueError, ZeroDivisionError, OverflowError):
            return float('nan')
    return wrapped


def _java_round(x):
    return math.floor(x + 0.5)


MATH = {
    'math.sin': lambda a: math.sin(math.radians(a)), 'math.cos': lambda a: math.cos(math.radians(a)),
    'math.asin': lambda a: math.degrees(math.asin(a)), 'math.acos': lambda a: math.degrees(math.acos(a)),
    'math.atan': lambda a: math.degrees(math.atan(a)), 'math.abs': abs, 'math.floor': math.floor,
    'math.ceil': math.ceil, 'math.round': _java_round, 'math.trunc': math.trunc, 'math.sqrt': math.sqrt,
    'math.pow': math.pow, 'math.exp': math.exp, 'math.ln': math.log, 'math.min': min, 'math.max': max,
    'math.clamp': lambda v, a, b: max(a, min(b, v)), 'math.lerp': lambda a, b, k: a + (b - a) * k,
    'math.mod': math.fmod, 'math.random': lambda a, b: random.uniform(a, b),
    'math.random_integer': lambda a, b: random.randint(int(a), int(b)), 'math.pi': lambda: math.pi,
    'math.hermite_blend': lambda k: 3 * k * k - 2 * k ** 3, 'math.copy_sign': math.copysign,
    'math.sign': lambda a: math.copysign(1.0, a),
}
MATH = {k: _nan_guard(v) for k, v in MATH.items()}


class Env:
    def __init__(self, variables=None, queries=None):
        self.vars = dict(variables or {})     # 'v.name' / 't.name' -> float
        self.queries = dict(queries or {})    # 'q.name' -> float or callable

    def get(self, name):
        if name.startswith('q.'):
            q = self.queries.get(name, 0.0)
            return float(q() if callable(q) else q)
        if name in ('true',):
            return 1.0
        if name in ('false',):
            return 0.0
        if name == 'math.pi':
            return math.pi
        return float(self.vars.get(name, 0.0))


def _eval(node, env):
    kind = node[0]
    if kind == 'num':
        return node[1]
    if kind == 'name':
        return env.get(node[1])
    if kind == 'set':
        val = _eval(node[2], env)
        env.vars[node[1]] = val
        return val
    if kind == 'neg':
        return -_eval(node[1], env)
    if kind == 'not':
        return 1.0 if _eval(node[1], env) == 0 else 0.0
    if kind == 'if':
        return _eval(node[2], env) if _eval(node[1], env) != 0 else _eval(node[3], env)
    if kind == 'call':
        name, args = node[1], [_eval(a, env) for a in node[2]]
        if name in MATH:
            return MATH[name](*args)
        q = env.queries.get(name)
        if callable(q):
            return float(q(*args))
        return 0.0
    op, a, b = node[1], node[2], node[3]
    if op == '&&':
        return 1.0 if _eval(a, env) != 0 and _eval(b, env) != 0 else 0.0
    if op == '||':
        return 1.0 if _eval(a, env) != 0 or _eval(b, env) != 0 else 0.0
    if op == '??':
        x = _eval(a, env)
        return x if x == x else _eval(b, env)
    x, y = _eval(a, env), _eval(b, env)
    if op == '+':
        return x + y
    if op == '-':
        return x - y
    if op == '*':
        return x * y
    if op == '/':
        return x / y if y != 0 else float('nan')
    return 1.0 if {'<': x < y, '<=': x <= y, '>': x > y, '>=': x >= y, '==': x == y, '!=': x != y}[op] else 0.0


_CACHE = {}


def compile_expr(src):
    """MoLang string (or number) -> list of parsed statements (cached)."""
    if isinstance(src, (int, float)):
        return [('num', float(src))]
    if src not in _CACHE:
        _CACHE[src] = _Parser(src).statements()
    return _CACHE[src]


def run(src, env):
    """Evaluate a MoLang string/number in env; returns the value of the last statement."""
    val = 0.0
    for st in compile_expr(src):
        val = _eval(st, env)
    return val


def linear_curve(spec, env):
    """Bedrock 'linear' curve: nodes spread evenly over input / horizontal_range, clamped to 0..1."""
    nodes = [run(n, env) for n in spec['nodes']]
    rng = run(spec.get('horizontal_range', 1), env) or 1.0
    x = max(0.0, min(1.0, run(spec['input'], env) / rng)) * (len(nodes) - 1)
    i = min(int(x), len(nodes) - 2)
    return nodes[i] + (nodes[i + 1] - nodes[i]) * (x - i)
