"""CLI: python -m sticky_scorer"""

from .simulate import demo_report, proxy_aligner_report


def main() -> None:
    print(demo_report())
    print()
    print(proxy_aligner_report())


if __name__ == "__main__":
    main()
