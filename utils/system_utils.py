import sys
import ctypes

def cpu_support_avx2(config=None):
    support = False

    # 仅在 Windows 环境下调用原生 API 检测
    if sys.platform == "win32":
        try:
            # 40 对应 Windows API 中的 PF_AVX2_INSTRUCTIONS_AVAILABLE
            support = bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(40))
        except Exception:
            support = False

    if config is not None:
        try:
            config.set(config.cpu_support_avx2, support)
        except Exception:
            pass

    return support


if __name__ == "__main__":
    print("AVX2 Support:", cpu_support_avx2())
