import os
import shutil
import subprocess
import site
import magika
from modelscope.hub import snapshot_download  # 添加这行来确保 ModelScope 被正确引用


def get_magika_path():
    magika_path = os.path.dirname(magika.__file__)
    return magika_path


def get_modelscope_path():
    modelscope_path = os.path.dirname(snapshot_download.__file__)
    return os.path.dirname(modelscope_path)  # 获取 modelscope 的根目录


def build_executable():
    # 获取 magika 的安装路径
    magika_path = get_magika_path()
    modelscope_path = get_modelscope_path()

    # 清理旧的构建文件
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    # 运行PyInstaller
    subprocess.run(
        [
            "pyinstaller",
            "--name=memos",
            "--add-data",
            "memos/static:memos/static",
            f"--add-data",
            f"{magika_path}:magika",
            f"--add-data",
            f"{modelscope_path}:modelscope",
            "--onefile",
            "--noupx",
            "--clean",
            "--strip",
            "--hidden-import=modelscope",  # 添加隐式导入
            "--hidden-import=modelscope.hub",
            "--hidden-import=modelscope.hub.snapshot_download",
            "memos_app.py",
        ],
        check=True,
    )

    print("可执行文件已生成在 'dist' 目录中。")


if __name__ == "__main__":
    build_executable()
