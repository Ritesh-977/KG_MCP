"""Fixture: a tiny module with one function imported by main.py."""


def authenticate(user: str) -> bool:
    return user == "admin"
