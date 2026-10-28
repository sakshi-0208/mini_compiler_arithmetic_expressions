import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mini_compiler import (  # noqa: E402
    CompileError,
    Parser,
    compile_and_run,
    fold,
    generate,
    tokenize,
)


class TestLexer(unittest.TestCase):
    def test_token_kinds(self):
        kinds = [t.kind for t in tokenize("12 + 3.5")]
        self.assertEqual(kinds, ["NUM", "PLUS", "NUM", "EOF"])

    def test_integer_and_float_values(self):
        toks = tokenize("7 2.5")
        self.assertEqual(toks[0].value, 7)
        self.assertEqual(toks[1].value, 2.5)

    def test_whitespace_ignored(self):
        self.assertEqual(
            [t.kind for t in tokenize("2+3")],
            [t.kind for t in tokenize("  2   +   3 ")],
        )

    def test_bad_character(self):
        with self.assertRaises(CompileError) as ctx:
            tokenize("3 $ 4")
        self.assertEqual(ctx.exception.pos, 2)

    def test_malformed_number(self):
        with self.assertRaises(CompileError):
            tokenize("1..2")


class TestParser(unittest.TestCase):
    def parse(self, src):
        return Parser(tokenize(src)).parse()

    def test_precedence_shape(self):
        tree = self.parse("2 + 3 * 4")
        self.assertEqual(tree.op, "+")
        self.assertEqual(tree.right.op, "*")

    def test_left_associativity(self):
        tree = self.parse("10 - 4 - 3")
        self.assertEqual(tree.op, "-")
        self.assertEqual(tree.left.op, "-")

    def test_right_associativity_of_power(self):
        tree = self.parse("2 ^ 3 ^ 2")
        self.assertEqual(tree.right.op, "^")

    def test_missing_closing_bracket(self):
        with self.assertRaises(CompileError):
            self.parse("(1 + 2")

    def test_trailing_operator(self):
        with self.assertRaises(CompileError):
            self.parse("2 +")

    def test_leftover_token(self):
        with self.assertRaises(CompileError):
            self.parse("2 3")


class TestOptimizer(unittest.TestCase):
    def test_folds_to_single_number(self):
        tree = fold(Parser(tokenize("2 + 3 * (4 - 1)")).parse())
        self.assertEqual(tree.value, 11)

    def test_folded_code_is_one_push(self):
        tree = fold(Parser(tokenize("2 * 3 + 4")).parse())
        self.assertEqual(generate(tree), [("PUSH", 10)])


class TestCodeGenerator(unittest.TestCase):
    def test_postfix_order(self):
        tree = Parser(tokenize("2 + 3 * 4")).parse()
        ops = [op for op, _ in generate(tree)]
        self.assertEqual(ops, ["PUSH", "PUSH", "PUSH", "MUL", "ADD"])


class TestEndToEnd(unittest.TestCase):
    CASES = {
        "2 + 3 * 4": 14,
        "(2 + 3) * 4": 20,
        "10 - 4 - 3": 3,
        "2 ^ 3 ^ 2": 512,
        "-3 + 5": 2,
        "--4": 4,
        "-2 ^ 2": -4,
        "100 / 8": 12.5,
        "17 % 5": 2,
        "1.5 * 4": 6.0,
        "((1+2)*(3+4))/7": 3.0,
    }

    def test_known_answers_with_folding(self):
        for src, want in self.CASES.items():
            with self.subTest(src=src):
                self.assertEqual(compile_and_run(src), want)

    def test_known_answers_without_folding(self):
        for src, want in self.CASES.items():
            with self.subTest(src=src):
                self.assertEqual(compile_and_run(src, optimize=False), want)

    def test_division_by_zero_with_folding(self):
        with self.assertRaises(CompileError):
            compile_and_run("1 / 0")

    def test_division_by_zero_in_vm(self):
        with self.assertRaises(CompileError):
            compile_and_run("1 / 0", optimize=False)

    def test_modulo_by_zero(self):
        with self.assertRaises(CompileError):
            compile_and_run("5 % 0")


if __name__ == "__main__":
    unittest.main()
