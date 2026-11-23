import re
from functools import cache

from pydantic import BaseModel, Field

from state_of_soroban.catalog import Pattern
from state_of_soroban.extract.rust import FunctionInfo, ParsedFile, digest, normalise

MAX_MATCHES_PER_PATTERN = 400
SNIPPET_LIMIT = 400


class Hit(BaseModel):
    pattern: str
    start_byte: int
    line_start: int
    line_end: int
    fn_name: str | None
    in_test: bool
    snippet: str
    shape_hash: str
    captures: dict[str, str] = Field(default_factory=dict)


@cache
def compiled(expression: str) -> re.Pattern[str]:
    return re.compile(expression)


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def regex_hits(pattern: Pattern, parsed: ParsedFile) -> list[Hit]:
    hits: list[Hit] = []
    for found in compiled(pattern.match.regex or "").finditer(parsed.clean):
        line_start = line_of(parsed.clean, found.start())
        line_end = line_start + found.group(0).count("\n")
        function = parsed.function_at(line_start)
        snippet = normalise(found.group(0))[:SNIPPET_LIMIT]
        hits.append(
            Hit(
                pattern=pattern.id,
                start_byte=len(parsed.clean[: found.start()].encode()),
                line_start=line_start,
                line_end=line_end,
                fn_name=function.name if function else None,
                in_test=parsed.is_test or bool(function and function.is_test),
                snippet=snippet,
                shape_hash=digest(snippet),
                captures={k: v for k, v in found.groupdict().items() if v is not None},
            )
        )
        if len(hits) >= MAX_MATCHES_PER_PATTERN:
            break
    return hits


def function_matches(pattern: Pattern, function: FunctionInfo) -> bool:
    match = pattern.match
    if match.contract_only and not function.is_contract_fn:
        return False
    if match.skip_tests and function.is_test:
        return False
    if match.is_test_helper and not (
        function.is_test and not any(a.startswith("test") for a in function.attributes)
    ):
        return False
    if match.name and not compiled(match.name).search(function.name):
        return False
    if match.max_loc is not None and function.loc > match.max_loc:
        return False
    if match.params_match:
        params = ", ".join(f"{p.name}: {p.type}" for p in function.params)
        if not compiled(match.params_match).search(params):
            return False
    if any(not compiled(rule).search(function.text) for rule in match.contains):
        return False
    return not any(compiled(rule).search(function.text) for rule in match.lacks)


def function_hits(pattern: Pattern, parsed: ParsedFile) -> list[Hit]:
    return [
        Hit(
            pattern=pattern.id,
            start_byte=function.first_byte,
            line_start=function.line_start,
            line_end=function.line_end,
            fn_name=function.name,
            in_test=function.is_test,
            snippet=normalise(function.text)[:SNIPPET_LIMIT],
            shape_hash=function.shape_hash,
        )
        for function in parsed.functions
        if function_matches(pattern, function)
    ][:MAX_MATCHES_PER_PATTERN]


def type_hits(pattern: Pattern, parsed: ParsedFile) -> list[Hit]:
    match = pattern.match
    flags = {
        "contracttype": "is_contracttype",
        "contracterror": "is_contracterror",
        "contractevent": "is_contractevent",
    }
    hits: list[Hit] = []
    for item in parsed.types:
        if match.type_kind and item.kind != match.type_kind:
            continue
        if any(not getattr(item, flags[flag], False) for flag in match.flags):
            continue
        if match.name and not compiled(match.name).search(item.name):
            continue
        hits.append(
            Hit(
                pattern=pattern.id,
                start_byte=item.line_start,
                line_start=item.line_start,
                line_end=item.line_start,
                fn_name=None,
                in_test=item.is_test,
                snippet=f"{item.kind} {item.name} ["
                + ", ".join(m.name for m in item.members[:12])
                + "]",
                shape_hash=item.shape_hash,
            )
        )
    return hits[:MAX_MATCHES_PER_PATTERN]


def run_patterns(patterns: list[Pattern], parsed: ParsedFile) -> list[Hit]:
    hits: list[Hit] = []
    for pattern in patterns:
        match pattern.match.kind:
            case "regex":
                hits.extend(regex_hits(pattern, parsed))
            case "function":
                hits.extend(function_hits(pattern, parsed))
            case "type":
                hits.extend(type_hits(pattern, parsed))
    return hits
