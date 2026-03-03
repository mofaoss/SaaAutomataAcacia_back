try:
    import cpufeature
except Exception:
    cpufeature = None


def cpu_support_avx2(config=None):
    if cpufeature is None:
        support = False
    else:
        try:
            support = bool(cpufeature.CPUFeature["AVX2"])
        except Exception:
            support = False

    if config is not None:
        try:
            config.set(config.cpu_support_avx2, support)
        except Exception:
            pass

    return support
