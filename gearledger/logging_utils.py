# -*- coding: utf-8 -*-


def step(msg: str) -> None:
    print(f"[STEP] {msg}")


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def err(msg: str) -> None:
    print(f"[ERROR] {msg}")
