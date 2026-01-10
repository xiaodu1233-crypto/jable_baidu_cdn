import asyncio
import pathlib
import re
import subprocess
import time

import aiohttp
import os
# from aiofiles import open
from aiohttp import ClientTimeout

# --- 配置区 ---
BOT_TOKEN = '8462879327:AAGzeC1ydXRaMN-4sog7ebFtL4zSoOGE5Es'
CHAT_ID = '6554928796'
WORKER_URL = 'https://tele.xiaodu1234.xyz'
MAX_CONCURRENT_TASKS = 3  # 限制同时上传的文件数量，建议 2-5 之间

LOCAL_PROXY = "http://127.0.0.1:10808"

index = 0
class TelegramUploader:
    def __init__(self, token, chat_id, worker_url, max_tasks):
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.worker_url = worker_url
        # 核心：信号量，用于控制并发


        # 自动判断环境：如果在 GitHub Actions 运行，则不使用代理
        if os.getenv('GITHUB_ACTIONS') == 'true':
            self.proxy = None
            self.semaphore = asyncio.Semaphore(5)
            print("🚀 检测到运行环境：GitHub Actions (不使用代理)")
        else:
            self.proxy = LOCAL_PROXY
            self.semaphore = asyncio.Semaphore(max_tasks)
            print(f"🏠 检测到运行环境：本地 (使用代理: {self.proxy})")

    async def upload_single_file(self, session, file_path):
        global index
        """带并发控制的上传任务"""
        async with self.semaphore:  # 只有拿到“许可证”的任务才能继续
            url = f"{self.api_url}/sendDocument"

            data = aiohttp.FormData()
            data.add_field('chat_id', str(self.chat_id))
            data.add_field('document', open(file_path, 'rb'), filename=os.path.basename(file_path))

            try:
                # 模拟一点微小的间隔，防止瞬时并发过高
                await asyncio.sleep(0.1)


                async with session.post(url, data=data, proxy= self.proxy) as response:
                    result = await response.json()

                    if response.status == 429:  # 触发 Telegram 限速
                        retry_after = result.get('parameters', {}).get('retry_after', 10)
                        print(f"⚠️ 被限速了！需等待 {retry_after} 秒")
                        return None

                    if result.get('ok'):
                        print(result)
                        file_id = result['result']['document']['file_id']
                        file_name2 = result['result']['document']['file_name']
                        permanent_link = f"{self.worker_url}/?file_id={file_id}"
                        print(f"✅ 成功: {os.path.basename(file_path)}")
                        index = index + 1
                        await asyncio.sleep(1)
                        print(f'当前下载了 {index}')
                        return file_name2, permanent_link,
                    else:
                        print(f"❌ 失败: {os.path.basename(file_path)} - {result.get('description')}")
                        return None
            except Exception as e:
                print(f"--- ⚠️ 错误: {e}")
                return None

    async def upload_batch(self, file_paths):
        timeout = ClientTimeout(total=300, connect=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            tasks = [self.upload_single_file(session, fp) for fp in file_paths]
            return await asyncio.gather(*tasks)


async def generate_m3u8(file_list, duration=10, output_file=''):
    """
    file_list: 包含 (文件名, URL) 的元组列表
    """

    # --- 核心：自然排序 (Natural Sort) ---
    # 使用正则提取文件名中的数字进行排序，防止 "part10.ts" 排在 "part2.ts" 前面
    def natural_key(string_):
        return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', string_[0])]

    # 按照文件名进行自然排序
    sorted_list = sorted(file_list, key=natural_key)

    m3u8_lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:3",
        f"#EXT-X-TARGETDURATION:{duration + 2}",  # 通常比实际时长多一点
        "#EXT-X-MEDIA-SEQUENCE:0",
    ]

    for file_name, file_url in sorted_list:
        m3u8_lines.append(f"#EXTINF:{duration}.0,")
        m3u8_lines.append(file_url)

    m3u8_lines.append("#EXT-X-ENDLIST")

    with open(output_file, "w") as f:
        f.write("\n".join(m3u8_lines))


# --- 执行区 ---
async def main(my_files, file_name):
    # 假设你有 100 个文件，程序现在也会有序地 3 个 3 个地传

    # return
    uploader = TelegramUploader(BOT_TOKEN, CHAT_ID, WORKER_URL, MAX_CONCURRENT_TASKS)
    print(f"🚀 开始批量上传，当前并发限制: {MAX_CONCURRENT_TASKS}")

    print(my_files)
    # return

    links = await uploader.upload_batch(my_files)
    links = [l for l in links if l]
    print(f"\n✨ 完成！成功获取 {len([l for l in links if l])} 个链接。")
    print(links)
    await generate_m3u8(links, output_file = file_name)
    final_m3u8_id = await uploader.upload_single_file(aiohttp.ClientSession(), file_name)
    print(f"🎬 你的在线播放地址: {final_m3u8_id[1]}")


def split_video_by_time(input_file , segment_time=130):

    """
    使用 FFmpeg 将视频按时间切割为 TS 片段
    :param input_file: 输入视频路径 (如 'movie.mp4')
    :param segment_time: 每段时长（秒），建议 120-150s 对应 50MB 左右
    """
    # 确保输出文件名格式，例如 out000.ts, out001.ts
    path = "."
    files_and_dirs = os.listdir(path)

    for item in files_and_dirs:
        print(item)


    output_template = "out%03d.ts"
    input_file = input_file + '.mp4'

    # if os.getenv('GITHUB_ACTIONS') == 'true':
    #     input_file = f'.{os.sep}' + input_file

    # 构建命令列表
    command = [
        "ffmpeg",
        "-i", input_file,  # 输入文件
        "-c", "copy",  # 直接拷贝编码流（极速）
        "-map", "0",  # 包含所有流（音轨、字幕）
        "-f", "segment",  # 开启切片模式
        "-segment_time", str(segment_time),  # 切片时间
        "-reset_timestamps", "1",  # 每个切片时间戳清零
        output_template  # 输出命名规则
    ]

    try:
        print(f"🚀 开始切割视频: {input_file} ...")
        # run 会等待命令执行完成
        # capture_output=True 可以捕获错误信息
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print("✅ 视频切割完成！")

    except subprocess.CalledProcessError as e:
        print(f"❌ FFmpeg 出错啦！错误信息：\n{e.stderr}")
    except FileNotFoundError:
        print("❌ 系统找不到 ffmpeg，请检查是否安装并添加到了环境变量。")

if __name__ == "__main__":
    urtl = 'https://kumak-clonser.mushroomtrack.com/hls/PFzMIjWSX16Psbsa2N1tHw/1768043344/48000/48168/48168.m3u8'
    save_name = 'ok'
    link_name = 'N_m3u8DL-RE'
    if os.getenv('GITHUB_ACTIONS') == 'true':
        link_name = './N_m3u8DL-RE'

    command = [
        link_name,
        urtl,
        "--save-name", "ok",
        # "--tmp-dir", "./temp",  # 临时目录存 TS 片段
        # "--del-after-done", "true",
        "--check-segments-count", "false"# 完成后不删除
    ]
    subprocess.run(command)

    time.sleep(2)

    split_video_by_time(save_name)


    path = pathlib.Path(save_name)
    file_name = 'finish.m3u8'
    print(f'file_name, {file_name}')

    time.sleep(5)

    #
    my_files = []
    for item in path.glob('*.ts'):
        my_files.append(item)
    if len(my_files):
        asyncio.run(main(my_files, file_name))