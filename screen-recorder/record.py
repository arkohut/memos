import time
import subprocess
from AppKit import NSWorkspace
from PIL import Image
import os
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    CGSessionCopyCurrentDictionary
)
import piexif
import json
import imagehash  # 新增
import argparse  # 新增

def get_active_window_title():
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
                return f"{app_name} - {window_title}"

    return app_name  # 如果没有找到窗口标题，则只返回应用名称


def take_screenshot(previous_hashes, threshold):  # 修改：添加 threshold 参数
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    date = timestamp.split("-")[0]
    screenshots = []

    # 获取连接的显示器数量
    result = subprocess.check_output(["system_profiler", "SPDisplaysDataType", "-json"])
    display_count = len(json.loads(result)["SPDisplaysDataType"][0]["spdisplays_ndrvs"])
    
    window_title = get_active_window_title()

    # 创建日期目录
    os.makedirs(date, exist_ok=True)

    # 打开 worklog 文件
    worklog_path = os.path.join(date, "worklog")
    with open(worklog_path, "a") as worklog:
        for display in range(display_count):
            # 获取显示器名称
            display_info = json.loads(result)["SPDisplaysDataType"][0]["spdisplays_ndrvs"][display]
            screen_name = display_info["_name"].replace(" ", "_").lower()

            # 生成临时 PNG 文件名
            temp_filename = os.path.join(date, f"temp_screenshot-{timestamp}-of-{screen_name}.png")

            # 使用 screencapture 命令进行截图，-D 选项指定显示器
            subprocess.run(["screencapture", "-C", "-x", "-D", str(display + 1), temp_filename])

            # 压缩图像为 JPEG 并添加元数据
            with Image.open(temp_filename) as img:
                img = img.convert("RGB")
                jpeg_filename = os.path.join(date, f"screenshot-{timestamp}-of-{screen_name}.jpg")
                
                # 计算当前截图的哈希值
                current_hash = imagehash.phash(img)
                
                # 检查当前截图与前一次截图的哈希值是否相似
                if screen_name in previous_hashes and current_hash - previous_hashes[screen_name] < threshold:  # 修改：使用 threshold 参数
                    print(f"Screenshot for {screen_name} is similar to the previous one. Skipping.")
                    os.remove(temp_filename)
                    # 记录跳过的截图
                    worklog.write(f"{timestamp} - {screen_name} - Skipped (similar to previous)\n")
                    continue
                
                # 更新前一次截图的哈希值
                previous_hashes[screen_name] = current_hash
                
                # 准备元数据
                metadata = {
                    "timestamp": timestamp,
                    "active_window": window_title,
                    "screen_name": screen_name
                }
                
                # 创建 EXIF 数据
                exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = json.dumps(metadata).encode()

                exif_bytes = piexif.dump(exif_dict)
                
                img.save(jpeg_filename, format="JPEG", quality=85, exif=exif_bytes)

            # 删除临时 PNG 文件
            os.remove(temp_filename)

            # 添加 JPEG 文件到截图列表
            screenshots.append(jpeg_filename)
            # 记录成功的截图
            worklog.write(f"{timestamp} - {screen_name} - Saved\n")

    return screenshots


def is_screen_locked():
    session_dict = CGSessionCopyCurrentDictionary()
    if session_dict:
        screen_locked = session_dict.get('CGSSessionScreenIsLocked', 0)
        return bool(screen_locked)
    return False


def main():
    parser = argparse.ArgumentParser(description="Screen Recorder")
    parser.add_argument("--threshold", type=int, default=3, help="Threshold for image similarity")  # 新增：添加 threshold 参数
    args = parser.parse_args()

    previous_hashes = {}  # 新增：存储前一次截图的哈希值
    while True:
        try:
            if not is_screen_locked():
                screenshot_files = take_screenshot(previous_hashes, args.threshold)  # 修改：传递 threshold 参数
                for screenshot_file in screenshot_files:
                    print(f"Screenshot taken: {screenshot_file}")
            else:
                print("Screen is locked. Skipping screenshot.")
        except Exception as e:
            print(f"An error occurred: {str(e)}. Skipping this iteration.")
        
        time.sleep(5)  # 等待 5 秒


if __name__ == "__main__":
    main()