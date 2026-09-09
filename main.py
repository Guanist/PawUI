"""传统启动方式：import pawui + context 传 Python 回调。"""

import pawui


def say_hi():
    print("hi from main.py")


if __name__ == "__main__":
    pawui.run("app.paw", context={"say_hi": say_hi})
