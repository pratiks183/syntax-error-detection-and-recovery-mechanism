from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class TokenType(Enum):
    """Token categories used by the lexer and parser."""
    KEYWORD = auto()
    IDENTIFIER = auto()
    NUMBER = auto()
    OPERATOR = auto()
    DELIMITER = auto()
    EOF = auto()
    UNKNOWN = auto()


@dataclass
class Token:
    """Represents a lexical token.

    Attributes:
        type: TokenType category
        lexeme: original text of the token
        line: 1-based line number where token starts
        column: 1-based column number where token starts
        literal: optional interpreted value (e.g. numeric value as string)
        corrected: whether this token was inserted by the auto-corrector
    """

    type: TokenType
    lexeme: str
    line: int
    column: int
    literal: Optional[str] = None
    corrected: bool = False

    def __repr__(self) -> str:
        return (
            f"Token(type={self.type.name}, lexeme={self.lexeme!r}, "
            f"line={self.line}, column={self.column}, corrected={self.corrected})"
        )

    def to_source(self) -> str:
        """Return the lexeme suitable for reconstructing source code.

        The parser/auto-corrector will use a sequence of `Token.to_source()`
        values to rebuild the corrected source text.
        """
        return self.lexeme


# Common lexical sets (exported for convenience)
KEYWORDS = {"int", "float", "if", "while"}
OPERATORS = {
    "+",
    "-",
    "*",
    "/",
    ">",
    "<",
    ">=",
    "<=",
    "==",
    "!=",
    "=",
}
DELIMITERS = {";", "(", ")", "{", "}", ","}
