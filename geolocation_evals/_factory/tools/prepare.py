#!/usr/bin/env python3
"""Stage 00 (prepare): prepare isolated case workspaces for streets fuzzing or golden evals."""

import argparse
import json
import random
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_golden import validate_golden

EVALS_ROOT = Path(__file__).resolve().parent.parent.parent
ICM_ROOT = EVALS_ROOT.parent / "geolocation_icm"
GOLDEN_PATH = EVALS_ROOT / "_factory" / "golden.json"
STREETS_PATH = EVALS_ROOT / "_factory" / "corroios_streets.json"
RESULTS_ROOT = EVALS_ROOT.parent / "output" / "evals"
TEMP_EVALS_ROOT = Path(tempfile.gettempdir()) / "icm-evals"

PREFIX_STOPWORDS = {
    "acesso",
    "alameda",
    "autoestrada",
    "avenida",
    "azinhaga",
    "beco",
    "calçada",
    "caminho",
    "estrada",
    "jardim",
    "largo",
    "parque",
    "pátio",
    "patio",
    "praceta",
    "praça",
    "rotunda",
    "rua",
    "travessa",
    "urbanização",
    "viela",
    "do",
    "da",
    "dos",
    "das",
    "de",
    "e",
    "em",
}


def make_blind_prompt(out_dir_rel: str, maps_path: str, raw_input: str) -> str:
    return (
        "Your workspace directory for this run is the current directory.\n"
        "Read `AGENTS.md`, then run the geolocation ICM pipeline for the customer message below, "
        "following every stage contract and check. Write `orientation.json` only inside "
        f"`{out_dir_rel}` (pass `--out-dir {out_dir_rel} --maps {maps_path}` to `write_stage01.py` "
        f"and `--out {maps_path}` to `google_maps.py`, without `--cleanup-maps`).\n\n"
        f"Customer message:\n{raw_input}"
    )


def _distinctive_word_indices(words: list[str]) -> list[int]:
    return [
        idx
        for idx, w in enumerate(words)
        if w.lower().strip(",.") not in PREFIX_STOPWORDS and len(w) >= 4
    ]


ABBREV_MAP = {
    "rua": ["r.", "r", "rua"],
    "avenida": ["av.", "av", "avenida"],
    "travessa": ["tv.", "tv", "travessa"],
    "praceta": ["pct.", "pct", "praceta"],
    "alameda": ["al.", "alameda"],
    "largo": ["lg.", "largo"],
    "estrada": ["estr.", "estrada"],
}

WHATSAPP_WRAPPERS = [
    "{addr}",
    "Boa tarde! A entrega é na {addr}. É no 3.º esquerdo, campainha avariada",
    "Boas!! olha manda pra {addr} sff, bloco B 2º dto",
    "oie td bem? entrega na {addr} portão azul ao lado do café",
    "pfv entreguem na {addr} (tocar no 1.º andar)",
    "Olá, pode ser na {addr}? Obrigado!",
    "fds entreguem logo na {addr}!! estou à espera",
    "caralho, é na {addr}, 4º andar, n se enganem",
    "Hi pls deliver to {addr}, 2nd floor",
    "hola, entrega en {addr} por favor",
]


def _maybe_abbreviate_and_lowercase(street: str, rng: random.Random) -> str:
    words = street.split()
    if words and words[0].lower() in ABBREV_MAP and rng.random() < 0.45:
        words[0] = rng.choice(ABBREV_MAP[words[0].lower()])
    text = " ".join(words)
    if rng.random() < 0.4:
        text = text.lower()
    return text


def _deform_word_mild(word: str, rng: random.Random) -> str:
    """Apply a realistic WhatsApp/keyboard/phonetic typo to a word."""
    phonetic_swaps = [
        ("ç", "c"),
        ("ç", "s"),
        ("ss", "s"),
        ("ch", "x"),
        ("qu", "k"),
        ("ão", "ao"),
        ("ã", "a"),
        ("á", "a"),
        ("é", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ú", "u"),
    ]
    lower = word.lower()
    if rng.random() < 0.45:
        for src, dst in phonetic_swaps:
            if src in lower:
                idx = lower.index(src)
                candidate = word[:idx] + dst + word[idx + len(src) :]
                if candidate != word:
                    return candidate

    chars = list(word)
    if len(chars) >= 5 and rng.random() < 0.5:
        pos = rng.randint(1, len(chars) - 2)
        chars[pos], chars[pos + 1] = chars[pos + 1], chars[pos]
        if "".join(chars) != word:
            return "".join(chars)
    pos = rng.randint(1, max(1, len(chars) - 1))
    if len(chars) >= 5 and rng.random() < 0.5:
        del chars[pos]
    else:
        replacement = rng.choice("aeiourstlnmp")
        chars[pos] = replacement if replacement != chars[pos].lower() else "x"
    return "".join(chars)


def _pick_door_number(rng: random.Random) -> int:
    """Door numbers vary (single digit, teens/tens, higher) so results are not tuned to '10'."""
    return rng.choice([rng.randint(1, 9), rng.randint(10, 39), rng.randint(40, 160)])


def _wrap_whatsapp_edge_case(
    street_text: str,
    rng: random.Random,
    number: int | None = 10,
    freguesia: bool | None = None,
) -> tuple[str, bool]:
    """Format street_text with realistic number formats, optional freguesia, and edge-case phrasing.

    number=None omits the door number; freguesia=None picks randomly, True/False forces it.
    """
    street_fmt = _maybe_abbreviate_and_lowercase(street_text, rng)
    include_freguesia = (rng.random() < 0.5) if freguesia is None else freguesia
    if number is None:
        num_fmt = rng.choice([", Corroios", " corroios"]) if include_freguesia else ""
    elif include_freguesia:
        num_fmt = rng.choice([f", {number}, Corroios", f" nº {number}, Corroios", f" n {number} corroios", f", {number} corroios"])
    else:
        num_fmt = rng.choice([f", {number}", f" nº {number}", f" n {number}"])
    addr = f"{street_fmt}{num_fmt}"
    template = rng.choice(WHATSAPP_WRAPPERS)
    return template.format(addr=addr), include_freguesia


def _deform_word_serious(word: str, rng: random.Random) -> str:
    """Heavily distort a word (~45% of characters dropped/replaced/scrambled)."""
    chars = list(word)
    out: list[str] = []
    for idx, ch in enumerate(chars):
        if idx == 0:
            out.append(ch)
            continue
        roll = rng.random()
        if roll < 0.25:
            continue
        if roll < 0.55:
            out.append(rng.choice("xzqkwjvy"))
        else:
            out.append(ch)
    if len(out) < 3:
        out.extend(rng.choice("xzqk") for _ in range(3 - len(out)))
    result = "".join(out)
    return result if result != word else word[:-2] + "xq"


def deform_street(street: str, level: str, rng: random.Random) -> str:
    """Deform a street name mildly ('deformed') or heavily ('seriously_deformed')."""
    words = street.split()
    indices = _distinctive_word_indices(words)
    if not indices:
        indices = [len(words) - 1]

    if level == "deformed":
        target = max(indices, key=lambda i: len(words[i]))
        words[target] = _deform_word_mild(words[target], rng)
        return " ".join(words)

    if level == "seriously_deformed":
        for idx in indices:
            words[idx] = _deform_word_serious(words[idx], rng)
        return " ".join(words)

    raise ValueError(f"Unknown deformation level: {level}")


def build_street_cases(num_streets: int, seed: int | None) -> list[dict[str, Any]]:
    """Sample num_streets random Corroios streets and generate 3 variants each."""
    data = json.loads(STREETS_PATH.read_text(encoding="utf-8"))
    verified_path = STREETS_PATH.parent / "verified_streets.json"
    if not verified_path.exists():
        raise RuntimeError("verified_streets.json missing: run tools/verify_streets.py first")
    verified = json.loads(verified_path.read_text(encoding="utf-8"))["streets"]
    pool = [
        s
        for s in data["streets"]
        if verified.get(s, {}).get("outcome") in {"exact", "unverified_number"}
        and len(_distinctive_word_indices(s.split())) >= 1
    ]
    if len(pool) < num_streets:
        raise RuntimeError(f"Only {len(pool)} eligible streets, requested {num_streets}")

    rng = random.Random(seed)
    chosen = rng.sample(pool, num_streets)
    cases: list[dict[str, Any]] = []

    for idx, street in enumerate(chosen, start=1):
        mild = deform_street(street, "deformed", rng)
        serious = deform_street(street, "seriously_deformed", rng)

        variants = [
            ("original", street, "exact street name must resolve within 50km"),
            (
                "deformed",
                mild,
                "mildly deformed street must ask for confirmation with options containing the right street",
            ),
            (
                "seriously_deformed",
                serious,
                "seriously deformed street must return ADDRESS_NOT_FOUND or options containing the right street",
            ),
        ]

        google_outcome = verified[street]["outcome"]
        door_number = _pick_door_number(rng)
        for variant_kind, street_text, note in variants:
            case_id = f"s{idx:02d}_{variant_kind}"
            wrapped_input, has_freguesia = _wrap_whatsapp_edge_case(street_text, rng, number=door_number)
            cases.append(
                {
                    "id": case_id,
                    "kind": variant_kind,
                    "split": "streets",
                    "street_truth": street,
                    "has_freguesia": has_freguesia,
                    "door_number": door_number,
                    "input": wrapped_input,
                    "notes": f"{note} (truth: {street}, freguesia={'yes' if has_freguesia else 'no'})",
                    "expected_input": {
                        "is_address": True,
                    },
                    "exp_street_rule": variant_kind,
                    "google_outcome": google_outcome,
                }
            )
    return cases


LANDMARKS = [
    ("ao lado do café", ["cafe"]),
    ("em frente à farmácia", ["farmacia"]),
    ("perto do Pingo Doce", ["pingo", "doce"]),
    ("junto à igreja", ["igreja"]),
    ("atrás do ginásio", ["ginasio"]),
    ("ao pé da escola", ["escola"]),
]
POSTAL_TEMPLATES = [
    "{cp}",
    "Boa tarde, o meu código postal é {cp}",
    "entrega no {cp} por favor",
    "CP {cp}, 2.º esq",
    "Hi, deliver to postal code {cp}",
    "hola, entrega en {cp}",
]
POI_TEMPLATES = [
    "Entrega no {poi}",
    "pfv entreguem no {poi}",
    "Olá, é no {poi}. Obrigado!",
    "Hi pls deliver to {poi}",
    "oie td bem? manda pro {poi}",
]
TWO_ADDRESS_TEMPLATES = [
    "Entrega na {a} ou na {b}",
    "Boa tarde! Pode ser na {a} ou então na {b}, qualquer uma serve",
    "Uma encomenda para {a} e outra para {b}",
    "Hi, deliver to {a} or {b}",
    "hola, entrega en {a} o en {b}",
]
SCENARIO_KINDS = ["missing_number", "multiple_matches", "postal_only", "poi", "poi_note", "two_addresses"]


def build_scenario_cases(per_kind: int, seed: int | None) -> list[dict[str, Any]]:
    """Extra scenarios: missing door number, multiple matches, postal-code-only, POIs, landmark notes, two addresses."""
    if per_kind <= 0:
        return []
    verified = json.loads((STREETS_PATH.parent / "verified_streets.json").read_text(encoding="utf-8"))["streets"]
    scen_path = STREETS_PATH.parent / "verified_scenarios.json"
    if not scen_path.exists():
        raise RuntimeError("verified_scenarios.json missing: run tools/verify_scenarios.py first")
    vs = json.loads(scen_path.read_text(encoding="utf-8"))
    data = json.loads(STREETS_PATH.read_text(encoding="utf-8"))
    pool = [
        st
        for st in data["streets"]
        if verified.get(st, {}).get("outcome") in {"exact", "unverified_number"}
        and len(_distinctive_word_indices(st.split())) >= 1
    ]
    postal_pool = [
        (st, m.group(0))
        for st in pool
        if (m := re.search(r"\b\d{4}-\d{3}\b", verified[st].get("formatted_address", "")))
    ]
    ambiguous = [k for k, v in vs["ambiguous_streets"].items() if v.get("outcome") == "multiple"]
    pois = [k for k, v in vs["pois"].items() if v.get("outcome") == "found"]
    rng = random.Random(None if seed is None else seed + 1)

    def cycler(items: list[Any]):
        """Yield every item once in random order before repeating any (small verified pools)."""
        order: list[Any] = []
        while True:
            if not order:
                order = items[:]
                rng.shuffle(order)
            yield order.pop()

    amb_cycle = cycler(ambiguous) if ambiguous else None
    poi_cycle = cycler(pois) if pois else None
    postal_cycle = cycler(postal_pool) if postal_pool else None

    def meta(case_id: str, kind: str, text: str, note: str, truth: str | None, **extra: Any) -> dict[str, Any]:
        return {
            "id": case_id,
            "kind": kind,
            "split": "scenarios",
            "street_truth": truth,
            "input": text,
            "notes": note,
            "expected_input": {"is_address": True},
            "exp_street_rule": kind,
            "google_outcome": None,
            **extra,
        }

    cases: list[dict[str, Any]] = []
    for i in range(1, per_kind + 1):
        # missing door number
        st = rng.choice(pool)
        text, _ = _wrap_whatsapp_edge_case(st, rng, number=None)
        cases.append(meta(f"x{i:02d}_missing_number", "missing_number", text,
                          "no door number given: must ask for it, never accept as resolved", st))
        # multiple matches (street name verified to exist in several places)
        if amb_cycle:
            st = next(amb_cycle)
            n = _pick_door_number(rng)
            text, _ = _wrap_whatsapp_edge_case(st, rng, number=n, freguesia=False)
            cases.append(meta(f"x{i:02d}_multiple_matches", "multiple_matches", text,
                              "street exists in several localities, none stated: list every candidate, never auto-pick",
                              st, door_number=n, scenario={"street": st}))
        # postal code only
        if postal_cycle:
            st, cp = next(postal_cycle)
            text = rng.choice(POSTAL_TEMPLATES).format(cp=cp)
            cases.append(meta(f"x{i:02d}_postal_only", "postal_only", text,
                              "postal code only: cannot be a delivery address, must ask for street and door number",
                              cp, scenario={"postal": cp}))
        # point of interest as destination
        if poi_cycle:
            poi = next(poi_cycle)
            text = rng.choice(POI_TEMPLATES).format(poi=poi)
            cases.append(meta(f"x{i:02d}_poi", "poi", text,
                              "named place as destination: keep the POI in the query, confirm what was found",
                              poi, scenario={"poi": poi}))
        # landmark note next to a real address
        st = rng.choice(pool)
        n = _pick_door_number(rng)
        phrase, tokens = rng.choice(LANDMARKS)
        addr, _ = _wrap_whatsapp_edge_case(st, rng, number=n, freguesia=True)
        text = f"{addr}, {phrase}"
        cases.append(meta(f"x{i:02d}_poi_note", "poi_note", text,
                          "landmark is an access note, must not pollute the Maps query", st,
                          door_number=n, scenario={"landmark_tokens": tokens}))
        # two addresses in one message
        a, b = rng.sample(pool, 2)
        na, nb = _pick_door_number(rng), _pick_door_number(rng)
        text = rng.choice(TWO_ADDRESS_TEMPLATES).format(a=f"{a}, {na}", b=f"{b}, {nb}")
        cases.append(meta(f"x{i:02d}_two_addresses", "two_addresses", text,
                          "two addresses: must not silently pick one, both must be surfaced", a,
                          scenario={"streets": [a, b]}))
    return cases


def prepare_eval(
    mode: str = "streets",
    num_streets: int = 16,
    seed: int | None = None,
    split: str | None = None,
    kinds: list[str] | None = None,
    ids: list[str] | None = None,
    repeat: int = 1,
    eval_id: str | None = None,
    scenarios_total: int = 20,
) -> str:
    """Prepare an isolated eval run and return eval_id."""
    if mode == "golden":
        errors = validate_golden(GOLDEN_PATH)
        if errors:
            raise RuntimeError("Golden validation failed:\n" + "\n".join(errors))
        all_cases: list[dict[str, Any]] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        selected = [
            c
            for c in all_cases
            if (not split or c["split"] == split)
            and (not kinds or c["kind"] in kinds)
            and (not ids or c["id"] in ids)
        ]
    elif mode == "streets":
        selected = build_street_cases(num_streets=num_streets, seed=seed)
        if scenarios_total > 0:
            # `--scenarios` is the total number of scenario cases. Sample evenly
            # across all six scenario kinds, giving the first kinds one extra
            # case when the total is not divisible by six.
            per_kind = (scenarios_total + len(SCENARIO_KINDS) - 1) // len(SCENARIO_KINDS)
            scenario_pool = build_scenario_cases(per_kind=per_kind, seed=seed)
            base, extra = divmod(scenarios_total, len(SCENARIO_KINDS))
            limits = {
                kind: base + (1 if index < extra else 0)
                for index, kind in enumerate(SCENARIO_KINDS)
            }
            counts = {kind: 0 for kind in SCENARIO_KINDS}
            for case in scenario_pool:
                kind = case["kind"]
                if counts[kind] < limits[kind]:
                    selected.append(case)
                    counts[kind] += 1
        if kinds:
            selected = [c for c in selected if c["kind"] in kinds]
        if ids:
            selected = [c for c in selected if c["id"] in ids]
    else:
        raise ValueError(f"Unsupported mode: {mode}")

    if not selected:
        raise RuntimeError("No cases matched the requested filters.")

    eid = eval_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    eval_dir = RESULTS_ROOT / eid
    eval_dir.mkdir(parents=True, exist_ok=False)

    manifest_cases: list[dict[str, Any]] = []
    for case in selected:
        for rep in range(1, repeat + 1):
            case_dir_name = case["id"] if repeat == 1 else f"{case['id']}-r{rep}"
            case_dir = eval_dir / "cases" / case_dir_name
            case_dir.mkdir(parents=True, exist_ok=True)
            out_dir_rel = f"output/evals/{eid}/cases/{case_dir_name}"
            tmp_case_dir = TEMP_EVALS_ROOT / eid / case_dir_name
            tmp_case_dir.mkdir(parents=True, exist_ok=True)
            maps_path = str(tmp_case_dir / "maps_raw_output.json")
            case_dir.mkdir(parents=True, exist_ok=True)
            (tmp_case_dir / "prompt.md").write_text(
                make_blind_prompt(out_dir_rel, maps_path, case["input"]) + "\n", encoding="utf-8"
            )
            manifest_cases.append(
                {
                    "dir": case_dir_name,
                    "case_id": case["id"],
                    "repeat": rep,
                    "kind": case["kind"],
                    "split": case["split"],
                    "street_truth": case.get("street_truth"),
                    "door_number": case.get("door_number"),
                    "scenario": case.get("scenario"),
                    "input": case["input"],
                    "notes": case["notes"],
                    "expected_input": case["expected_input"],
                    "expected_orientation": case.get("expected_orientation"),
                    "exp_street_rule": case.get("exp_street_rule"),
                    "google_outcome": case.get("google_outcome"),
                    "exp_message_must_contain": case.get("exp_message_must_contain", []),
                    "exp_message_must_not": case.get("exp_message_must_not", []),
                }
            )

    eval_meta = {
        "eval_id": eid,
        "mode": mode,
        "seed": seed,
        "num_streets": num_streets if mode == "streets" else None,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repeat": repeat,
        "filters": {"split": split, "kinds": kinds, "ids": ids},
        "total_runs": len(manifest_cases),
        "cases": manifest_cases,
    }
    tmp_eval_dir = TEMP_EVALS_ROOT / eid
    tmp_eval_dir.mkdir(parents=True, exist_ok=True)
    (tmp_eval_dir / "eval.json").write_text(
        json.dumps(eval_meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_eval_dir / "status.json").write_text(
        json.dumps({"eval_id": eid, "state": "prepared"}, indent=2), encoding="utf-8"
    )
    return eid


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an isolated eval run.")
    parser.add_argument("--mode", choices=["streets", "golden"], default="streets")
    parser.add_argument("--streets", type=int, default=10, help="Random streets to sample in streets mode")
    parser.add_argument("--seed", type=int, default=None, help="Optional RNG seed for street sampling")
    parser.add_argument("--split", choices=["dev", "test"], default=None)
    parser.add_argument("--kind", default=None, help="Comma-separated kinds")
    parser.add_argument("--ids", default=None, help="Comma-separated case IDs")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--eval-id", default=None)
    parser.add_argument("--scenarios", type=int, default=20, help="Total scenario cases, sampled evenly across kinds (0 disables)")
    args = parser.parse_args()

    kinds = [k.strip() for k in args.kind.split(",") if k.strip()] if args.kind else None
    ids = [i.strip() for i in args.ids.split(",") if i.strip()] if args.ids else None
    try:
        eid = prepare_eval(
            mode=args.mode,
            num_streets=args.streets,
            seed=args.seed,
            split=args.split,
            kinds=kinds,
            ids=ids,
            repeat=args.repeat,
            eval_id=args.eval_id,
            scenarios_total=args.scenarios,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(eid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
