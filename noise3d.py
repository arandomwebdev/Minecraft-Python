import random
from math import floor

class PerlinNoise3D:
    def __init__(self, seed=None):
        if seed is None:
            seed = 0
        self.seed = seed
        rnd = random.Random(seed)
        p = list(range(256))
        rnd.shuffle(p)
        self.perm = p + p

    def fade(self, t):
        return t * t * t * (t * (t * 6 - 15) + 10)

    def lerp(self, a, b, t):
        return a + t * (b - a)

    def grad(self, hash, x, y, z):
        h = hash & 15
        u = x if h < 8 else y
        v = y if h < 4 else (x if h in (12, 14) else z)
        return ((u if (h & 1) == 0 else -u) +
                (v if (h & 2) == 0 else -v))

    def noise(self, x, y, z):
        xi = int(floor(x)) & 255
        yi = int(floor(y)) & 255
        zi = int(floor(z)) & 255
        xf = x - floor(x)
        yf = y - floor(y)
        zf = z - floor(z)
        u = self.fade(xf)
        v = self.fade(yf)
        w = self.fade(zf)

        p = self.perm
        aaa = p[p[p[    xi ] +     yi ] +     zi ]
        aba = p[p[p[    xi ] + (yi+1)] +     zi ]
        aab = p[p[p[    xi ] +     yi ] + (zi+1)]
        abb = p[p[p[    xi ] + (yi+1)] + (zi+1)]
        baa = p[p[p[(xi+1)] +     yi ] +     zi ]
        bba = p[p[p[(xi+1)] + (yi+1)] +     zi ]
        bab = p[p[p[(xi+1)] +     yi ] + (zi+1)]
        bbb = p[p[p[(xi+1)] + (yi+1)] + (zi+1)]

        x1 = self.lerp(self.grad(aaa, xf, yf, zf),
                       self.grad(baa, xf-1, yf, zf),
                       u)
        x2 = self.lerp(self.grad(aba, xf, yf-1, zf),
                       self.grad(bba, xf-1, yf-1, zf),
                       u)
        y1 = self.lerp(x1, x2, v)

        x3 = self.lerp(self.grad(aab, xf, yf, zf-1),
                       self.grad(bab, xf-1, yf, zf-1),
                       u)
        x4 = self.lerp(self.grad(abb, xf, yf-1, zf-1),
                       self.grad(bbb, xf-1, yf-1, zf-1),
                       u)
        y2 = self.lerp(x3, x4, v)

        return (self.lerp(y1, y2, w) + 1) / 2

    def fractal_noise(self, x, y, z, octaves=4, lacunarity=2.0, gain=0.5):
        amplitude = 1.0
        frequency = 1.0
        total = 0.0
        maxA = 0.0
        for _ in range(octaves):
            total += self.noise(x * frequency, y * frequency, z * frequency) * amplitude
            maxA += amplitude
            amplitude *= gain
            frequency *= lacunarity
        return total / maxA

    def cave_density(self, x, y, z, threshold=0.45):
        d = self.fractal_noise(x * 0.05, y * 0.05, z * 0.05, octaves=4)

        warp = self.noise(x * 0.1, y * 0.1, z * 0.1) * 4.0
        d2 = self.fractal_noise(
            (x + warp) * 0.05,
            (y + warp) * 0.05,
            (z + warp) * 0.05,
            octaves=4
        )

        density = (d + d2) * 0.5

        return density < threshold
