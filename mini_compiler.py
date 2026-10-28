"""
Mini Compiler for Arithmetic Expressions
=========================================
Pipeline:
  Source text -> Lexer -> Tokens -> Parser -> AST
              -> Optimizer (constant folding) -> Code Generator
              -> Stack-machine bytecode -> Virtual Machine -> Result

Supports:  + - * / % ^   unary minus   ( )   integers & decimals
Grammar (lowest to highest precedence):
    expr    -> term   (('+' | '-') term)*
    term    -> unary  (('*' | '/' | '%') unary)*
    unary   -> '-' unary | power
    power   -> atom ('^' unary)?          # right-associative
    atom    -> NUMBER | '(' expr ')'

Usage:
    python mini_compiler.py                  # interactive REPL
    python mini_compiler.py "2 + 3 * 4"      # one-shot
    python mini_compiler.py --debug "2+3*4"  # show every stage
"""

import sys
from dataclasses import dataclass


# ---------------------------------------------------------------- errors
class CompileError(Exception):
    def __init__(self, msg, pos=None):
        super().__init__(msg)
        self.msg, self.pos = msg, pos


# ------------------------------------------------------------ 1. LEXER
@dataclass
class Token:
    kind: str    # NUM, PLUS, MINUS, STAR, SLASH, PERCENT, CARET, LPAREN, RPAREN, EOF
    value: object
    pos: int


SYMBOLS = {
    "+": "PLUS", "-": "MINUS", "*": "STAR", "/": "SLASH",
    "%": "PERCENT", "^": "CARET", "(": "LPAREN", ")": "RPAREN",
}


def tokenize(src):
    tokens, i = [], 0
    while i < len(src):
        ch = src[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit() or ch == ".":
            start, dots = i, 0
            while i < len(src) and (src[i].isdigit() or src[i] == "."):
                dots += src[i] == "."
                i += 1
            text = src[start:i]
            if dots > 1 or text == ".":
                raise CompileError(f"Malformed number '{text}'", start)
            tokens.append(Token("NUM", float(text) if dots else int(text), start))
        elif ch in SYMBOLS:
            tokens.append(Token(SYMBOLS[ch], ch, i))
            i += 1
        else:
            raise CompileError(f"Unexpected character '{ch}'", i)
    tokens.append(Token("EOF", None, len(src)))
    return tokens


# ------------------------------------------------------- 2. AST + PARSER
@dataclass
class Num:
    value: object

@dataclass
class UnaryOp:
    op: str
    operand: object

@dataclass
class BinOp:
    op: str
    left: object
    right: object


class Parser:
    """Recursive-descent parser: one method per grammar rule."""

    def __init__(self, tokens):
        self.toks, self.i = tokens, 0

    @property
    def cur(self):
        return self.toks[self.i]

    def eat(self, *kinds):
        tok = self.cur
        if tok.kind not in kinds:
            raise CompileError(f"Expected {' or '.join(kinds)}, got {tok.kind}", tok.pos)
        self.i += 1
        return tok

    def parse(self):
        node = self.expr()
        if self.cur.kind != "EOF":
            raise CompileError(f"Unexpected token '{self.cur.value}'", self.cur.pos)
        return node

    def expr(self):
        node = self.term()
        while self.cur.kind in ("PLUS", "MINUS"):
            op = self.eat("PLUS", "MINUS").value
            node = BinOp(op, node, self.term())
        return node

    def term(self):
        node = self.unary()
        while self.cur.kind in ("STAR", "SLASH", "PERCENT"):
            op = self.eat("STAR", "SLASH", "PERCENT").value
            node = BinOp(op, node, self.unary())
        return node

    def unary(self):
        if self.cur.kind == "MINUS":
            self.eat("MINUS")
            return UnaryOp("-", self.unary())
        return self.power()

    def power(self):
        base = self.atom()
        if self.cur.kind == "CARET":
            self.eat("CARET")
            return BinOp("^", base, self.unary())   # right-associative
        return base

    def atom(self):
        if self.cur.kind == "NUM":
            return Num(self.eat("NUM").value)
        if self.cur.kind == "LPAREN":
            self.eat("LPAREN")
            node = self.expr()
            self.eat("RPAREN")
            return node
        raise CompileError(f"Unexpected '{self.cur.value or 'end of input'}'", self.cur.pos)


# ---------------------------------------------- 3. OPTIMIZER (const fold)
def apply_op(op, a, b):
    if op == "+": return a + b
    if op == "-": return a - b
    if op == "*": return a * b
    if op == "/":
        if b == 0:
            raise CompileError("Division by zero")
        return a / b
    if op == "%":
        if b == 0:
            raise CompileError("Modulo by zero")
        return a % b
    if op == "^": return a ** b
    raise CompileError(f"Unknown operator {op}")


def fold(node):
    """Evaluate constant sub-trees at compile time."""
    if isinstance(node, Num):
        return node
    if isinstance(node, UnaryOp):
        inner = fold(node.operand)
        return Num(-inner.value) if isinstance(inner, Num) else UnaryOp("-", inner)
    left, right = fold(node.left), fold(node.right)
    if isinstance(left, Num) and isinstance(right, Num):
        return Num(apply_op(node.op, left.value, right.value))
    return BinOp(node.op, left, right)


# ----------------------------------------------------- 4. CODE GENERATOR
def generate(node, code=None):
    """Post-order walk: children first, then the operator (=> stack code)."""
    code = [] if code is None else code
    if isinstance(node, Num):
        code.append(("PUSH", node.value))
    elif isinstance(node, UnaryOp):
        generate(node.operand, code)
        code.append(("NEG", None))
    else:
        generate(node.left, code)
        generate(node.right, code)
        code.append(({"+": "ADD", "-": "SUB", "*": "MUL",
                      "/": "DIV", "%": "MOD", "^": "POW"}[node.op], None))
    return code


# ------------------------------------------------------- 5. VIRTUAL MACHINE
def run(code):
    stack = []
    for op, arg in code:
        if op == "PUSH":
            stack.append(arg)
        elif op == "NEG":
            stack.append(-stack.pop())
        else:
            b, a = stack.pop(), stack.pop()      # note the order!
            sym = {"ADD": "+", "SUB": "-", "MUL": "*",
                   "DIV": "/", "MOD": "%", "POW": "^"}[op]
            stack.append(apply_op(sym, a, b))
    return stack.pop()


# --------------------------------------------------------------- helpers
def show_ast(node, indent=0):
    pad = "  " * indent
    if isinstance(node, Num):
        return f"{pad}Num({node.value})"
    if isinstance(node, UnaryOp):
        return f"{pad}Unary({node.op})\n{show_ast(node.operand, indent + 1)}"
    return (f"{pad}Bin({node.op})\n{show_ast(node.left, indent + 1)}\n"
            f"{show_ast(node.right, indent + 1)}")


def fmt(x):
    return int(x) if isinstance(x, float) and x.is_integer() else x


def compile_and_run(src, debug=False, optimize=True):
    tokens = tokenize(src)
    ast = Parser(tokens).parse()
    if debug:
        print("TOKENS:", [(t.kind, t.value) for t in tokens[:-1]])
        print("AST:\n" + show_ast(ast))
    if optimize:
        ast = fold(ast)
        if debug:
            print("AST after constant folding:\n" + show_ast(ast))
    code = generate(ast)
    if debug:
        print("BYTECODE:")
        for n, (op, arg) in enumerate(code):
            print(f"  {n:02d}  {op:<5} {'' if arg is None else arg}")
    return run(code)


def report(err, src):
    print(f"Error: {err.msg}")
    if err.pos is not None:
        print("  " + src)
        print("  " + " " * err.pos + "^")


def main():
    args = sys.argv[1:]
    debug = "--debug" in args
    args = [a for a in args if a != "--debug"]
    if args:
        src = " ".join(args)
        try:
            print(fmt(compile_and_run(src, debug)))
        except CompileError as e:
            report(e, src)
        return
    print("Mini Compiler  (type 'quit' to exit, prefix with ':d ' for debug view)")
    while True:
        try:
            src = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if src in ("quit", "exit"):
            break
        if not src:
            continue
        dbg = src.startswith(":d ")
        src = src[3:] if dbg else src
        try:
            print(fmt(compile_and_run(src, dbg)))
        except CompileError as e:
            report(e, src)


# ------------------------------------------------------------------ tests
def _self_test():
    cases = {
        "2 + 3 * 4": 14, "(2 + 3) * 4": 20, "10 - 4 - 3": 3,
        "2 ^ 3 ^ 2": 512, "-3 + 5": 2, "--4": 4, "-2 ^ 2": -4,
        "100 / 8": 12.5, "17 % 5": 2, "1.5 * 4": 6.0,
        "((1+2)*(3+4))/7": 3.0,
    }
    for src, want in cases.items():
        got = compile_and_run(src)
        assert got == want, f"{src}: got {got}, want {want}"
    for bad in ["2 +", "(1 + 2", "3 $ 4", "1 / 0", "1..2 + 3", ")"]:
        try:
            compile_and_run(bad)
            raise AssertionError(f"should fail: {bad}")
        except CompileError:
            pass
    print("All tests passed.")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        _self_test()
    else:
        main()
