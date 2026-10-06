"""Generates Darkest Lariat's generic animation file and action effect.

Outputs (paths relative to the repo root):
  src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/darkestlariat.animation.json
  src/main/resources/data/cobblemon/action_effects/moves/darkestlariat.json

Edit the constants below and re-run `python3 docs/tools/darkestlariat_gen.py`; don't hand-edit
the two outputs (the 15 dash variants and the arm numbers would drift apart).
Particle files are hand-written JSON in bedrock/particles/moves/darkestlariat/.
Design notes and the reasoning behind every number: docs/darkestlariat_assets.md.
"""
import json, os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
ANIM_OUT = os.path.join(ROOT, 'src/main/resources/assets/cobblemon/bedrock/generic/animations/moves/darkestlariat.animation.json')
EFFECT_OUT = os.path.join(ROOT, 'src/main/resources/data/cobblemon/action_effects/moves/darkestlariat.json')

# ---------------------------------------------------------------- timing (seconds of animation time)
ANIM_LENGTH = 1.45
HOLD_START, SPIN_START = 0.34, 0.50   # T-pose beat: spin angle held at exactly 0 (fist orbs fire in here)
IMPACT, HITSTOP_END = 0.80, 0.90      # dash arrives + spin freezes at SPIN_IMPACT for a hit-stop
RETURN_START, RETURN_END = 1.00, 1.32
SPIN_IMPACT = 630                     # 1.75 turns; ends with one arm pointing straight at the target
SPIN_END = 1080                       # 3 full turns, so dropping the animation causes no pop

# ---------------------------------------------------------------- arms
# Additive "spread both arms" deltas, mirrored left/right. Fitted with forward kinematics against
# the battle idle of all 15 learners that have models in Cobblemon 1.7.3 (docs/darkestlariat_assets.md).
# Bones a model doesn't have are skipped by Cobblemon, so this is safe on any Pokémon.
ARM_DELTAS = {
    'arm_left':        [-22, -35, -32],
    'arm_left1':       [-22, -35, -32],
    'arm_right':       [-22,  35,  32],
    'arm_right1':      [-22,  35,  32],
    'arm_left2':       [-17,   0,   3],
    'arm_right2':      [-17,   0,  -3],
    # shoulder_*1 only exists on Incineroar; its idle is asymmetric, so each side has its own fit
    'shoulder_left1':  [-19, -11,  -8],
    'shoulder_right1': [ -7,  75,   7],
}
# fraction of ARM_DELTAS over time: cock during the crouch, fling out, hold through the spin, relax
ARM_CURVE = [(0.0, 0), (0.12, 0.15), (0.2, 0.3), (0.3, 0.95), (0.34, 1.08), (0.42, 1.0),
             (0.6, 1.08), (0.8, 1.08), (0.9, 1.0), (1.02, 0.85), (1.2, 0.45), (1.38, 0), (ANIM_LENGTH, 0)]

# ---------------------------------------------------------------- dash
# The server measures the real gap to the target (v.dl_units, in the user's model units) and picks
# the nearest dash variant, so the spinning Pokémon actually reaches the target at any distance.
DASH_STEP = 16          # model units between variants (1 block at scale 1)
DASH_VARIANTS = 15      # dash_1 .. dash_15 (16..240 units); 0 = target already in reach, no dash
DASH_FALLBACK = 3       # used when there's no target entity (expression yields -1)
REACH_FACTOR = 0.53     # user stops with its centre this many max(width,height) from the target's edge
DISTANCE_EXPR = (
    "v.dl_units = (q.target.width > 0) ? math.clamp((q.user.distance_to_pos(q.target.x, q.target.y, q.target.z)"
    f" - 0.5 * q.target.width - {REACH_FACTOR} * math.max(q.user.width, q.user.height))"
    f" * 16 / math.max(q.user.species.base_scale, 0.1), 0, {DASH_STEP * DASH_VARIANTS}) : -1"
)

TARGET_COND = "q.entity.is_user == false && q.missed(q.entity.uuid) == false"


def t(x):
    """Keyframe time key: shortest exact decimal string."""
    s = f"{x:.4f}".rstrip('0').rstrip('.')
    return s if '.' in s else s + '.0'


def vec(v):
    return [round(c, 3) + 0 for c in v]


def actor_animation():
    rot = {
        0.0: [0, 0, 0], 0.1: [5, -26, 0], 0.2: [7, -40, 0], 0.28: [2, -22, 0],
        HOLD_START: [-4, 0, 0], 0.42: [-2, 0, 0], SPIN_START: [0, 0, 0],
        0.65: [4, SPIN_IMPACT / 2, 0], IMPACT: [3, SPIN_IMPACT, 0], 0.84: [6, SPIN_IMPACT, 0],
        HITSTOP_END: [2, SPIN_IMPACT, 0], 1.02: [0, 830, 0], 1.14: [0, 980, 0], 1.26: [0, SPIN_END, 0],
        ANIM_LENGTH: [0, SPIN_END, 0],
    }
    pos = {
        0.0: [0, 0, 0], 0.1: [0, -1.4, 0], 0.2: [0, -2.2, 0], HOLD_START: [0, 0.8, 0], 0.42: [0, 0.3, 0],
        SPIN_START: [0, 0, 0], 0.65: [0, 0.8, 0], IMPACT: [0, 0.4, 0], 0.84: [0, -1.0, 0],
        HITSTOP_END: [0, 0, 0], 1.16: [0, 0.6, 0], 1.32: [0, -0.6, 0], ANIM_LENGTH: [0, 0, 0],
    }
    scale = {
        0.0: [1, 1, 1], 0.18: [1.05, 0.93, 1.05], 0.3: [0.97, 1.04, 0.97], 0.42: [1, 1, 1],
        0.82: [1, 1, 1], 0.85: [1.05, 0.95, 1.05], 0.92: [1, 1, 1], 1.3: [1, 1, 1],
        1.34: [1.04, 0.95, 1.04], 1.42: [1, 1, 1],
    }
    bones = {'root_part': {
        'rotation': {t(k): vec(v) for k, v in sorted(rot.items())},
        'position': {t(k): vec(v) for k, v in sorted(pos.items())},
        'scale': {t(k): vec(v) for k, v in sorted(scale.items())},
    }}
    for bone, d in ARM_DELTAS.items():
        bones[bone] = {'rotation': {t(k): vec([c * f for c in d]) for k, f in ARM_CURVE}}

    def fist_beat(flare):
        # one emitter per fist (v.side = -1 / +1), so each fist gets exactly one orb, hoop and flare
        beat = []
        for side in (-1, 1):
            script = f"v.flare = {flare}\nv.side = {side}"
            for effect in ('fistorb', 'fisthoop', 'fiststar'):
                beat.append({'effect': f'cobblemon:darkestlariat_{effect}', 'locator': 'root', 'pre_effect_script': script})
        beat.append({'effect': 'cobblemon:darkestlariat_stancering', 'locator': 'root', 'pre_effect_script': f"v.flare = {flare}"})
        return beat
    return {
        'animation_length': ANIM_LENGTH,
        'bones': bones,
        # Both beats fire while the spin angle is frozen, so the emitter's captured frame has the
        # arms exactly on its local x axis: 0.37 sits in the 0.34-0.50 T-pose hold, 0.80 in the hit-stop.
        'particle_effects': {
            t(0.37): fist_beat(0),
            t(IMPACT): fist_beat(1),
        },
        'sound_effects': {
            t(0.0): {'effect': 'move.darkestlariat.charge'},
            t(SPIN_START): {'effect': 'move.darkestlariat.spin'},
            t(0.66): {'effect': 'move.darkestlariat.spin2'},
            t(RETURN_START): {'effect': 'move.darkestlariat.return'},
        },
    }


def dash_animation(units):
    u = float(units)
    pos = {
        0.0: [0, 0, 0], SPIN_START: [0, 0, 0],
        0.56: [0, 0, -0.08 * u],          # explosive start...
        IMPACT: [0, 0, -u],               # ...then full speed into the hit, no braking
        RETURN_START: [0, 0, -u],
        1.08: [0, 2.5, -0.82 * u], 1.16: [0, 4.0, -0.55 * u], 1.24: [0, 2.5, -0.25 * u],
        RETURN_END: [0, 0, 0], ANIM_LENGTH: [0, 0, 0],
    }
    return {
        'animation_length': ANIM_LENGTH,
        'bones': {'root_part': {'position': {t(k): vec(v) for k, v in sorted(pos.items())}}},
        # 0.45 is inside the T-pose hold, so the dash lines' captured frame faces the target.
        'particle_effects': {
            t(0.45): {'effect': 'cobblemon:darkestlariat_dashlines', 'locator': 'root'},
            t(RETURN_END): {'effect': 'cobblemon:quickattack_dust', 'locator': 'root'},
        },
    }


def target_animation():
    # Started in the same tick as the actor animation and offset by IMPACT, so the whole impact
    # (particles, sounds, knockback) is driven by the client clock and lands on the dash arrival
    # frame. Server-timed impacts drifted by +-0.3 s on a loaded integrated server.
    shove = {0.0: [0, 0, 0], 0.06: [0, 1.0, 7], 0.16: [0, 0.4, 9], 0.32: [0, 0, 4], 0.5: [0, 0, 1], 0.7: [0, 0, 0]}
    # target faces the attacker (-z), so negative x tilts it back, away from the hit
    tilt = {0.0: [0, 0, 0], 0.06: [-14, 0, 0], 0.1: [-13, 0, 5], 0.22: [-7, 0, -4],
            0.34: [-3, 0, 2], 0.46: [-1, 0, 0], 0.7: [0, 0, 0]}
    squash = {0.0: [1, 1, 1], 0.05: [1.06, 0.92, 1.06], 0.15: [0.97, 1.03, 0.97], 0.3: [1, 1, 1]}
    def shifted(frames):
        out = {t(0.0): frames[0.0]}
        out.update({t(IMPACT + k): v for k, v in sorted(frames.items())})
        return out
    impact = [{'effect': f'cobblemon:{e}', 'locator': loc} for e, loc in (
        ('impact_dark', 'target'), ('darkestlariat_impactflash', 'target'), ('darkestlariat_impactring', 'target'),
        ('darkestlariat_impactlines', 'target'), ('darkestlariat_impactsparks', 'target'),
        ('darkestlariat_impactshards', 'target'), ('darkestlariat_impactgroundring', 'root'))]
    return {
        'animation_length': round(IMPACT + 0.7, 2),
        'bones': {'root_part': {'position': shifted(shove), 'rotation': shifted(tilt), 'scale': shifted(squash)}},
        'particle_effects': {t(IMPACT): impact},
        'sound_effects': {t(IMPACT): [{'effect': 'impact.dark'}, {'effect': 'move.darkestlariat.target'}]},
    }


def build_animation_file():
    anims = {'animation.darkestlariat.actor': actor_animation(),
             'animation.darkestlariat.target': target_animation()}
    for k in range(1, DASH_VARIANTS + 1):
        anims[f'animation.darkestlariat.dash_{k}'] = dash_animation(k * DASH_STEP)
    return {'format_version': '1.8.0', 'animations': anims}


def play(anim):
    return f"q.play_animation(q.bedrock_stateful('darkestlariat', '{anim}', 'endures_primary_animations'))"


def build_effect_file():
    # Every entity_* / animation keyframe costs one server tick even with no delay (1.7.3's
    # delayedFuture(seconds) always goes through afterOnServer), so a plain list of them drifts the
    # timeline behind the client animation. Each group below is a `parallel`: one tick per group.
    start = [{'type': 'entity_molang', 'expressions': [play('actor')]}]
    half = DASH_STEP / 2
    for k in range(1, DASH_VARIANTS + 1):
        lo = k * DASH_STEP - half
        cond = f"v.dl_units >= {lo:g}" if k == DASH_VARIANTS else f"v.dl_units >= {lo:g} && v.dl_units < {lo + DASH_STEP:g}"
        start.append({'type': 'entity_molang', 'condition': cond, 'expressions': [play(f'dash_{k}')]})
    start.append({'type': 'entity_molang', 'condition': '!(v.dl_units >= 0)', 'expressions': [play(f'dash_{DASH_FALLBACK}')]})
    for effect, locator in (('gather', 'middle'), ('aura', 'root'), ('auraglint', 'root'),
                            ('swoosh', 'root'), ('swooshdark', 'root')):
        start.append({'type': 'entity_particles', 'effect': f'cobblemon:darkestlariat_{effect}', 'locators': [locator]})
    # the target's impact runs on the client clock too (see target_animation)
    start.append({'type': 'entity_molang', 'entityCondition': TARGET_COND, 'expressions': [play('target')]})
    tl = [
        {'type': 'add_holds', 'holds': ['effects']},
        # server side: how far the user has to travel (see DISTANCE_EXPR); -1 = no target entity
        {'type': 'molang', 'expressions': DISTANCE_EXPR},
        {'type': 'parallel', 'keyframes': start},
        # the parallel above already used one tick after the animations started
        {'type': 'pause', 'pause': round(IMPACT - 0.05, 2)},
        # release the battle on the hit so the HP bar drops with the impact
        {'type': 'remove_holds', 'holds': ['effects']},
        {'type': 'pause', 'pause': 0.9},
    ]
    return {'timeline': tl}


if __name__ == '__main__':
    for path, data in ((ANIM_OUT, build_animation_file()), (EFFECT_OUT, build_effect_file())):
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print('wrote', os.path.relpath(path, ROOT))
