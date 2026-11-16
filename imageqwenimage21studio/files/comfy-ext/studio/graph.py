"""Pick a flow for a job and turn the flow's API workflow into a prompt.

Pure functions over plain dicts (studio.json flows, API workflows, asset
records), so they run and are tested without ComfyUI.
"""
import copy
import math
import random
import re

# mask: white where an edit may change the first ref_image.
ASSET_ROLES = ("first_frame", "last_frame", "ref_image", "ref_video", "ref_audio", "mask")
ROLE_KIND = {"first_frame": "image", "last_frame": "image", "ref_image": "image", "ref_video": "video", "ref_audio": "audio",
             "mask": "image"}
SPEEDS = ("quality", "fast")
# aspect "follow": the output keeps image 1's shape (the parameter bar's
# "follow image 1").
FOLLOW = "follow"
TOKEN = re.compile(r"\{\{([A-Za-z0-9_-]{1,64})\}\}")
CJK = re.compile(u"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
MAX_SEED = 2 ** 50


class JobError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra

    def as_dict(self):
        return {"code": self.code, "message": self.message, **self.extra}


def check_route(flow, items):
    """None when the flow takes these assets, else why not.

    items: [{"role", "kind", "duration"}]."""
    route = flow.get("route") or {}
    accepts = route.get("accepts") or {}
    counts, seconds = {}, {}
    for it in items:
        role = it["role"]
        lim = accepts.get(role)
        if not lim:
            return {"code": "role_not_accepted", "role": role}
        if ROLE_KIND.get(role) != it.get("kind"):
            return {"code": "wrong_kind", "role": role, "kind": it.get("kind")}
        counts[role] = counts.get(role, 0) + 1
        if counts[role] > lim["max"]:
            return {"code": "too_many", "role": role, "max": lim["max"]}
        d = it.get("duration")
        if d is not None:
            if lim.get("minSeconds") and d < lim["minSeconds"] - 0.05:
                return {"code": "too_short", "role": role, "min": lim["minSeconds"]}
            if lim.get("maxSeconds") and d > lim["maxSeconds"] + 0.05:
                return {"code": "too_long", "role": role, "max": lim["maxSeconds"]}
            seconds[role] = seconds.get(role, 0) + d
            if lim.get("totalSeconds") and seconds[role] > lim["totalSeconds"] + 0.05:
                return {"code": "total_too_long", "role": role, "max": lim["totalSeconds"]}
    if route.get("maxTotal") and len(items) > route["maxTotal"]:
        return {"code": "too_many_total", "max": route["maxTotal"]}
    need = route.get("requiresAny") or []
    if need and not any(it["role"] in need for it in items):
        return {"code": "requires_any", "roles": need}
    return None


def aspect_route(aspect, items, defaults=None):
    """Which route.aspect a job with images takes: follow (keep image 1's
    shape) or ratio (a picked aspect ratio). A mask always follows; no
    pick ("auto") takes defaults[single|multi], else follow. None without
    images.

    Mirrored by aspectRoute in web/src/plan.ts; both run
    testdata/aspect_route.json."""
    n = sum(1 for it in items or () if it.get("role") == "ref_image")
    if not n:
        return None
    if any(it.get("role") == "mask" for it in items) or aspect == FOLLOW:
        return FOLLOW
    if aspect not in (None, "", "auto"):
        return "ratio"
    return (defaults or {}).get("multi" if n > 1 else "single") or FOLLOW


def pick_flow(flows, items, mode="auto", speed=None, aspect=None):
    """The flow for these assets: the asked mode, or the first that fits,
    flows made for the asked speed first. Flows with a speed are only taken
    for that speed; flows with a route.aspect only for that aspect_route."""
    speed_of = lambda f: (f.get("route") or {}).get("speed") or ""
    fits = lambda f: not aspect or (f.get("route") or {}).get("aspect") in (None, "", aspect)
    order = [f for f in flows if speed and speed_of(f) == speed and fits(f)] + [f for f in flows if not speed_of(f) and fits(f)]
    if mode and mode != "auto":
        for f in flows:
            if f["mode"] == mode:
                why = check_route(f, items)
                if why:
                    raise JobError("flow_rejects_assets", "This mode cannot take these assets", mode=mode, reason=why)
                return f
        raise JobError("unknown_mode", "Unknown mode", mode=mode)
    reasons = {}
    for f in order:
        why = check_route(f, items)
        if why is None:
            return f
        reasons[f["mode"]] = why
    raise JobError("no_flow", "No mode takes this combination of assets", reasons=reasons)


def _tokens(items, tokens):
    """Asset id -> tokens[role] with {n} its number within its role in tray order."""
    out, n = {}, {}
    for it in items:
        tok = (tokens or {}).get(it["role"])
        if tok and it["id"] not in out:
            n[it["role"]] = n.get(it["role"], 0) + 1
            out[it["id"]] = tok.replace("{n}", str(n[it["role"]]))
    return out


def render_prompt(text, items, names, tokens=None):
    """Turn {{asset-id}} chips into the model's syntax (profile.tokens),
    else the asset's name."""
    tags = _tokens(items, tokens)

    def sub(m):
        aid = m.group(1)
        return tags.get(aid) or names.get(aid, "")

    return TOKEN.sub(sub, text or "")


def ref_note(items, profile, prompt):
    """The phrases of the images marked with a refTag, in the prompt's
    language (Chinese when it has CJK text, else English), as one sentence."""
    phrases = {t["id"]: t.get("phrase") or {} for t in (profile or {}).get("refTags") or []}
    toks = _tokens(items, (profile or {}).get("tokens"))
    lang = "zh" if CJK.search(prompt or "") else "en"
    parts = [phrases[it["tag"]][lang].replace("{ref}", toks[it["id"]])
             for it in items if it.get("tag") in phrases and it["id"] in toks and phrases[it["tag"]].get(lang)]
    if not parts:
        return ""
    return "；".join(parts) + "。" if lang == "zh" else "; ".join(parts) + "."


def _refs(value):
    return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and isinstance(value[1], int)


def _sinks(g):
    used = {v[0] for node in g.values() for v in node.get("inputs", {}).values() if _refs(v)}
    return [nid for nid in g if nid not in used]


def _prune(g, sinks):
    keep, todo = set(), [s for s in sinks if s in g]
    while todo:
        nid = todo.pop()
        if nid in keep:
            continue
        keep.add(nid)
        for v in g[nid].get("inputs", {}).values():
            if _refs(v) and v[0] in g:
                todo.append(v[0])
    return {k: v for k, v in g.items() if k in keep}


def _cut_links_from(g, src):
    for node in g.values():
        ins = node.get("inputs", {})
        for k in [k for k, v in ins.items() if _refs(v) and v[0] == src]:
            del ins[k]


def _bypass(g, nid, field):
    """Skip node nid: whatever read its output reads its input field."""
    node = g.get(nid)
    if node is None:
        raise JobError("bad_flow", "The workflow has no node %s" % nid)
    src = node.get("inputs", {}).get(field)
    if not _refs(src):
        raise JobError("bad_flow", "Node %s has no link at %s" % (nid, field))
    for other in g.values():
        ins = other.get("inputs", {})
        for k, v in list(ins.items()):
            if _refs(v) and v[0] == nid:
                ins[k] = list(src)
    del g[nid]


def _set(g, node, field, value):
    if node not in g:
        raise JobError("bad_flow", "The workflow has no node %s" % node)
    g[node].setdefault("inputs", {})[field] = value


def tiers(profile):
    """Megapixels per resolution tier id, in display order."""
    return {t["id"]: t["megapixels"] for t in (profile or {}).get("tiers") or []}


def _in_unit(mp, inp):
    """Megapixels as the input takes them: unit edge is the side of a
    square of that many megapixels (1 MP = 1024²)."""
    if inp.get("unit") == "edge":
        return int(round(math.sqrt(mp) * 1024 / 32)) * 32
    return mp


def default_tier(inp, profile):
    """The tier of a resolution input's default, else the first."""
    mp = tiers(profile)
    d = inp.get("default")
    for k, v in mp.items():
        if d is not None and abs(_in_unit(v, inp) - float(d)) < 1e-6:
            return k
    return next(iter(mp), None)


def flow_roles(flow, profile=None):
    """The flow's parameter inputs by role, as /health sends them."""
    roles = {}
    for i in flow.get("inputs", []):
        if i.get("role"):
            roles[i["role"]] = {k: i.get(k) for k in ("min", "max", "step", "default", "options", "optional") if i.get(k) is not None}
            if i["role"] == "resolution":
                roles["resolution"]["default"] = default_tier(i, profile)
    return roles


SIZE_ROLES = ("first_frame", "ref_image", "ref_video")


def aspect_value(label):
    try:
        a, b = str(label).split(" ")[0].split(":")
        return float(a) / float(b)
    except (ValueError, ZeroDivisionError):
        return None


def nearest_aspect(options, width, height):
    r = math.log(width / height)
    scored = [(abs(math.log(v) - r), o) for o in options for v in [aspect_value(o)] if v]
    return min(scored, key=lambda x: x[0])[1] if scored else None


def first_size(items):
    for role in SIZE_ROLES:
        for it in items or ():
            a = it.get("asset") or it
            if it.get("role") == role and a.get("width") and a.get("height"):
                return a["width"], a["height"]
    return None


def resolve_roles(roles, params, items=(), tier_ids=()):
    """Final aspect, duration and resolution with where each came from
    ("user", "image" or "default"). An unknown aspect or resolution falls
    back like an unset one; duration is clamped to the input's range. The
    prompt text is never read for size, aspect or length.

    Mirrored by resolveParams in web/src/plan.ts; both run
    testdata/resolve_params.json."""
    out, src = dict(params), {}
    out.pop("aspect", None)
    r = roles.get("aspect")
    if r:
        opts = r.get("options") or []
        a = params.get("aspect")
        pick = next((o for o in opts if a not in (None, "", "auto") and (o == a or o.split(" ")[0] == a)), None)
        size = first_size(items)
        if pick:
            out["aspect"], src["aspect"] = pick, "user"
        elif size and nearest_aspect(opts, *size):
            out["aspect"], src["aspect"] = nearest_aspect(opts, *size), "image"
        elif r.get("default"):
            out["aspect"], src["aspect"] = r["default"], "default"
    d = roles.get("duration")
    if d:
        v = params.get("duration")
        src["duration"] = "default" if v in (None, "") else "user"
        v = d.get("default") if v in (None, "") else v
        if v is not None:
            v = float(v)
            if d.get("min") is not None:
                v = max(float(d["min"]), v)
            if d.get("max") is not None:
                v = min(float(d["max"]), v)
            out["duration"] = v
    res = roles.get("resolution")
    if res:
        v = params.get("resolution")
        if v in tier_ids:
            out["resolution"], src["resolution"] = v, "user"
        elif res.get("default") or tier_ids:
            out["resolution"], src["resolution"] = res.get("default") or tier_ids[0], "default"
    return out, src


def resolve_params(flow, params, items=(), profile=None):
    return resolve_roles(flow_roles(flow, profile), params, items, list(tiers(profile)))


def assemble(flow, api, job_id, items, params, replace=None, file_of=None, names=None, profile=None):
    """The prompt for one job.

    items: the job's assets in tray order, [{"id", "role", "kind",
    "has_audio", "tag"}], the first ref_image the one an edit changes; file_of(item)
    is the name a loader node takes;
    params: prompt, duration, aspect, resolution, seed, steps;
    profile: studio.json's profile (tiers, tokens)."""
    file_of = file_of or (lambda it: it["file"])
    profile = profile or {}
    params, sources = resolve_params(flow, params, items, profile)
    g = copy.deepcopy(api)
    sinks = _sinks(g)
    if replace:
        for node in g.values():
            ins = node.get("inputs", {})
            for k, v in ins.items():
                if isinstance(v, str) and v in replace:
                    ins[k] = replace[v]

    by_role = {}
    for it in items:
        by_role.setdefault(it["role"], []).append(it)
    grown = {ag["role"] for ag in flow.get("autogrow") or []}

    seed = params.get("seed")
    if seed is None or seed == "":
        seed = random.randrange(MAX_SEED)
    seed = int(seed)
    used = {"seed": seed}

    for inp in flow.get("inputs", []):
        role = inp.get("role")
        if not role:
            continue
        targets = [(inp["node"], inp["field"])] + [(t["node"], t["field"]) for t in inp.get("also") or []]
        value = None
        if role in ASSET_ROLES and role not in grown:
            got = by_role.get(role) or []
            if got:
                value = file_of(got[0])
            elif inp.get("optional"):
                _cut_links_from(g, inp["node"])
                if inp.get("bypass"):
                    _bypass(g, inp["bypass"]["node"], inp["bypass"]["field"])
                continue
            else:
                raise JobError("missing_asset", "This mode needs a %s" % role.replace("_", " "), role=role)
        elif role == "prompt":
            value = render_prompt(params.get("prompt", ""), items, names or {}, profile.get("tokens"))
            if not value.strip():
                raise JobError("empty_prompt", "Write a prompt first")
            note = ref_note(items, profile, value)
            if note:
                used["refNote"] = note
                value = note + "\n" + value
        elif role == "duration":
            if params.get("duration") is None:
                continue
            value = used["duration"] = params["duration"]
        elif role == "aspect":
            if not params.get("aspect"):
                continue
            value = used["aspect"] = params["aspect"]
            if sources.get("aspect") != "user":
                used["aspectAuto"] = True
        elif role == "resolution":
            if not params.get("resolution"):
                continue
            value = _in_unit(tiers(profile)[params["resolution"]], inp)
            used["resolution"] = params["resolution"]
        elif role == "seed":
            value = seed
        elif role == "steps":
            s = params.get("steps")
            if not s:
                continue
            value = int(s)
            used["steps"] = value
        else:
            continue
        for node, field in targets:
            _set(g, node, field, value)

    for ag in flow.get("autogrow") or []:
        target = g.get(ag["node"])
        if target is None:
            raise JobError("bad_flow", "The workflow has no node %s" % ag["node"])
        ins = target.setdefault("inputs", {})
        prefixes = [l["prefix"] for l in ag["links"]]
        for k in [k for k in ins if any(k.startswith(p) for p in prefixes)]:
            del ins[k]
        start = ag.get("start") or 0
        first, clones = None, set()
        for i, it in enumerate(by_role.get(ag["role"]) or []):
            ids = {t: "%s_%s%d" % (t, ag["role"], i) for t in ag["template"]}
            clones.update(ids.values())
            for t in ag["template"]:
                if t not in g:
                    raise JobError("bad_flow", "The workflow has no node %s" % t)
                node = copy.deepcopy(g[t])
                for k, v in node.get("inputs", {}).items():
                    if _refs(v) and v[0] in ids:
                        node["inputs"][k] = [ids[v[0]], v[1]]
                g[ids[t]] = node
            g[ids[ag["file"]["node"]]]["inputs"][ag["file"]["field"]] = file_of(it)
            for l in ag["links"]:
                if l.get("when") == "has_audio" and not it.get("has_audio"):
                    continue
                ins["%s%d" % (l["prefix"], start + i)] = [ids[l["from"]], l["output"]]
            first = first or ids
        if first:
            # Nodes outside the autogrow that read a template node read the
            # first asset's copy (the edit's base image).
            for nid, node in g.items():
                if nid in clones:
                    continue
                for k, v in node.get("inputs", {}).items():
                    if _refs(v) and v[0] in first:
                        node["inputs"][k] = [first[v[0]], v[1]]

    for nid in sinks:
        ins = g.get(nid, {}).get("inputs", {})
        if "filename_prefix" in ins:
            ins["filename_prefix"] = "studio/%s" % job_id
    return _prune(g, sinks), used
