import argparse


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="goldenset")
    args = parser.parse_args()
    print(f"Evaluation suite '{args.suite}' is stubbed until Phase 1G.")


if __name__ == "__main__":
    main()
