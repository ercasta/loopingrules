"""M0 -- what the IR can express, proven on a real domain, with NO LM.

Run: `python -m loopingrules_forge.m0`

Two questions, per `docs/plan-forge.md`'s milestone M0:

1. **Derivability.** Can the catalog (which components exist, what each rule
   reads/writes) be *derived* from the rules' own source via `analyze`,
   rather than hand-declared?

2. **Expressiveness.** Can a small IR express a *whole* real domain
   (`cards`, all 12 of its rules, incl. the text front-ends), and can
   lowering it back to Python reproduce the domain's behaviour exactly?

## The reshape (what M0's first pass changed)

The first pass expressed 9 of `cards`' 12 rules and found three things.
This file is the reshape:

- **The IR IS a Python-subset AST.** The emitter is nearly trivial because
  the IR's shape and Python's are the same; "a grammar over a Python subset"
  is the honest description, not "a new language." So the term language just
  grew the missing Python shapes -- method calls (`text.split()`), indexing
  (`words[0]`), `len`, list literals -- rather than inventing anything.
- **Helpers.** `_find_card` is a pure query returning an entity; it is a
  *helper* -- an IR function in the same module, still `analyze`-readable.
- **A declared, verbatim escape.** `_parse_int` (a try/except lexical helper)
  and `_status_text` (a formatting helper) are embedded as raw Python. They
  are NOT an escape from analysis -- `analyze` still reads them, so the
  catalog still derives every read -- only from the IR's *generation*
  vocabulary. This is the concession ledger's first entry, and it is
  *lexing/formatting*: the edge, not the reasoning core.

Everything is still proven the same way: build a world from the real rules
and one from the IR-emitted rules, drive both with the kit's `replay` over
real command lines, and compare the (name-normalised) `signature`.
"""

from __future__ import annotations

import linecache
import sys
import types

import loopingrules.analyze as analyze
from loopingrules.engine import Reply, Said
from loopingrules.loop import Loop
from loopingrules_patterns import judge
from loopingrules_patterns.judge import Risk, RiskTolerance, TooRisky, flag_too_risky

from examples import cards

# =====================================================================
# 1. The IR -- a Python-subset AST
# =====================================================================

# -- expression constructors ------------------------------------------
def const(v):                 return ("const", v)
def var(n):                   return ("var", n)
def attr(e, f):               return ("attr", e, f)
def index(e, i):              return ("index", e, i)
def meth(e, name, args=()):   return ("meth", e, name, list(args))
def call(name, args=()):      return ("call", name, list(args))
def helper(name, args=()):    return ("helper", name, list(args))
def w_the(kind):              return ("the", kind)
def w_first(kind):            return ("first", kind)
def w_get(e, kind):           return ("get", e, kind)
def w_each(kinds, without=()): return ("each", tuple(kinds), tuple(without))
def binop(op, a, b):          return ("bin", op, a, b)
def cmp(op, a, b):            return ("cmp", op, a, b)
def land(a, b):               return ("and", a, b)
def lor(a, b):                return ("or", a, b)
def lnot(e):                  return ("not", e)
def isnone(e):                return ("isnone", e)
def isnotnone(e):             return ("notnone", e)
def cond(c, a, b):            return ("cond", c, a, b)
def fmt(tmpl, args):          return ("fmt", tmpl, list(args))
def listlit(els):             return ("list", list(els))
def tuplelit(els):            return ("tuple", list(els))

# -- statement constructors -------------------------------------------
def let(n, e):                return ("let", n, e)
def unpack(ns, e):            return ("unpack", tuple(ns), e)
def each_for(kinds, names, body, without=()):
    return ("for", ("each", tuple(kinds), tuple(without)), tuple(names), list(body))
def all_for(kind, names, body):
    return ("for", ("all", kind), tuple(names), list(body))
def if_(c, then, els=()):     return ("if", c, list(then), list(els))
def attach(e, kind, kw=None): return ("attach", e, kind, dict(kw or {}))
def detach(e, kind):          return ("detach", e, kind)
def replace(e, kind, kw):     return ("replace", e, kind, dict(kw))
def spawn(kind, kw=None):     return ("spawn", kind, dict(kw or {}))
def destroy(e):               return ("destroy", e)
def append(e, v):             return ("append", e, v)
def cont():                   return ("continue",)
def ret(e=None):              return ("return", e)


def _kind(k) -> str:
    return k.__name__


def e_src(e) -> str:
    tag = e[0]
    if tag == "const":   return repr(e[1])
    if tag == "var":     return e[1]
    if tag == "attr":    return "%s.%s" % (e_src(e[1]), e[2])
    if tag == "index":   return "%s[%s]" % (e_src(e[1]),
                                            e[2] if isinstance(e[2], int)
                                            else e_src(e[2]))
    if tag == "meth":    return "%s.%s(%s)" % (e_src(e[1]), e[2],
                                               ", ".join(e_src(a) for a in e[3]))
    if tag == "call":    return "%s(%s)" % (e[1], ", ".join(e_src(a) for a in e[2]))
    if tag == "helper":  return "%s(w%s)" % (e[1],
                                             "".join(", " + e_src(a) for a in e[2]))
    if tag == "the":     return "w.the(%s)" % _kind(e[1])
    if tag == "first":   return "w.first(%s)" % _kind(e[1])
    if tag == "get":     return "w.get(%s, %s)" % (e_src(e[1]), _kind(e[2]))
    if tag == "all":     return "w.all(%s)" % _kind(e[1])
    if tag == "each":
        ks, wo = e[1], e[2]
        s = "w.each(%s" % ", ".join(_kind(k) for k in ks)
        if wo:
            s += ", without=%s" % ", ".join(_kind(k) for k in wo)
        return s + ")"
    if tag == "bin":     return "(%s %s %s)" % (e_src(e[2]), e[1], e_src(e[3]))
    if tag == "cmp":     return "(%s %s %s)" % (e_src(e[2]), e[1], e_src(e[3]))
    if tag == "and":     return "(%s and %s)" % (e_src(e[1]), e_src(e[2]))
    if tag == "or":      return "(%s or %s)" % (e_src(e[1]), e_src(e[2]))
    if tag == "not":     return "(not %s)" % e_src(e[1])
    if tag == "isnone":  return "(%s is None)" % e_src(e[1])
    if tag == "notnone": return "(%s is not None)" % e_src(e[1])
    if tag == "cond":    return "(%s if %s else %s)" % (e_src(e[2]), e_src(e[1]),
                                                        e_src(e[3]))
    if tag == "fmt":
        args = e[2]
        if len(args) == 1:
            return "%r %% (%s)" % (e[1], e_src(args[0]))
        return "%r %% (%s)" % (e[1], ", ".join(e_src(a) for a in args))
    if tag == "list":    return "[%s]" % ", ".join(e_src(a) for a in e[1])
    if tag == "tuple":   return "(%s%s)" % (", ".join(e_src(a) for a in e[1]),
                                            "," if len(e[1]) == 1 else "")
    raise ValueError("unknown expression %r" % (tag,))


def _inst(kind, kw) -> str:
    return "%s(%s)" % (_kind(kind), ", ".join(
        "%s=%s" % (f, e_src(v)) for f, v in kw.items()))


def _s_src(s, ind):
    pad = "    " * ind
    tag = s[0]
    if tag == "let":
        return ["%s%s = %s" % (pad, s[1], e_src(s[2]))]
    if tag == "unpack":
        return ["%s%s = %s" % (pad, ", ".join(s[1]), e_src(s[2]))]
    if tag == "for":
        q, names, body = s[1], s[2], s[3]
        lines = ["%sfor %s in %s:" % (pad, ", ".join(names), e_src(q))]
        return lines + _lines(body, ind + 1)
    if tag == "if":
        lines = ["%sif %s:" % (pad, e_src(s[1]))]
        lines += _lines(s[2], ind + 1)
        if s[3]:
            lines.append("%selse:" % pad)
            lines += _lines(s[3], ind + 1)
        return lines
    if tag == "attach":
        return ["%sw.attach(%s, %s)" % (pad, e_src(s[1]), _inst(s[2], s[3]))]
    if tag == "detach":
        return ["%sw.detach(%s, %s)" % (pad, e_src(s[1]), _kind(s[2]))]
    if tag == "replace":
        return ["%sw.replace(%s, %s)" % (pad, e_src(s[1]), _inst(s[2], s[3]))]
    if tag == "spawn":
        return ["%sw.spawn(%s)" % (pad, _inst(s[1], s[2]))]
    if tag == "destroy":
        return ["%sw.destroy(%s)" % (pad, e_src(s[1]))]
    if tag == "append":
        return ["%s%s.append(%s)" % (pad, e_src(s[1]), e_src(s[2]))]
    if tag == "continue":
        return [pad + "continue"]
    if tag == "return":
        return [pad + "return" if s[1] is None else
                "%sreturn %s" % (pad, e_src(s[1]))]
    raise ValueError("unknown statement %r" % (tag,))


def _lines(body, ind):
    out = []
    for s in body:
        out += _s_src(s, ind)
    if not out:
        out = ["    " * ind + "pass"]
    return out


def emit_rule(name, body) -> str:
    return "\n".join(["def %s(w):" % name] + _lines(body, 1))


def emit_helper(name, params, body) -> str:
    return "\n".join(["def %s(w%s):" % (name, "".join(", " + p for p in params))]
                     + _lines(body, 1))


# =====================================================================
# 2. Hand-written IR for `cards` -- all 13 rules
# =====================================================================

Listing, Wants, Copies = cards.Listing, cards.Wants, cards.Copies
Purse, RiskProfile, CardDef = cards.Purse, cards.RiskProfile, cards.CardDef
Wanted, Affordable, FairPriced = cards.Wanted, cards.Affordable, cards.FairPriced
Bought, BadCommand, GoalMet, Announced = (
    cards.Bought, cards.BadCommand, cards.GoalMet, cards.Announced)

# -- the tag family, the act, the goal check, the replies (unchanged
#    in shape from the first pass) -------------------------------------

def ir_tag_wanted():
    return [
        each_for([Listing], ("entity", "listing"), [
            let("wants", w_get(attr(var("listing"), "card"), Wants)),
            if_(isnone(var("wants")), [detach(var("entity"), Wanted), cont()]),
            let("copies", w_get(attr(var("listing"), "card"), Copies)),
            let("have", cond(var("copies"), attr(var("copies"), "count"), const(0))),
            if_(cmp("<", var("have"), attr(var("wants"), "qty")),
                [attach(var("entity"), Wanted)],
                [detach(var("entity"), Wanted)]),
        ]),
    ]


def ir_tag_affordable():
    return [
        let("purse", w_the(Purse)),
        let("risk", w_the(RiskProfile)),
        each_for([Listing], ("entity", "listing"), [
            let("room", binop("-", attr(var("purse"), "cash"),
                              attr(var("risk"), "min_cash_reserve"))),
            if_(land(cmp("<=", attr(var("listing"), "price"), var("room")),
                     cmp("<=", attr(var("listing"), "price"),
                         attr(var("risk"), "max_spend_per_trade"))),
                [attach(var("entity"), Affordable)],
                [detach(var("entity"), Affordable)]),
        ]),
    ]


def ir_tag_fair_priced():
    return [
        let("risk", w_the(RiskProfile)),
        each_for([Listing], ("entity", "listing"), [
            let("card_def", w_get(attr(var("listing"), "card"), CardDef)),
            if_(isnone(var("card_def")), [detach(var("entity"), FairPriced), cont()]),
            let("limit", binop("*", attr(var("card_def"), "value"),
                               binop("+", const(1), attr(var("risk"), "max_premium")))),
            if_(cmp("<=", attr(var("listing"), "price"), var("limit")),
                [attach(var("entity"), FairPriced)],
                [detach(var("entity"), FairPriced)]),
        ]),
    ]


def ir_tag_risk_level():
    return [
        let("purse", w_the(Purse)),
        let("risk", w_the(RiskProfile)),
        each_for([Listing], ("entity", "listing"), [
            let("room", binop("-", attr(var("purse"), "cash"),
                              attr(var("risk"), "min_cash_reserve"))),
            let("level", cond(cmp("<=", var("room"), const(0)), const(1.0),
                              call("min", [const(1.0),
                                           binop("/", attr(var("listing"), "price"),
                                                 var("room"))]))),
            replace(var("entity"), Risk, {
                "level": var("level"),
                "reason": fmt("would use %.0f%% of the %d cash still free to spend",
                              [binop("*", var("level"), const(100)),
                               call("max", [var("room"), const(0)])]),
            }),
        ]),
    ]


def ir_decide_buy():
    return [
        each_for([Listing, Wanted, Affordable, FairPriced],
                 ("entity", "listing", "_wanted", "_affordable", "_fair"), [
            let("wants", w_get(attr(var("listing"), "card"), Wants)),
            let("copies", w_get(attr(var("listing"), "card"), Copies)),
            let("have", cond(var("copies"), attr(var("copies"), "count"), const(0))),
            if_(lor(isnone(var("wants")),
                    cmp(">=", var("have"), attr(var("wants"), "qty"))), [cont()]),
            unpack(("purse_entity", "purse"), w_first(Purse)),
            let("risk", w_the(RiskProfile)),
            if_(cmp(">", attr(var("listing"), "price"),
                    binop("-", attr(var("purse"), "cash"),
                          attr(var("risk"), "min_cash_reserve"))), [cont()]),
            replace(var("purse_entity"), Purse, {
                "cash": binop("-", attr(var("purse"), "cash"),
                              attr(var("listing"), "price"))}),
            replace(attr(var("listing"), "card"), Copies, {
                "count": binop("+", var("have"), const(1))}),
            destroy(var("entity")),
            spawn(Bought, {"card": attr(var("listing"), "card"),
                           "price": attr(var("listing"), "price")}),
        ], without=[TooRisky]),
    ]


def ir_check_goal():
    return [
        let("wanted", w_each([CardDef, Wants])),
        if_(lor(lnot(var("wanted")), isnotnone(w_the(GoalMet))), [ret()]),
        each_for([CardDef, Wants], ("card_entity", "_card_def", "wants"), [
            let("copies", w_get(var("card_entity"), Copies)),
            let("have", cond(var("copies"), attr(var("copies"), "count"), const(0))),
            if_(cmp("<", var("have"), attr(var("wants"), "qty")), [ret()]),
        ]),
        spawn(GoalMet),
    ]


def ir_reply_bought():
    return [
        each_for([Bought], ("entity", "bought"), [
            destroy(var("entity")),
            let("card_def", w_get(attr(var("bought"), "card"), CardDef)),
            let("name", cond(var("card_def"), attr(var("card_def"), "name"),
                             fmt("card #%d", [attr(var("bought"), "card")]))),
            spawn(Reply, {"channel": const("user"),
                          "text": fmt("bought %s for %d",
                                      [var("name"), attr(var("bought"), "price")])}),
        ]),
    ]


def ir_reply_bad_command():
    return [
        each_for([BadCommand], ("entity", "bad"), [
            destroy(var("entity")),
            spawn(Reply, {"channel": const("user"),
                          "text": fmt("! %s", [attr(var("bad"), "why")])}),
        ]),
    ]


def ir_reply_goal_met():
    return [
        each_for([GoalMet], ("entity", "_goal"), [
            attach(var("entity"), Announced),
            spawn(Reply, {"channel": const("user"),
                          "text": const("goal met -- every wanted card "
                                        "is in the collection")}),
        ], without=[Announced]),
    ]


# -- the text front-ends (NEW: what the reshape unlocked) --------------

def _command(words_expr, verb):
    """`if not words or words[0].lower() != "<verb>": continue` -- the
    three hear_* rules share it."""
    return if_(lor(lnot(var("words")),
                   cmp("!=", meth(index(var("words"), 0), "lower"),
                       const(verb))), [cont()])


def ir_hear_list():
    return [
        each_for([Said], ("entity", "said"), [
            let("words", meth(attr(var("said"), "text"), "split")),
            _command(None, "list"),
            destroy(var("entity")),
            if_(cmp("!=", call("len", [var("words")]), const(3)),
                [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                    "why": const("usage: list <card> <price>")}),
                 cont()]),
            let("name", index(var("words"), 1)),
            let("price_text", index(var("words"), 2)),
            let("card", helper("_find_card", [var("name")])),
            if_(isnone(var("card")),
                [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                    "why": fmt("unknown card %r", [var("name")])}),
                 cont()]),
            let("price", call("_parse_int", [var("price_text")])),
            if_(isnone(var("price")),
                [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                    "why": fmt("not a price: %r", [var("price_text")])}),
                 cont()]),
            spawn(Listing, {"card": var("card"), "price": var("price")}),
        ]),
    ]


def ir_hear_want():
    return [
        each_for([Said], ("entity", "said"), [
            let("words", meth(attr(var("said"), "text"), "split")),
            _command(None, "want"),
            destroy(var("entity")),
            if_(cmp("not in", call("len", [var("words")]),
                    tuplelit([const(2), const(3)])),
                [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                    "why": const("usage: want <card> [qty]")}),
                 cont()]),
            let("card", helper("_find_card", [index(var("words"), 1)])),
            if_(isnone(var("card")),
                [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                    "why": fmt("unknown card %r",
                                               [index(var("words"), 1)])}),
                 cont()]),
            let("qty", const(1)),
            if_(cmp("==", call("len", [var("words")]), const(3)), [
                let("qty", call("_parse_int", [index(var("words"), 2)])),
                if_(lor(isnone(var("qty")), cmp("<", var("qty"), const(1))),
                    [spawn(BadCommand, {"text": attr(var("said"), "text"),
                                        "why": fmt("not a quantity: %r",
                                                   [index(var("words"), 2)])}),
                     cont()]),
            ]),
            replace(var("card"), Wants, {"qty": var("qty")}),
        ]),
    ]


def ir_hear_status():
    # the formatting lives in a verbatim helper; the rule itself is IR.
    return [
        each_for([Said], ("entity", "said"), [
            let("words", meth(attr(var("said"), "text"), "split")),
            _command(None, "status"),
            destroy(var("entity")),
            spawn(Reply, {"channel": const("user"),
                          "text": helper("_status_text")}),
        ]),
    ]


IR = {
    "hear_list": ir_hear_list,
    "hear_want": ir_hear_want,
    "hear_status": ir_hear_status,
    "tag_wanted": ir_tag_wanted,
    "tag_affordable": ir_tag_affordable,
    "tag_fair_priced": ir_tag_fair_priced,
    "tag_risk_level": ir_tag_risk_level,
    "decide_buy": ir_decide_buy,
    "check_goal": ir_check_goal,
    "reply_bought": ir_reply_bought,
    "reply_bad_command": ir_reply_bad_command,
    "reply_goal_met": ir_reply_goal_met,
}

# IR-defined helpers: an IR function in the same module, `analyze`-readable.
IR_HELPERS = {
    "_find_card": (["name"], [
        all_for(CardDef, ("entity", "card_def"), [
            if_(cmp("==", meth(attr(var("card_def"), "name"), "lower"),
                    meth(var("name"), "lower")),
                [ret(var("entity"))]),
        ]),
        ret(const(None)),
    ]),
}

# Verbatim helpers: raw Python, embedded as-is. NOT an escape from analysis
# (analyze still reads them, so the catalog still derives every read) -- only
# from the IR's *generation* vocabulary. The concession ledger's first entry,
# and it is purely lexing/formatting: the edge, not the reasoning core.
VERBATIM = {
    "_parse_int": '''
def _parse_int(text):
    try:
        return int(text)
    except ValueError:
        return None
''',
    "_status_text": '''
def _status_text(w):
    purse = w.the(Purse)
    lines = ["cash: %d" % purse.cash]
    wanted = sorted(w.each(CardDef, Wants), key=lambda row: row[1].name)
    if not wanted:
        lines.append("no goal set")
    for card_entity, card_def, want in wanted:
        copies = w.get(card_entity, Copies)
        have = copies.count if copies else 0
        lines.append("%s: %d/%d" % (card_def.name, have, want.qty))
    if w.the(GoalMet) is not None:
        lines.append("goal met")
    return "; ".join(lines)
''',
}

ORDER = ("hear_list", "hear_want", "hear_status", "tag_wanted",
         "tag_affordable", "tag_fair_priced", "tag_risk_level",
         "flag_too_risky", "decide_buy", "check_goal", "reply_bought",
         "reply_bad_command", "reply_goal_met")


# =====================================================================
# 3. Lowering the IR back to Python, as a real, analyzable module
# =====================================================================

HEADER = """\
from examples.cards import (CardDef, Copies, Wants, Purse, RiskProfile,
    Listing, Wanted, Affordable, FairPriced, Bought, BadCommand, GoalMet,
    Announced)
from loopingrules_patterns.judge import Risk, RiskTolerance, TooRisky
from loopingrules.engine import Said, Reply
"""


def emit_module(rules=IR, ir_helpers=IR_HELPERS, verbatim=VERBATIM) -> str:
    parts = [HEADER]
    for name, (params, body) in ir_helpers.items():
        parts.append(emit_helper(name, params, body))
    for src in verbatim.values():
        parts.append(src.strip())
    for name, body in rules.items():
        parts.append(emit_rule(name, body() if callable(body) else body))
    return "\n\n\n".join(parts)


def load_emitted(source, name="forge_cards"):
    """Lower the emitted source into a REAL module (registered in
    `sys.modules`, source in `linecache`, a loader so `inspect` can read it
    back). This is what makes helpers work: `analyze` resolves same-module
    calls against `sys.modules[name]`, so `_find_card` is followed, not the
    same-named function somewhere in `cards`."""
    filename = name + ".py"
    linecache.cache[filename] = (len(source), None, source.splitlines(True),
                                 filename)
    module = types.ModuleType(name)
    module.__dict__["__name__"] = name
    module.__loader__ = types.SimpleNamespace(get_source=lambda _name: source)
    sys.modules[name] = module
    exec(compile(source, filename, "exec"), module.__dict__)  # noqa: S102
    return module


def make_install(module):
    """An `install` shaped like `cards.install`, registering the emitted
    rules and seeding identically, so the kit's `replay` can drive it."""
    def install(loop, cash=100):
        for name in ORDER:
            if hasattr(module, name):
                loop.rule(getattr(module, name))
            elif name == "flag_too_risky":
                loop.rule(flag_too_risky)
            else:                                   # pragma: no cover
                raise KeyError(name)
        _seed(loop, cash)
    return install


def _seed(loop, cash=100):
    w = loop.world
    for card_def in cards.DEFAULT_CATALOG:
        if cards._find_card(w, card_def.name) is None:
            entity = w.spawn(card_def)
            w.attach(entity, cards.Copies(0))
    if w.first(cards.Purse) is None:
        w.spawn(cards.Purse(cash))
    if w.first(cards.RiskProfile) is None:
        w.spawn(cards.RiskProfile(max_spend_per_trade=50, min_cash_reserve=0,
                                  max_premium=0.25))
    if w.first(RiskTolerance) is None:
        w.spawn(RiskTolerance(max_level=0.8))


# =====================================================================
# 4. The equivalence harness (driven by real command lines)
# =====================================================================

LINES = ("list dragon 30", "want dragon 1", "list goblin 3", "want goblin 1",
         "list goblin 12", "status", "bogus line")


def signature(world, fired):
    """Behavioural signature over BARE rule names. The kit's own hash keeps
    the module qualifier (so two domains' `hear` do not collide); here the
    whole point is that `cards.hear_list` and `forge_cards.hear_list` behave
    alike, so the qualifier is stripped before hashing."""
    from loopingrules_calibration.kit import _signature
    bare = tuple(tuple(n.rsplit(".", 1)[-1] for n in tick) for tick in fired)
    return _signature(world, bare)


# =====================================================================
# 5. The two questions M0 asks
# =====================================================================

def report_derivability():
    print("== 1. Derivability: the catalog from `analyze` alone ==")
    report = analyze.component_map(*cards.RULES)
    kinds = sorted(set(report.reads) | set(report.writes),
                   key=lambda k: k.__name__)
    print("  components seen: %d" % len(kinds))
    for kind in kinds:
        readers = report.reads.get(kind, set())
        writers = report.writes.get(kind, set())
        print("    %-14s read %-2d write %-2d %s" % (
            kind.__name__, len(readers), len(writers),
            "<-- no in-rule writer (seeded / edge)" if readers and not writers
            else ("<-- no in-rule reader (edge)" if writers and not readers
                  else "")))
    print("  opaque (analyze refused): %s"
          % (sorted(report.opaque) or "none"))


def report_expressiveness():
    print("\n== 2. Expressiveness: IR -> Python -> same behaviour ==")
    module = load_emitted(emit_module())

    # reads must match, or the gating (and so the trajectory) differs.
    bad = 0
    for name in IR:
        real = analyze.analyze(getattr(cards, name))
        got = analyze.analyze(getattr(module, name))
        ok = (got.reads == real.reads
              and got.negated_reads == real.negated_reads)
        bad += not ok
        print("    reads %-18s %s" % (
            name, "ok" if ok else "MISMATCH got=%r want=%r" % (
                sorted(k.__name__ for k in got.reads),
                sorted(k.__name__ for k in real.reads))))
    print("    %d/%d rules expressed" % (len(IR) - bad, len(IR)))

    from loopingrules_calibration.kit import Scenario, replay
    scenario = Scenario(lines=LINES)
    real = replay(scenario, cards.install)
    emit = replay(scenario, make_install(module))

    print("\n    real: ticks=%d hot=%r replies=%r"
          % (real.ticks, list(real.hot), list(real.replies)))
    print("    emit: ticks=%d hot=%r replies=%r"
          % (emit.ticks, list(emit.hot), list(emit.replies)))
    rs = signature(real.world, real.fired)
    es = signature(emit.world, emit.fired)
    print("    real signature %s" % rs)
    print("    emit signature %s" % es)
    print("    EQUAL: %s" % (rs == es))
    return bad == 0 and rs == es


RESHAPE_NOTE = """
== What the reshape settled ==

ALL 12 `cards` rules are now expressed as IR, including the text
front-ends (13 with the judge's `flag_too_risky`, kept verbatim -- it is an
imported, shared pattern, not this domain's structure). The
first pass's escapes were closed by *extending the term language to more
Python shapes* (method calls, indexing, len, list literals) and by two
mechanisms:

  * HELPERS (`_find_card`) -- an IR function in the same module, still read
    by `analyze`, so the catalog still derives its reads.
  * VERBATIM HELPERS (`_parse_int`, `_status_text`) -- raw Python, embedded
    as-is. Not an escape from analysis (still analyzable), only from the
    IR's *generation* vocabulary. This is the concession ledger's first
    entry, and both are lexing/formatting -- the edge, not the reasoning.

The multi-level-control worry from the first pass was overstated: the
`continue` sits in the OUTER loop and `_find_card`'s loop is inside the
helper -- separate scopes, no labelled break needed.

Design decision (M0 finding c, now acted on): the IR IS a Python-subset
AST, not a new language. The emitter is near-trivial because the two shapes
are the same; the "grammar" is a check over that subset, and the artifact
stays plain, `analyze`-readable Python.
"""


def main():
    report_derivability()
    ok = report_expressiveness()
    print(RESHAPE_NOTE)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
