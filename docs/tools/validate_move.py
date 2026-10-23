"""Cross-checks one move's generated files before it goes in-game.

  python3 docs/tools/validate_move.py flareblitz

Checks, for src/main/resources:
- every particle in bedrock/particles/moves/<move>/: identifier matches the file name, the texture
  exists (ours or Cobblemon's), numeric uv / flipbook rectangles stay inside the sheet (max_frame is a
  frame COUNT), tint colours are "#AARRGGBB", every v.* it reads is declared somewhere (curve, script,
  Cobblemon's entity variables or a Bedrock built-in);
- the move's generic animation file: every particle effect and sound event it fires exists;
- the action effect: every animation it plays exists;
- every MoLang string in all of them parses with Cobblemon's own parser (MoCheck.java, run against the
  Cobblemon jar from the Gradle cache).
Exit status 1 if anything is wrong.
"""
import glob, json, os, re, struct, subprocess, sys, tempfile, zipfile

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
RES = os.path.join(ROOT, 'src/main/resources')
GRADLE = os.path.expanduser('~/.gradle/caches/modules-2/files-2.1')

BUILTIN_VARS = {'particle_age', 'particle_lifetime', 'emitter_age', 'emitter_lifetime',
                'particle_random_1', 'particle_random_2', 'particle_random_3', 'particle_random_4',
                'emitter_random_1', 'emitter_random_2', 'emitter_random_3', 'emitter_random_4',
                # set by Cobblemon's ParticleStorm.spawn() for entity particles
                'entity_width', 'entity_height', 'entity_size', 'entity_radius', 'entity_scale',
                'target_deltax', 'target_deltay', 'target_deltaz', 'target_distance'}
NOT_EXPR_KEYS = {'identifier', 'material', 'texture', 'facing_camera_mode', 'type', 'effect', 'event_name',
                 'format_version', 'locator', 'plane_normal', 'lerp_mode'}
WORDS = {'outwards', 'inwards', 'y', 'x', 'z', 'linear', 'catmullrom', 'bezier', 'bezier_chain'}

problems = []


def bad(msg):
    problems.append(msg)


def find_jar(name):
    hits = [p for p in glob.glob(os.path.join(GRADLE, '**', name), recursive=True) if 'sources' not in p]
    return hits[0] if hits else None


COB_JAR = find_jar('fabric-1.7.3+1.21.1.jar')
GSON_JAR = find_jar('gson-2.10.1.jar')
jar = zipfile.ZipFile(COB_JAR)
JAR_NAMES = set(jar.namelist())


def png_size(data):
    return struct.unpack('>II', data[16:24])


def texture_size(path):
    """'textures/particles/x/y' -> (w, h) from our resources or the Cobblemon jar (stored as textures/particle/)."""
    rel = 'assets/cobblemon/' + path.replace('textures/particles/', 'textures/particle/', 1) + '.png'
    ours = os.path.join(RES, rel)
    if os.path.exists(ours):
        with open(ours, 'rb') as f:
            return png_size(f.read(24))
    if rel in JAR_NAMES:
        return png_size(jar.read(rel)[:24])
    return None


def strings(node, key=None, out=None):
    """All MoLang strings in a particle JSON (skips names, paths, enums and colours)."""
    if out is None:
        out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k in NOT_EXPR_KEYS or k == 'events' or k == 'gradient':
                continue
            strings(v, k, out)
    elif isinstance(node, list):
        for v in node:
            strings(v, key, out)
    elif isinstance(node, str):
        if not (node.startswith('#') or node in WORDS):
            out.append(node)
    return out


VAR_RE = re.compile(r'\b(?:v|variable)\.([a-z_][a-z0-9_]*)', re.I)
ASSIGN_RE = re.compile(r'\b(?:v|variable)\.([a-z_][a-z0-9_]*)\s*=(?!=)', re.I)


def check_particles(move):
    ids = {}
    exprs = []
    pdir = os.path.join(RES, f'assets/cobblemon/bedrock/particles/moves/{move}')
    files = sorted(glob.glob(os.path.join(pdir, '*.particle.json')))
    if not files:
        bad(f'no particles in {pdir}')
    for path in files:
        name = os.path.basename(path)[:-len('.particle.json')]
        d = json.load(open(path))
        pe = d['particle_effect']
        pid = pe['description']['identifier']
        ids[pid] = path
        if pid != f'cobblemon:{name}':
            bad(f'{name}: identifier {pid} does not match the file name')
        tex_path = pe['description']['basic_render_parameters']['texture']
        size = texture_size(tex_path)
        comps = pe['components']
        bb = comps.get('minecraft:particle_appearance_billboard', {})
        uv = bb.get('uv', {})
        if size is None:
            bad(f'{name}: texture {tex_path} not found')
        else:
            tw, th = uv.get('texture_width'), uv.get('texture_height')
            if (tw, th) != tuple(size):
                bad(f'{name}: texture_width/height {tw}x{th} but {tex_path} is {size[0]}x{size[1]}')
            fb = uv.get('flipbook')
            if fb:
                vals = [fb.get('base_UV'), fb.get('size_UV'), fb.get('step_UV'), fb.get('max_frame')]
                if all(isinstance(c, (int, float)) for v in vals[:3] for c in v) and isinstance(vals[3], (int, float)):
                    (bu, bv), (su, sv), (stu, stv), n = vals
                    eu, ev = bu + (n - 1) * stu + su, bv + (n - 1) * stv + sv
                    if eu > tw or ev > th or bu < 0 or bv < 0:
                        bad(f'{name}: flipbook runs off the sheet (last frame ends at {eu},{ev} of {tw}x{th})')
            elif isinstance(uv.get('uv'), list) and all(isinstance(c, (int, float)) for c in uv['uv'] + uv['uv_size']):
                if uv['uv'][0] + uv['uv_size'][0] > tw or uv['uv'][1] + uv['uv_size'][1] > th:
                    bad(f'{name}: uv rectangle outside the sheet')
        tint = comps.get('minecraft:particle_appearance_tinting', {}).get('color')
        if isinstance(tint, dict):
            for c in tint['gradient'].values():
                if not re.fullmatch(r'#[0-9A-Fa-f]{8}', c):
                    bad(f'{name}: tint colour {c!r} is not #AARRGGBB')
        # variables
        ex = strings(pe)
        exprs += ex
        declared = set(BUILTIN_VARS) | {'du', 'miss'}   # du/miss come from the dash animation's pre_effect_script
        for k in pe.get('curves', {}):
            declared.add(k.split('.', 1)[1])
        for s in ex:
            declared |= set(m.lower() for m in ASSIGN_RE.findall(s))
        for s in ex:
            for v in VAR_RE.findall(s):
                if v.lower() not in declared:
                    bad(f'{name}: reads undeclared v.{v}')
        # events must point at existing effects
        for ev in pe.get('events', {}).values():
            eff = ev.get('particle_effect', {}).get('effect')
            if eff and eff not in ids and not os.path.exists(os.path.join(pdir, eff.split(':')[1] + '.particle.json')):
                bad(f'{name}: event spawns unknown effect {eff}')
    return ids, exprs


def official_particle_ids():
    out = set()
    for n in JAR_NAMES:
        if n.startswith('assets/cobblemon/bedrock/particles/') and n.endswith('.json'):
            try:
                out.add(json.loads(jar.read(n))['particle_effect']['description']['identifier'])
            except Exception:
                pass
    for p in glob.glob(os.path.join(RES, 'assets/cobblemon/bedrock/particles/**/*.particle.json'), recursive=True):
        out.add(json.load(open(p))['particle_effect']['description']['identifier'])
    return out


def sound_events():
    ours = set(json.load(open(os.path.join(RES, 'assets/cobblemon/sounds.json'))))
    official = set(json.loads(jar.read('assets/cobblemon/sounds.json')))
    return ours | official


def check_animation(move, all_ids, events):
    path = os.path.join(RES, f'assets/cobblemon/bedrock/generic/animations/moves/{move}.animation.json')
    anims = json.load(open(path))['animations']
    exprs = []
    for an, a in anims.items():
        length = a.get('animation_length', 0)
        for tkey, eff in a.get('particle_effects', {}).items():
            if float(tkey) > length + 1e-6:
                bad(f'{an}: particle effect at {tkey} after the end ({length})')
            for e in (eff if isinstance(eff, list) else [eff]):
                if e['effect'] not in all_ids:
                    bad(f'{an}: unknown particle effect {e["effect"]}')
                if 'pre_effect_script' in e:
                    exprs += [ln for ln in e['pre_effect_script'].split('\n') if ln.strip()]
        for tkey, snd in a.get('sound_effects', {}).items():
            for s in (snd if isinstance(snd, list) else [snd]):
                if s['effect'] not in events:
                    bad(f'{an}: unknown sound event {s["effect"]}')
        for bone, chans in a.get('bones', {}).items():
            for ch, keys in chans.items():
                for tkey in keys:
                    if float(tkey) > length + 1e-6:
                        bad(f'{an}: {bone}.{ch} key at {tkey} after the end ({length})')
    return anims, exprs


def check_effect(move, anims):
    path = os.path.join(RES, f'data/cobblemon/action_effects/moves/{move}.json')
    tl = json.load(open(path))['timeline']
    exprs = []

    def walk(kfs):
        for kf in kfs:
            if isinstance(kf, str):
                continue
            for key in ('condition', 'entityCondition'):
                if key in kf:
                    exprs.append(kf[key])
            for e in kf.get('expressions', []) if isinstance(kf.get('expressions'), list) else (
                    [kf['expressions']] if 'expressions' in kf else []):
                exprs.append(e)
                for grp, nm in re.findall(r"q\.bedrock_stateful\('([^']+)', '([^']+)'", e):
                    if f'animation.{grp}.{nm}' not in anims:
                        bad(f'action effect plays missing animation.{grp}.{nm}')
            walk(kf.get('keyframes', []))
    walk(tl)
    return exprs


def molang_check(exprs):
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(['javac', '-d', tmp, '-cp', COB_JAR, os.path.join(here, 'MoCheck.java')], check=True)
        lst = os.path.join(tmp, 'exprs.txt')
        with open(lst, 'w') as f:
            f.write('\n'.join(e.replace('\n', ' ') for e in exprs))
        out = subprocess.run(['java', '-cp', f'{COB_JAR}:{GSON_JAR}:{tmp}', 'MoCheck', lst],
                             capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith('LINE'):
            bad('MoLang: ' + line)
    print(out.strip().splitlines()[-1] if out.strip() else 'MoCheck printed nothing')


if __name__ == '__main__':
    move = sys.argv[1]
    ids, pexprs = check_particles(move)
    all_ids = official_particle_ids()
    anims, aexprs = check_animation(move, all_ids, sound_events())
    eexprs = check_effect(move, anims)
    print(f'{len(ids)} particles, {len(anims)} animations')
    molang_check(sorted(set(pexprs + aexprs + eexprs)))
    for p in problems:
        print('PROBLEM:', p)
    print(f'{len(problems)} problem(s)')
    sys.exit(1 if problems else 0)
