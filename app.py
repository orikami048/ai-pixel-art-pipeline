"""兼容入口：python app.py 等同于 python -m truepixel serve"""
from truepixel.cli import main

if __name__ == "__main__":
    main(["serve"])
