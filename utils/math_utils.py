import numpy as np


def random_normal_distribution_int(a, b, n=15):
    if a < b:
        output = np.mean(np.random.randint(a, b, size=n))
        return int(output.round())
    return b


def random_rectangle_point(area, n=3):
    x = random_normal_distribution_int(area[0][0], area[1][0], n=n)
    y = random_normal_distribution_int(area[0][1], area[1][1], n=n)
    return x, y
