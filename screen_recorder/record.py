import time
import subprocess
from AppKit import NSWorkspace
from PIL import Image
import os
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    CGSessionCopyCurrentDictionary,
)
import json
import imagehash
import argparse
from memos.utils import write_image_metadata


def get_active_window_info():
    active_app = NSWorkspace.sharedWorkspace().activeApplication()
    app_name = active_app["NSApplicationName"]
    app_pid = active_app["NSApplicationProcessIdentifier"]

    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    )
    for window in windows:
        if window["kCGWindowOwnerPID"] == app_pid:
            window_title = window.get("kCGWindowName", "")
            if window_title:
                return app_name, window_title

    return app_name, ""  # 如果没有找到窗口标题，则返回空字符串作为标题


def load_screen_sequences(base_dir, date):
    try:
        with open(os.path.join(base_dir, date, ".screen_sequences"), "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_screen_sequences(base_dir, screen_sequences, date):
    with open(os.path.join(base_dir, date, ".screen_sequences"), "w") as f:
        json.dump(screen_sequences, f)
        f.flush()
        os.fsync(f.fileno())


def take_screenshot(
    base_dir, previous_hashes, threshold, screen_sequences, date, timestamp
):
    screenshots = []

    # 获取连接的显示器数量
    result = subprocess.check_output(["system_profiler", "SPDisplaysDataType", "-json"])
    display_count = len(json.loads(result)["SPDisplaysDataType"][0]["spdisplays_ndrvs"])

    app_name, window_title = get_active_window_info()

    # 创建日期目录
    os.makedirs(os.path.join(base_dir, date), exist_ok=True)

    # 打开 worklog 文件
    worklog_path = os.path.join(base_dir, date, "worklog")
    with open(worklog_path, "a") as worklog:
        for display in range(display_count):
            # 获取显示器名称
            display_info = json.loads(result)["SPDisplaysDataType"][0][
                "spdisplays_ndrvs"
            ][display]
            screen_name = display_info["_name"].replace(" ", "_").lower()

            # 生成临时 PNG 文件名
            temp_filename = os.path.join(
                os.path.join(base_dir, date),
                f"temp_screenshot-{timestamp}-of-{screen_name}.png",
            )

            # 使用 screencapture 命令进行截图，-D 选项指定显示器
            subprocess.run(
                ["screencapture", "-C", "-x", "-D", str(display + 1), temp_filename]
            )

            # 压缩图像为 WebP 并添加元数据
            with Image.open(temp_filename) as img:
                img = img.convert("RGB")
                webp_filename = os.path.join(
                    os.path.join(base_dir, date),
                    f"screenshot-{timestamp}-of-{screen_name}.webp",
                )

                # 计算当前截图的哈希值
                current_hash = imagehash.phash(img)

                # 检查当前截图与前一次截图的哈希值是否相似
                if (
                    screen_name in previous_hashes
                    and current_hash - previous_hashes[screen_name] < threshold
                ):
                    print(
                        f"Screenshot for {screen_name} is similar to the previous one. Skipping."
                    )
                    os.remove(temp_filename)
                    # 记录跳过的截图
                    worklog.write(
                        f"{timestamp} - {screen_name} - Skipped (similar to previous)\n"
                    )
                    continue

                # 更新前一次截图的哈希值
                previous_hashes[screen_name] = current_hash

                # 更新序列号
                screen_sequences[screen_name] = screen_sequences.get(screen_name, 0) + 1

                # 准备元数据
                metadata = {
                    "timestamp": timestamp,
                    "active_app": app_name,
                    "active_window": window_title,
                    "screen_name": screen_name,
                    "sequence": screen_sequences[screen_name],  # 添加序列号到元数据
                }

                # 使用 write_image_metadata 函数写入元数据
                img.save(webp_filename, format="WebP", quality=85)
                write_image_metadata(webp_filename, metadata)
                save_screen_sequences(base_dir, screen_sequences, date)

            # 删除临时 PNG 文件
            os.remove(temp_filename)

            # 添加 WebP 文件到截图列表
            screenshots.append(webp_filename)
            # 记录成功的截图
            worklog.write(f"{timestamp} - {screen_name} - Saved\n")

    return screenshots


def is_screen_locked():
    session_dict = CGSessionCopyCurrentDictionary()
    if session_dict:
        screen_locked = session_dict.get("CGSSessionScreenIsLocked", 0)
        return bool(screen_locked)
    return False


def main():
    parser = argparse.ArgumentParser(description="Screen Recorder")
    parser.add_argument(
        "--threshold", type=int, default=4, help="Threshold for image similarity"
    )
    parser.add_argument(
        "--base-dir", type=str, default="~/tmp", help="Base directory for screenshots"
    )
    args = parser.parse_args()

    base_dir = os.path.expanduser(args.base_dir)

    previous_hashes = {}

    while True:
        try:
            if not is_screen_locked():
                date = time.strftime("%Y%m%d")
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                screen_sequences = load_screen_sequences(base_dir, date)
                screenshot_files = take_screenshot(
                    base_dir,
                    previous_hashes,
                    args.threshold,
                    screen_sequences,
                    date,
                    timestamp,
                )
                for screenshot_file in screenshot_files:
                    print(f"Screenshot taken: {screenshot_file}")
            else:
                print("Screen is locked. Skipping screenshot.")
        except Exception as e:
            print(f"An error occurred: {str(e)}. Skipping this iteration.")

        time.sleep(5)


if __name__ == "__main__":
    main()