"""Deterministic control-flow and def-use analysis for the supplied 4GL subset."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z_0-9]*(?:\.[A-Za-z_][A-Za-z_0-9]*)?\b")
KEYWORDS = {
    "AND", "AS", "BEGIN", "BY", "CALL", "CHAR", "COMMIT", "CONTINUE", "DATABASE",
    "DECIMAL", "DEFINE", "DELETE", "ELSE", "END", "ERROR", "FALSE", "FROM",
    "FUNCTION", "IF", "IN", "INITIALIZE", "INSERT", "INTEGER", "INTO", "IS",
    "LET", "MESSAGE", "NOT", "NULL", "OR", "RECORD", "RETURN", "ROLLBACK",
    "SET", "SQLCODE", "STOP", "THEN", "TO", "TRUE", "UPDATE", "VALUES",
    "WHENEVER", "WHERE", "WORK",
}


@dataclass
class Statement:
    line: int
    kind: str
    text: str
    children: list[Statement] = field(default_factory=list)


@dataclass
class Node:
    id: str
    line: int | None
    kind: str
    label: str
    text: str


@dataclass
class Graph:
    name: str
    parameters: list[str]
    nodes: dict[str, Node]
    edges: list[tuple[str, str, str]]

    @property
    def complexity(self) -> int:
        return len(self.edges) - len(self.nodes) + 2

    @property
    def decisions(self) -> int:
        return sum(node.kind == "if" for node in self.nodes.values())

    def dot(self) -> str:
        def quote(value: str) -> str:
            return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

        lines = ["digraph G {", "rankdir=TB;", 'node [shape=box, style="rounded,filled", fillcolor="#f1f5f9"];']
        for node in self.nodes.values():
            shape = "diamond" if node.kind == "if" else "oval" if node.kind in {"entry", "exit"} else "box"
            lines.append(f"{quote(node.id)} [label={quote(node.label)}, shape={shape}];")
        for origin, target, branch in self.edges:
            label = f" [label={quote(branch)}]" if branch else ""
            lines.append(f"{quote(origin)} -> {quote(target)}{label};")
        lines.append("}")
        return "\n".join(lines)


def functions_from_source(source: str) -> list[tuple[str, list[str], list[tuple[int, str]]]]:
    """Extract function bodies and preserve original line numbers."""
    lines = list(enumerate(source.splitlines(), 1))
    result = []
    position = 0
    while position < len(lines):
        line_no, raw = lines[position]
        match = re.match(r"\s*FUNCTION\s+(\w+)\s*\(([^)]*)\)", raw, re.I)
        if not match:
            position += 1
            continue
        name = match.group(1)
        parameters = [part.strip() for part in match.group(2).split(",") if part.strip()]
        body = []
        position += 1
        while position < len(lines) and not re.match(r"\s*END\s+FUNCTION\b", lines[position][1], re.I):
            body.append(lines[position])
            position += 1
        if position == len(lines):
            raise ValueError(f"A função {name} não possui END FUNCTION.")
        result.append((name, parameters, body))
        position += 1
    if not result:
        raise ValueError("Nenhuma função 4GL foi encontrada no fonte.")
    return result


def _logical_lines(body: list[tuple[int, str]]) -> list[tuple[int, str]]:
    clean = [(line, raw.strip()) for line, raw in body if raw.strip() and not raw.lstrip().startswith("#")]
    result = []
    index = 0
    while index < len(clean):
        line, value = clean[index]
        upper = value.upper()
        if upper.startswith("DEFINE "):
            index += 1
            while index < len(clean) and clean[index][1].upper().startswith(("P_", "L_")):
                index += 1
            continue
        if upper.startswith(("INSERT ", "UPDATE ", "DELETE ")):
            parts = [value]
            index += 1
            while index < len(clean) and not clean[index][1].upper().startswith("WHENEVER "):
                parts.append(clean[index][1])
                index += 1
            result.append((line, " ".join(parts)))
            continue
        if upper.startswith("LET ") and value.count("(") > value.count(")"):
            parts = [value]
            balance = value.count("(") - value.count(")")
            index += 1
            while balance > 0 and index < len(clean):
                part = clean[index][1]
                parts.append(part)
                balance += part.count("(") - part.count(")")
                index += 1
            result.append((line, " ".join(parts)))
            continue
        result.append((line, value))
        index += 1
    return result


def _parse_statements(lines: list[tuple[int, str]], position: int = 0, expect_end: bool = False) -> tuple[list[Statement], int]:
    statements = []
    while position < len(lines):
        line, value = lines[position]
        upper = value.upper()
        if upper == "END IF":
            if not expect_end:
                raise ValueError(f"END IF inesperado na linha {line}.")
            return statements, position + 1
        inline = re.fullmatch(r"IF\s+(.+?)\s+THEN\s+(.+?)\s+END\s+IF", value, re.I)
        if inline:
            child_text = inline.group(2)
            child_kind = child_text.split()[0].lower()
            statements.append(Statement(line, "if", f"IF {inline.group(1)}", [Statement(line, child_kind, child_text)]))
            position += 1
            continue
        block = re.fullmatch(r"IF\s+(.+?)\s+THEN", value, re.I)
        if block:
            children, position = _parse_statements(lines, position + 1, expect_end=True)
            statements.append(Statement(line, "if", f"IF {block.group(1)}", children))
            continue
        if upper.startswith("IF ") or upper == "ELSE":
            raise ValueError(f"Estrutura IF não suportada na linha {line}: {value}")
        statements.append(Statement(line, value.split()[0].lower(), value))
        position += 1
    if expect_end:
        raise ValueError("IF sem END IF no fonte.")
    return statements, position


def build_graph(name: str, parameters: list[str], body: list[tuple[int, str]]) -> Graph:
    statements, _ = _parse_statements(_logical_lines(body))
    nodes = {
        "entry": Node("entry", None, "entry", "Entrada", ""),
        "exit": Node("exit", None, "exit", "Saída", ""),
    }
    edges = []

    def add(statement: Statement) -> str:
        identifier = f"n{len(nodes) - 1}"
        label = f"L{statement.line}: {statement.text}"
        if len(label) > 85:
            label = label[:82] + "..."
        nodes[identifier] = Node(identifier, statement.line, statement.kind, label, statement.text)
        return identifier

    def wire_sequence(items: list[Statement], follow: str) -> str:
        current = follow
        for statement in reversed(items):
            identifier = add(statement)
            if statement.kind == "if":
                yes = wire_sequence(statement.children, current)
                edges.append((identifier, yes, "Sim"))
                edges.append((identifier, current, "Não"))
            elif statement.kind == "return":
                edges.append((identifier, "exit", ""))
            else:
                edges.append((identifier, current, ""))
            current = identifier
        return current

    first = wire_sequence(statements, "exit")
    edges.append(("entry", first, ""))
    graph = Graph(name, parameters, nodes, edges)
    if graph.complexity != graph.decisions + 1:
        raise ValueError(f"GFC inconsistente para {name}.")
    return graph


def build_all_graphs(source: str) -> list[Graph]:
    return [build_graph(*item) for item in functions_from_source(source)]


def _variables(text: str) -> set[str]:
    text = re.sub(r'"(?:[^"]|"")*"', " ", text)
    called = {match.group(1) for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", text)}
    return {
        match.group(0) for match in IDENTIFIER.finditer(text)
        if match.group(0).upper() not in KEYWORDS and match.group(0) not in called
    }


def _def_use(node: Node) -> tuple[set[str], set[str], str]:
    text = node.text
    kind = node.kind
    if kind == "entry":
        return set(), set(), ""
    if kind == "if":
        return set(), _variables(text[3:]), "p-uso"
    if kind == "let":
        match = re.match(r"LET\s+([\w.]+)\s*=\s*(.*)", text, re.I)
        if not match:
            raise ValueError(f"LET não reconhecido na linha {node.line}.")
        return {match.group(1)}, _variables(match.group(2)), "c-uso"
    if kind == "initialize":
        return {"mr_item.*"}, set(), ""
    if kind in {"insert", "update", "delete"}:
        # SQL updates sqlca.sqlcode; references to table and column names are not variable uses.
        return {"sqlca.sqlcode"}, set(re.findall(r"\bmr_item\.\w+\b", text)), "c-uso"
    if kind in {"return", "call", "message"}:
        return set(), _variables(text.split(" ", 1)[1]) if " " in text else set(), "c-uso"
    return set(), set(), ""


def def_use_pairs(graph: Graph) -> list[dict[str, str | int | None]]:
    """Compute reaching definitions on graph edges and emit def-clear pairs."""
    facts = {node.id: _def_use(node) for node in graph.nodes.values()}
    variables = set(graph.parameters)
    for definitions, uses, _ in facts.values():
        variables.update(definitions)
        variables.update(uses)
    variables.discard("mr_item.*")
    origin = {(variable, "entry") for variable in variables}
    incoming: dict[str, set[tuple[str, str]]] = {key: set() for key in graph.nodes}
    outgoing: dict[str, set[tuple[str, str]]] = {key: set() for key in graph.nodes}
    incoming["entry"] = set(origin)
    changed = True
    while changed:
        changed = False
        for identifier in graph.nodes:
            if identifier != "entry":
                incoming[identifier] = set().union(*(outgoing[prior] for prior, target, _ in graph.edges if target == identifier))
            definitions, _, _ = facts[identifier]
            actual_definitions = set(definitions)
            if "mr_item.*" in actual_definitions:
                actual_definitions.remove("mr_item.*")
                actual_definitions.update(var for var in variables if var.startswith("mr_item."))
            next_out = {fact for fact in incoming[identifier] if fact[0] not in actual_definitions}
            next_out.update((var, identifier) for var in actual_definitions)
            if next_out != outgoing[identifier]:
                outgoing[identifier] = next_out
                changed = True
    pairs = []
    for identifier, node in graph.nodes.items():
        _, uses, use_kind = facts[identifier]
        for variable in sorted(uses):
            for _, defining_id in sorted(fact for fact in incoming[identifier] if fact[0] == variable):
                defining_node = graph.nodes[defining_id]
                pairs.append({
                    "function": graph.name,
                    "variable": variable,
                    "definition": defining_id,
                    "definition_line": defining_node.line,
                    "use": identifier,
                    "use_line": node.line,
                    "kind": use_kind,
                    "origin": "parâmetro" if defining_id == "entry" and variable in graph.parameters else "externo" if defining_id == "entry" else "fonte",
                })
    return pairs
