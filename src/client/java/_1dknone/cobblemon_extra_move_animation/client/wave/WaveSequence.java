package _1dknone.cobblemon_extra_move_animation.client.wave;

import _1dknone.cobblemon_extra_move_animation.wave.WavePayload;
import net.minecraft.block.ShapeContext;
import net.minecraft.client.MinecraftClient;
import net.minecraft.client.render.RenderLayer;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.client.render.VertexConsumerProvider;
import net.minecraft.client.render.WorldRenderer;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.client.world.ClientWorld;
import net.minecraft.entity.Entity;
import net.minecraft.entity.LivingEntity;
import net.minecraft.util.hit.BlockHitResult;
import net.minecraft.util.hit.HitResult;
import net.minecraft.util.math.BlockPos;
import net.minecraft.util.math.Vec3d;
import net.minecraft.world.RaycastContext;

import java.util.List;

/**
 * One wave, from the moment its packet arrived. Time runs on client ticks plus the frame's partial tick,
 * the same clock as the move's animations, so the crash lands on the frame the targets react.
 *
 * <p>Three sheets of water, rebuilt every frame from where the Pokemon stand:
 * <ol>
 *   <li>a muddy pool swirling out under the user, and a crown of water rising round it (gathering);</li>
 *   <li>the wave: the crown collapses forwards into a curling wave as wide as the targets' line, which
 *       rolls over to them, its lip curling further as it goes (release);</li>
 *   <li>the crash: the lip falls onto the targets, the wave flattens into a flood that surges past them
 *       and drains away, the end nearest the user first (impact, then cleanup).</li>
 * </ol>
 * Everything is placed from the Pokemon's positions and hitboxes, never from bones, so it fits any model.
 */
final class WaveSequence {
    // ---- mesh resolution
    private static final int COLS = 36;            // cells across the wave
    private static final int TAIL_ROWS = 10;       // flat water trailing back to the user
    private static final int BACK_ROWS = 16;       // the wave's back, up to the crest
    private static final int FACE_ROWS = 18;       // over the crest, the lip and down the face
    private static final int LIP_ROWS = 8;         // ... of which the curling lip's outside
    private static final int ROWS = TAIL_ROWS + BACK_ROWS + FACE_ROWS;
    private static final int RING = 40;            // cells round the crown and the pool
    private static final int CROWN_ROWS = 8;
    private static final int POOL_RINGS = 5;
    /** How far below a Pokemon the ground is looked for (fliers hover above it). */
    private static final double MAX_DROP = 6;
    /** Lifts the water off the ground so it doesn't flicker against it. */
    private static final double LIFT = 0.03;

    private final ClientWorld world;
    private final WaveStyle style;
    private final int userId;
    private final List<Integer> targetIds;
    private int ticks;

    // where everyone stands; kept when an entity unloads mid-move so the wave doesn't snap away
    private Vec3d user;
    private double userGround;
    private float userWidth = 0.8F;
    private float userHeight = 1F;
    private Vec3d facing = new Vec3d(0, 0, 1);
    private final Vec3d[] targets;
    private final double[] targetGrounds;
    private final float[] targetWidths;

    // this frame's layout: user's feet on the ground, unit vectors towards the targets and across
    private double originX;
    private double originZ;
    private double forwardX;
    private double forwardZ;
    private double distance;
    private double halfWidth;
    private double targetGround;

    private final WaveGrid wave = new WaveGrid(COLS + 1, ROWS);
    private final WaveGrid crown = new WaveGrid(RING + 1, CROWN_ROWS + 1);
    private final WaveGrid pool = new WaveGrid(RING + 1, POOL_RINGS + 1);
    // the wave's cross-section through its middle, from the user's end to the toe of its face
    private final double[] profileA = new double[ROWS];   // forward of the crest (blocks)
    private final double[] profileB = new double[ROWS];   // height (blocks)
    private final double[] profileK = new double[ROWS];   // 0..1 along its part of the profile
    private final double[] arc = new double[ROWS];        // length along the surface (texture)
    private final float[] colour = new float[3];

    WaveSequence(ClientWorld world, WaveStyle style, WavePayload payload) {
        this.world = world;
        this.style = style;
        this.userId = payload.userId();
        this.targetIds = payload.targetIds();
        this.targets = new Vec3d[targetIds.size()];
        this.targetGrounds = new double[targetIds.size()];
        this.targetWidths = new float[targetIds.size()];
    }

    /** Runs once per client tick; false once the water has drained (or the player changed world). */
    boolean tick(MinecraftClient client) {
        if (client.world != world) {
            return false;
        }
        ticks++;
        return ticks / 20F <= style.drainEnd + 0.1F;
    }

    void render(MatrixStack matrices, VertexConsumerProvider consumers, Vec3d camera, float tickDelta) {
        if (!stage(tickDelta)) {
            return;
        }
        double t = (ticks + tickDelta) / 20.0;
        boolean anyCrown = buildCrown(t);
        boolean anyPool = buildPool(t);
        boolean anyWave = buildWave(t);
        if (!anyCrown && !anyPool && !anyWave) {
            return;
        }
        double midX = originX + forwardX * distance * 0.5;
        double midZ = originZ + forwardZ * distance * 0.5;
        int light = WorldRenderer.getLightmapCoordinates(world,
                BlockPos.ofFloored(midX, Math.max(userGround, targetGround) + 1, midZ));
        VertexConsumer buffer = consumers.getBuffer(RenderLayer.getEntityTranslucent(style.texture));
        MatrixStack.Entry entry = matrices.peek();
        double bias = style.lightingUpBias;
        if (anyPool) {
            pool.draw(buffer, entry, camera, light, 0, 1, 0, false, bias);
        }
        if (anyCrown) {
            crown.draw(buffer, entry, camera, light, originX, 0, originZ, true, bias);
        }
        if (anyWave) {
            wave.draw(buffer, entry, camera, light, 0, 1, 0, false, bias);
        }
    }

    // ================================================================= where everyone stands
    private boolean stage(float tickDelta) {
        Entity userEntity = world.getEntityById(userId);
        if (userEntity != null) {
            Vec3d pos = userEntity.getLerpedPos(tickDelta);
            if (user == null || pos.squaredDistanceTo(user) > 0.04) {
                userGround = ground(pos, userEntity.getHeight());
            }
            user = pos;
            userWidth = userEntity.getWidth();
            userHeight = userEntity.getHeight();
            float yaw = userEntity instanceof LivingEntity living ? living.getBodyYaw() : userEntity.getYaw();
            facing = Vec3d.fromPolar(0, yaw);
        }
        if (user == null) {
            return false;
        }
        double sumX = 0, sumZ = 0, sumGround = 0;
        int known = 0;
        for (int i = 0; i < targets.length; i++) {
            Entity target = world.getEntityById(targetIds.get(i));
            if (target != null) {
                Vec3d pos = target.getLerpedPos(tickDelta);
                if (targets[i] == null || pos.squaredDistanceTo(targets[i]) > 0.04) {
                    targetGrounds[i] = ground(pos, target.getHeight());
                }
                targets[i] = pos;
                targetWidths[i] = target.getWidth();
            }
            if (targets[i] != null) {
                sumX += targets[i].x;
                sumZ += targets[i].z;
                sumGround += targetGrounds[i];
                known++;
            }
        }
        originX = user.x;
        originZ = user.z;
        double dx, dz;
        if (known == 0) {
            // nothing to aim at: roll forwards from where the user faces
            dx = facing.x * 4;
            dz = facing.z * 4;
            targetGround = userGround;
        } else {
            dx = sumX / known - user.x;
            dz = sumZ / known - user.z;
            targetGround = sumGround / known;
        }
        distance = Math.sqrt(dx * dx + dz * dz);
        if (distance < 1.0E-3) {
            Vec3d flat = new Vec3d(facing.x, 0, facing.z).normalize();
            dx = flat.x;
            dz = flat.z;
            distance = 1;
        }
        forwardX = dx / distance;
        forwardZ = dz / distance;
        distance = Math.max(distance, 1.5);

        // wide enough for every target with room to spare
        double half = Math.max(style.minHalfWidth, 0.5 * userWidth + style.sidePadding);
        for (int i = 0; i < targets.length; i++) {
            if (targets[i] != null) {
                double lateral = (targets[i].x - user.x) * -forwardZ + (targets[i].z - user.z) * forwardX;
                half = Math.max(half, Math.abs(lateral) + 0.5 * targetWidths[i] + style.sidePadding);
            }
        }
        halfWidth = half;
        return true;
    }

    /** The ground (or water surface) under a Pokemon, which may be hovering. */
    private double ground(Vec3d pos, float height) {
        Vec3d from = pos.add(0, Math.min(0.5, height * 0.5), 0);
        Vec3d to = pos.add(0, -MAX_DROP, 0);
        BlockHitResult hit = world.raycast(new RaycastContext(from, to, RaycastContext.ShapeType.COLLIDER,
                RaycastContext.FluidHandling.ANY, ShapeContext.absent()));
        return hit.getType() == HitResult.Type.MISS ? pos.y : hit.getPos().y;
    }

    /** Ground height at a distance along the line from the user to the targets. */
    private double groundAt(double along) {
        return userGround + (targetGround - userGround) * clamp01(along / distance) + LIFT;
    }

    // ================================================================= 1. gathering: the pool and the crown
    private boolean buildPool(double t) {
        WaveStyle s = style;
        double fadeStart = s.release + s.crownCollapse;
        if (t < s.crownRise || t > fadeStart + 0.45) {
            return false;
        }
        double grow = easeOut(clamp01((t - s.crownRise) / 0.3));
        double fade = 1 - smooth(clamp01((t - fadeStart) / 0.45));
        double radius = (0.5 * userWidth + s.poolRadius) * grow;
        double spin = -Math.toRadians(0.6 * s.crownSwirl * (t - s.crownRise));
        for (int i = 0; i <= RING; i++) {
            double theta = 2 * Math.PI * i / RING;
            for (int k = 0; k <= POOL_RINGS; k++) {
                double share = k / (double) POOL_RINGS;
                double rr = radius * share;
                double px = originX + rr * Math.cos(theta + spin);
                double pz = originZ + rr * Math.sin(theta + spin);
                double py = userGround + LIFT + 0.03 * share * Math.sin(3 * theta + 5 * t);
                double lx = rr * Math.cos(theta), lz = rr * Math.sin(theta);
                mottle(s.body, lx * 0.9 + 0.8 * t, lz * 0.9 - 0.5 * t, 0.45);
                double alpha = s.alphaPool * (1 - share * share) * fade;
                pool.put(i, k, px, py, pz, colour, alpha, lx / s.textureBlocks, lz / s.textureBlocks);
            }
        }
        return true;
    }

    private boolean buildCrown(double t) {
        WaveStyle s = style;
        if (t < s.crownRise || t > s.release + s.crownCollapse) {
            return false;
        }
        double rise = easeOut(clamp01((t - s.crownRise) / (s.crownPeak - s.crownRise)));
        double collapse = smooth(clamp01((t - s.release) / s.crownCollapse));
        double full = s.crownHeight.of(userHeight);
        double height = full * rise * (1 - 0.9 * collapse);
        double inner = 0.5 * userWidth + s.crownGap + 0.8 * full * collapse;   // bursts outwards as it falls
        double spin = Math.toRadians(s.crownSwirl * (t - s.crownRise));
        int repeats = Math.max(2, (int) Math.round(2 * Math.PI * inner / s.textureBlocks));
        double fadeIn = clamp01((t - s.crownRise) / 0.08);
        for (int i = 0; i <= RING; i++) {
            double theta = 2 * Math.PI * i / RING;
            for (int k = 0; k <= CROWN_ROWS; k++) {
                double share = k / (double) CROWN_ROWS;
                double top = 1 + s.crownJag * share * share * (0.6 * Math.sin(5 * theta + 2.6 * t) + 0.4 * Math.sin(9 * theta - 3.7 * t));
                double radius = inner + s.crownFlare * share * height;
                double py = userGround + LIFT + share * height * top;
                double px = originX + radius * Math.cos(theta + spin);
                double pz = originZ + radius * Math.sin(theta + spin);
                // dark at the foot, foaming at the rim
                blend(s.deep, s.body, share);
                double foam = smooth((share - 0.72) / 0.28);
                mix(s.foam, foam);
                mottleInPlace(s, theta * 2.2 + 1.1 * t, share * 2.5 - 1.6 * t, 0.35 * (1 - foam));
                double alpha = (s.alphaCrown + (s.alphaFoam - s.alphaCrown) * foam) * fadeIn * (1 - 0.5 * collapse);
                crown.put(i, k, px, py, pz, colour, alpha, repeats * i / (double) RING,
                        -share * height / s.textureBlocks + 1.1 * t);
            }
        }
        return true;
    }

    // ================================================================= 2-3. the wave, the crash and the flood
    private boolean buildWave(double t) {
        WaveStyle s = style;
        if (t < s.release || t > s.drainEnd) {
            return false;
        }
        double p = clamp01((t - s.release) / (s.impact - s.release));    // rolling over to the targets
        double q = clamp01((t - s.impact) / (s.crashEnd - s.impact));    // crashing
        double d = clamp01((t - s.crashEnd) / (s.drainEnd - s.crashEnd)); // draining
        double travel = 0.65 * p + 0.35 * smooth(p);   // a quick start, fastest in the middle
        double big = s.waveHeight.of(userHeight);

        // the crest: forms just in front of the user, lands its lip on the targets at the impact
        double x0 = 0.5 * userWidth + s.startGap;
        double x1 = Math.max(x0 + 0.3, distance - s.lip * big);
        double crestX = x0 + (x1 - x0) * travel + s.overshoot * big * easeOut(q) + 0.35 * big * d;
        double height = big * (0.55 + 0.45 * smooth(Math.min(p / 0.55, 1)));
        height *= 1 - 0.84 * Math.pow(q, 0.8);
        height *= 1 - 0.6 * d;
        double curl = smooth((p - 0.25) / 0.75);
        double overhang = s.lip * big * (0.2 + 0.8 * curl);
        double fall = smooth(q);                              // the crash flattening the wave
        double sheet = (0.06 + 0.07 * fall) * (1 - 0.8 * d);  // depth of the flat water behind it

        // the flat water reaches back to the user, and drains from that end first
        double tailStart = (x0 - 0.35) + Math.max(0, crestX - x0) * 0.75 * smooth(d);
        double tailA = Math.min(tailStart - crestX, -0.05);
        double back = Math.min(1.3 * height + 0.3, -tailA);

        int row = 0;
        for (int k = 0; k < TAIL_ROWS; k++, row++) {
            double f = k / (double) TAIL_ROWS;
            profileA[row] = tailA + (-back - tailA) * f;
            profileB[row] = sheet;
            profileK[row] = f;
        }
        for (int k = 0; k < BACK_ROWS; k++, row++) {
            double f = k / (double) BACK_ROWS;
            profileA[row] = -back * (1 - f);
            profileB[row] = sheet + (height - sheet) * Math.pow(smooth(f), 1.15);
            profileK[row] = f;
        }
        // Over the crest the lip curls forward and down (its outside foams), then the face runs back
        // under it, hollowed out, to the toe on the ground. In the crash the lip is thrown forward onto
        // the targets and comes down, and the toe surges on with the flood.
        double surge = big * easeOut(q);
        double slam = smooth(Math.min(q * 1.6, 1));          // the lip comes down fast, onto the targets
        double lipX = overhang * 1.02 + 0.55 * surge;
        double lipY = height * (0.8 - 0.2 * curl) * (1 - 0.95 * slam);
        double toe = 0.2 * height + 1.1 * surge;
        for (int k = 0; k < FACE_ROWS; k++, row++) {
            double f = k / (double) (FACE_ROWS - 1);
            if (k < LIP_ROWS) {
                // the lip's outside: crest -> lip tip
                double g = k / (double) LIP_ROWS;
                profileA[row] = bezier(0, 0.55 * overhang, overhang * 1.02 + 0.4 * surge, lipX, g);
                profileB[row] = bezier(height, height * (1.04 - 0.3 * fall), height * (0.97 - 0.6 * fall), lipY, g);
            } else {
                // under the lip and down the hollow face: lip tip -> toe
                double g = (k - LIP_ROWS) / (double) (FACE_ROWS - 1 - LIP_ROWS);
                profileA[row] = bezier(lipX, lipX + 0.05 * overhang, 0.12 * height + 0.5 * surge, toe, g);
                profileB[row] = bezier(lipY, lipY - 0.28 * height, 0.45 * height * (1 - fall), 0, g);
            }
            profileK[row] = f;
        }
        arc[0] = 0;
        for (int i = 1; i < ROWS; i++) {
            arc[i] = arc[i - 1] + Math.hypot(profileA[i] - profileA[i - 1], profileB[i] - profileB[i - 1]);
        }
        double crestArc = arc[TAIL_ROWS + BACK_ROWS];
        double envelope = clamp01((t - s.release) / 0.07) * Math.pow(1 - d, 1.4);
        double sideX = -forwardZ, sideZ = forwardX;
        double userHalf = 0.5 * userWidth + 0.45;
        // The wave fans out from the user: about its width as it forms, as wide as the targets' line by the
        // time it is most of the way there (so it doesn't sweep through a partner standing beside the user)
        double startHalf = Math.min(halfWidth, 0.5 * userWidth + 0.9);
        double halfNow = startHalf + (halfWidth - startHalf) * smooth(p / 0.65);

        for (int col = 0; col <= COLS; col++) {
            double u = -1 + 2.0 * col / COLS;
            double au = Math.abs(u);
            double ends = Math.sqrt(Math.max(0, 1 - Math.pow(au, s.endTaper)));   // the wave sinks into the ground at its ends
            double wobble = s.crestNoise * (0.6 * Math.sin(7.3 * u + 4.1 * t) + 0.4 * Math.sin(15.7 * u - 6.3 * t));
            double bowShift = -s.bow * height * u * u;
            double endFade = 1 - 0.7 * smooth((au - 0.7) / 0.3);
            for (int r = 0; r < ROWS; r++) {
                boolean tail = r < TAIL_ROWS;
                boolean face = r >= TAIL_ROWS + BACK_ROWS;
                double k = profileK[r];
                double half = tail ? userHalf + (halfNow - userHalf) * smooth(k) : halfNow;
                double along = crestX + profileA[r] + (tail ? bowShift * k : bowShift);
                double lateral = u * half;
                double h = profileB[r];
                if (!tail) {
                    h *= ends * (1 + wobble * h / Math.max(height, 1.0E-3));
                }
                double px = originX + forwardX * along + sideX * lateral;
                double pz = originZ + forwardZ * along + sideZ * lateral;
                double py = groundAt(along) + h;

                double alpha;
                if (tail) {
                    // thin water fanning out from the user
                    blend(s.body, s.light, 0.3);
                    alpha = s.alphaSheet * smooth(k * 3);
                } else if (!face) {
                    // the wave's back: darker where the water is deep, foaming as it nears the crest
                    blend(s.body, s.deep, 0.7 * h / Math.max(big, 1.0E-3));
                    double foam = 0.85 * smooth((k - s.foamBack) / (1 - s.foamBack));
                    mix(s.foam, foam);
                    alpha = s.alphaBody + (s.alphaFoam - s.alphaBody) * foam;
                } else {
                    // the crest and the lip foam; the face below is dark, and thins out to the toe
                    double foam = 1 - smooth(k / s.foamFace);
                    blend(s.deep, s.body, smooth(k / 0.6));
                    mix(s.foam, foam);
                    alpha = (s.alphaBody + (s.alphaFoam - s.alphaBody) * foam) * (1 - 0.35 * smooth((k - 0.7) / 0.3));
                }
                mottleInPlace(s, lateral * 0.55 + 0.7 * t, arc[r] * 0.5 - 1.3 * t, s.mottle);
                wave.put(col, r, px, py, pz, colour, alpha * endFade * envelope,
                        lateral / s.textureBlocks + 0.15 * t, (arc[r] - crestArc) / s.textureBlocks - s.flowSpeed * t);
            }
        }
        return true;
    }

    // ================================================================= colour helpers (write into `colour`)
    private void blend(float[] from, float[] to, double share) {
        double k = clamp01(share);
        for (int i = 0; i < 3; i++) {
            colour[i] = (float) (from[i] + (to[i] - from[i]) * k);
        }
    }

    private void mix(float[] towards, double share) {
        double k = clamp01(share);
        for (int i = 0; i < 3; i++) {
            colour[i] = (float) (colour[i] + (towards[i] - colour[i]) * k);
        }
    }

    private void mottle(float[] base, double nx, double ny, double strength) {
        System.arraycopy(base, 0, colour, 0, 3);
        mottleInPlace(style, nx, ny, strength);
    }

    /** Swirls of lighter and darker mud drifting through the water. */
    private void mottleInPlace(WaveStyle s, double nx, double ny, double strength) {
        double n = noise(nx, ny) * 0.65 + noise(nx * 2.3 + 17.1, ny * 2.3 - 5.7) * 0.35;
        if (n > 0) {
            mix(s.light, strength * n * 1.4);
        } else {
            mix(s.deep, strength * -n * 1.2);
        }
    }

    // ================================================================= maths
    static double clamp01(double x) {
        return x < 0 ? 0 : x > 1 ? 1 : x;
    }

    static double smooth(double x) {
        x = clamp01(x);
        return x * x * (3 - 2 * x);
    }

    static double easeOut(double x) {
        x = clamp01(x);
        return 1 - (1 - x) * (1 - x);
    }

    /** Cubic Bezier through p0..p3 at t (one coordinate). */
    static double bezier(double p0, double p1, double p2, double p3, double t) {
        double m = 1 - t;
        return m * m * m * p0 + 3 * m * m * t * p1 + 3 * m * t * t * p2 + t * t * t * p3;
    }

    /** Smooth value noise in -1..1. */
    static double noise(double x, double y) {
        int xi = (int) Math.floor(x), yi = (int) Math.floor(y);
        double xf = x - xi, yf = y - yi;
        double u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
        double a = hash(xi, yi), b = hash(xi + 1, yi), c = hash(xi, yi + 1), e = hash(xi + 1, yi + 1);
        double top = a + (b - a) * u, bottom = c + (e - c) * u;
        return (top + (bottom - top) * v) * 2 - 1;
    }

    private static double hash(int x, int y) {
        int h = x * 374761393 + y * 668265263;
        h = (h ^ (h >>> 13)) * 1274126177;
        h ^= h >>> 16;
        return (h & 0x7fffffff) / (double) 0x7fffffff;
    }
}
