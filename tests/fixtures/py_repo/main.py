"""Fixture: imports auth and calls authenticate."""

from auth import authenticate


def main() -> None:
    if authenticate("admin"):
        print("ok")
