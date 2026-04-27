"""Semantic analyzer for Mini-C compiler.

Performs semantic analysis on the AST including:
- Type checking
- Symbol table management
- Semantic error detection
- Attribute annotation to AST nodes
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class Symbol:
    """Represents a symbol in the symbol table."""
    name: str
    type_: str  # 'int', 'float'
    line: int
    column: int
    is_initialized: bool = False


class SemanticError:
    """Represents a semantic error."""
    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line = line
        self.column = column

    def __repr__(self) -> str:
        return f"SemanticError({self.message!r}, line={self.line}, column={self.column})"


class SemanticAnalyzer:
    """Performs semantic analysis on the AST."""

    def __init__(self):
        self.symbol_table: Dict[str, Symbol] = {}
        self.errors: List[SemanticError] = []
        self.temp_counter = 0
        self.current_scope = 0

    def analyze(self, ast_node) -> Tuple[bool, List[SemanticError]]:
        """Analyze the AST and return (success, errors)."""
        if ast_node is None:
            return False, [SemanticError("Empty AST")]

        self.visit(ast_node)
        success = len(self.errors) == 0
        return success, self.errors

    def new_temp(self) -> str:
        """Generate a new temporary variable."""
        self.temp_counter += 1
        return f"t{self.temp_counter}"

    def add_symbol(self, name: str, type_: str, line: int = 0, column: int = 0) -> bool:
        """Add a symbol to the symbol table. Returns True if added, False if already exists."""
        if name in self.symbol_table:
            self.errors.append(
                SemanticError(f"Variable '{name}' already declared", line, column)
            )
            return False
        self.symbol_table[name] = Symbol(name, type_, line, column)
        return True

    def get_symbol(self, name: str) -> Optional[Symbol]:
        """Get a symbol from the symbol table."""
        return self.symbol_table.get(name)

    def get_symbol_type(self, name: str) -> Optional[str]:
        """Get the type of a symbol."""
        symbol = self.get_symbol(name)
        return symbol.type_ if symbol else None

    def mark_initialized(self, name: str, line: int = 0, column: int = 0) -> bool:
        """Mark a variable as initialized."""
        symbol = self.get_symbol(name)
        if symbol is None:
            self.errors.append(
                SemanticError(f"Undeclared variable '{name}'", line, column)
            )
            return False
        symbol.is_initialized = True
        return True

    def is_initialized(self, name: str) -> bool:
        """Check if a variable is initialized."""
        symbol = self.get_symbol(name)
        return symbol.is_initialized if symbol else False

    def check_type_compatibility(self, type1: str, type2: str) -> bool:
        """Check if two types are compatible (allow implicit conversions)."""
        if type1 == type2:
            return True
        # Allow implicit conversions between int and float
        if {type1, type2} == {"int", "float"}:
            return True
        return False

    def infer_type(self, node) -> Optional[str]:
        """Infer the type of an expression."""
        if node is None:
            return None

        if node.name == "Factor":
            # Factor is either an identifier, number, or parenthesized expression
            if len(node.children) > 0:
                child = node.children[0]
                
                # Check if it's a number
                try:
                    float(child.name)
                    return "int"
                except (ValueError, TypeError):
                    pass

                # Check if it's an identifier
                if child.name in self.symbol_table:
                    return self.get_symbol_type(child.name)
                
                # Check if it's a parenthesized expression
                if child.name == "(":
                    for expr_child in node.children:
                        if expr_child.name == "Expr":
                            return self.infer_type(expr_child)

        elif node.name == "Expr" or node.name == "Term":
            # Expressions and terms propagate type from their children
            if len(node.children) > 0:
                return self.infer_type(node.children[0])

        elif node.name == "ExprPrime" or node.name == "TermPrime":
            # Primes might have operators; infer from their operands
            if len(node.children) > 1 and node.children[0].name != "ε":
                # Has an operation
                operand_type = None
                for child in node.children:
                    if child.name not in ("+", "-", "*", "/", "ε"):
                        operand_type = self.infer_type(child)
                        if operand_type:
                            break
                return operand_type

        return "unknown"

    def visit(self, node):
        """Visit an AST node for semantic analysis."""
        if node is None or node.name == "ε":
            return

        if node.name == "Program":
            for child in node.children:
                self.visit(child)

        elif node.name == "StmtList":
            for child in node.children:
                self.visit(child)

        elif node.name == "Stmt":
            for child in node.children:
                self.visit(child)

        elif node.name == "Declaration":
            self._handle_declaration(node)

        elif node.name == "Assignment":
            self._handle_assignment(node)

        elif node.name == "IfStmt":
            self._handle_if_stmt(node)

        elif node.name == "WhileStmt":
            self._handle_while_stmt(node)

        elif node.name == "Condition":
            self._handle_condition(node)

        elif node.name == "Expr":
            self._handle_expr(node)

    def _handle_declaration(self, node):
        """Handle Declaration node."""
        # Declaration structure: type, identifier, optional (=, expr), ;
        if len(node.children) < 2:
            return

        type_node = node.children[0]
        id_node = node.children[1]
        var_type = type_node.name
        var_name = id_node.name

        # Add to symbol table
        self.add_symbol(var_name, var_type)

        # If there's an initialization, check type compatibility
        if len(node.children) >= 4 and node.children[2].name == "=":
            expr_node = node.children[3]
            expr_type = self.infer_type(expr_node)
            
            if expr_type and expr_type != "unknown":
                if not self.check_type_compatibility(var_type, expr_type):
                    self.errors.append(
                        SemanticError(
                            f"Type mismatch: cannot assign {expr_type} to {var_type}",
                            line=0, column=0
                        )
                    )
            
            self.mark_initialized(var_name)
            self.visit(expr_node)

    def _handle_assignment(self, node):
        """Handle Assignment node."""
        # Assignment structure: id, =, expr, ;
        if len(node.children) < 3:
            return

        id_node = node.children[0]
        var_name = id_node.name

        # Check if variable is declared
        symbol = self.get_symbol(var_name)
        if symbol is None:
            self.errors.append(
                SemanticError(f"Undeclared variable '{var_name}'", 0, 0)
            )
            return

        # Check type compatibility with expression
        expr_node = node.children[2]
        expr_type = self.infer_type(expr_node)
        
        if expr_type and expr_type != "unknown":
            if not self.check_type_compatibility(symbol.type_, expr_type):
                self.errors.append(
                    SemanticError(
                        f"Type mismatch: cannot assign {expr_type} to {symbol.type_}",
                        0, 0
                    )
                )

        self.mark_initialized(var_name)
        self.visit(expr_node)

    def _handle_if_stmt(self, node):
        """Handle IfStmt node."""
        # IfStmt: if, (, condition, ), {, stmt_list, }
        for child in node.children:
            if child.name == "Condition":
                self.visit(child)
            elif child.name == "StmtList":
                self.visit(child)

    def _handle_while_stmt(self, node):
        """Handle WhileStmt node."""
        # WhileStmt: while, (, condition, ), {, stmt_list, }
        for child in node.children:
            if child.name == "Condition":
                self.visit(child)
            elif child.name == "StmtList":
                self.visit(child)

    def _handle_condition(self, node):
        """Handle Condition node."""
        # Condition: expr, relop, expr
        for child in node.children:
            if child.name == "Expr":
                self.visit(child)

    def _handle_expr(self, node):
        """Handle Expr node."""
        for child in node.children:
            self.visit(child)

    def get_symbol_table(self) -> Dict[str, Symbol]:
        """Return the symbol table."""
        return self.symbol_table

    def print_symbol_table(self) -> str:
        """Return a formatted string of the symbol table."""
        lines = ["Symbol Table:"]
        lines.append("-" * 60)
        lines.append(f"{'Name':<20} {'Type':<15} {'Initialized':<15} {'Line':<10}")
        lines.append("-" * 60)
        
        for name, symbol in self.symbol_table.items():
            lines.append(
                f"{name:<20} {symbol.type_:<15} {str(symbol.is_initialized):<15} {symbol.line:<10}"
            )        
        lines.append("-" * 60)
        return "\n".join(lines)
