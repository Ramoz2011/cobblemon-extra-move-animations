package _1dknone.cobblemon_extra_move_animation.client.wave;

import net.minecraft.client.render.OverlayTexture;
import net.minecraft.client.render.VertexConsumer;
import net.minecraft.client.util.math.MatrixStack;
import net.minecraft.util.math.Vec3d;
import org.joml.Matrix4f;

/**
 * A sheet of water as a grid of vertices (columns x rows) in world space, with a colour, an opacity and a
 * texture coordinate at each. It is drawn as one quad per grid cell, both sides visible; the normals for
 * the lighting come from the grid's own shape, turned towards a hint direction so a surface seen from
 * above is lit as one.
 */
final class WaveGrid {
    final int cols;
    final int rows;
    private final double[] x;
    private final double[] y;
    private final double[] z;
    private final float[] r;
    private final float[] g;
    private final float[] b;
    private final float[] a;
    private final float[] u;
    private final float[] v;
    private final float[] nx;
    private final float[] ny;
    private final float[] nz;

    WaveGrid(int cols, int rows) {
        this.cols = cols;
        this.rows = rows;
        int n = cols * rows;
        x = new double[n];
        y = new double[n];
        z = new double[n];
        r = new float[n];
        g = new float[n];
        b = new float[n];
        a = new float[n];
        u = new float[n];
        v = new float[n];
        nx = new float[n];
        ny = new float[n];
        nz = new float[n];
    }

    void put(int col, int row, double px, double py, double pz, float[] colour, double alpha, double tu, double tv) {
        int i = row * cols + col;
        x[i] = px;
        y[i] = py;
        z[i] = pz;
        r[i] = colour[0];
        g[i] = colour[1];
        b[i] = colour[2];
        a[i] = (float) Math.max(0, Math.min(1, alpha));
        u[i] = (float) tu;
        v[i] = (float) tv;
    }

    /**
     * Draws the grid. {@code hintX/Y/Z} is the side a normal should face (up for the wave and the pool);
     * with {@code radial} set it is instead the horizontal direction away from that point (the crown).
     * {@code upBias} tips every normal towards the sky, which softens Minecraft's entity shading: steep
     * water would otherwise come out half as bright as flat water.
     */
    void draw(VertexConsumer buffer, MatrixStack.Entry entry, Vec3d camera, int light,
              double hintX, double hintY, double hintZ, boolean radial, double upBias) {
        normals(hintX, hintY, hintZ, radial, upBias);
        Matrix4f pose = entry.getPositionMatrix();
        for (int row = 0; row < rows - 1; row++) {
            for (int col = 0; col < cols - 1; col++) {
                int i00 = row * cols + col;
                int i10 = i00 + 1;
                int i01 = i00 + cols;
                int i11 = i01 + 1;
                if (a[i00] < 0.004F && a[i10] < 0.004F && a[i01] < 0.004F && a[i11] < 0.004F) {
                    continue;
                }
                vertex(buffer, pose, entry, camera, light, i00);
                vertex(buffer, pose, entry, camera, light, i10);
                vertex(buffer, pose, entry, camera, light, i11);
                vertex(buffer, pose, entry, camera, light, i01);
            }
        }
    }

    private void vertex(VertexConsumer buffer, Matrix4f pose, MatrixStack.Entry entry, Vec3d camera, int light, int i) {
        buffer.vertex(pose, (float) (x[i] - camera.x), (float) (y[i] - camera.y), (float) (z[i] - camera.z))
                .color(r[i], g[i], b[i], a[i])
                .texture(u[i], v[i])
                .overlay(OverlayTexture.DEFAULT_UV)
                .light(light)
                .normal(entry, nx[i], ny[i], nz[i]);
    }

    private void normals(double hintX, double hintY, double hintZ, boolean radial, double upBias) {
        for (int row = 0; row < rows; row++) {
            for (int col = 0; col < cols; col++) {
                int i = row * cols + col;
                int left = row * cols + Math.max(col - 1, 0);
                int right = row * cols + Math.min(col + 1, cols - 1);
                int down = Math.max(row - 1, 0) * cols + col;
                int up = Math.min(row + 1, rows - 1) * cols + col;
                double ax = x[right] - x[left], ay = y[right] - y[left], az = z[right] - z[left];
                double bx = x[up] - x[down], by = y[up] - y[down], bz = z[up] - z[down];
                double cx = ay * bz - az * by, cy = az * bx - ax * bz, cz = ax * by - ay * bx;
                double length = Math.sqrt(cx * cx + cy * cy + cz * cz);
                if (length < 1.0E-9) {
                    cx = 0;
                    cy = 1;
                    cz = 0;
                    length = 1;
                }
                double hx = hintX, hy = hintY, hz = hintZ;
                if (radial) {
                    hx = x[i] - hintX;
                    hy = 0;
                    hz = z[i] - hintZ;
                }
                double sign = cx * hx + cy * hy + cz * hz < 0 ? -1 : 1;
                double ox = sign * cx / length, oy = sign * cy / length + upBias, oz = sign * cz / length;
                double tipped = Math.sqrt(ox * ox + oy * oy + oz * oz);
                if (tipped < 1.0E-9) {
                    ox = 0;
                    oy = 1;
                    oz = 0;
                    tipped = 1;
                }
                nx[i] = (float) (ox / tipped);
                ny[i] = (float) (oy / tipped);
                nz[i] = (float) (oz / tipped);
            }
        }
    }
}
