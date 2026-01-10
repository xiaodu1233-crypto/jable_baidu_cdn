import asyncio
import pathlib
import re
import subprocess
import time
from zoneinfo import reset_tzpath
import glob
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


def merge_and_resplit(ts_dir, output_mp4="merged.mp4", segment_time = 130):
    # 1. 获取并自然排序
    files = glob.glob(os.path.join(ts_dir, "*.ts"))
    files.sort(key=lambda f: int(re.search(r'\d+', os.path.basename(f)).group()))

    if not files:
        print("❌ 错误：未找到分片")
        return

    # 2. 绕过 FFmpeg Concat，使用 Linux cat 二进制合并
    # 这种方式对 1000+ 分片非常友好，不会溢出
    combined_ts = "combined_all.ts"
    print(f"🔗 正在使用二进制流合并 {len(files)} 个分片...")

    # 构造 cat 命令：cat file1.ts file2.ts ... > combined_all.ts
    # 如果文件太多导致命令行长度超限，我们分批写入
    with open(combined_ts, 'wb') as outfile:
        for filename in files:
            with open(filename, 'rb') as infile:
                outfile.write(infile.read())

        # 3. 按时间重新切片
        print(f"✂️ 正在按时间（{segment_time}s）进行二次切片...")
        split_cmd = [
            "ffmpeg", "-y",
            "-i", combined_ts,  # 输入合并后的 TS
            "-c", "copy",  # 无损拷贝
            "-map", "0",
            "-f", "segment",
            "-segment_time", str(segment_time),  # 【此处已换回时间参数】
            "-reset_timestamps", "1",
            "upload_%03d.ts"  # 生成新的上传片段
        ]
    try:
        subprocess.run(split_cmd, check=True)
        print("✅ 成功生成 45MB 规范切片")
    finally:
        # 清理那个巨大的临时合并文件
        if os.path.exists(combined_ts):
            os.remove(combined_ts)


# 调用示例


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
        if item.startswith('ok'):
            print(pathlib.Path(item).is_dir())
        print(item)

    path = pathlib.Path(input_file)
    if path.is_dir():
        print("目录")
        for item in path.iterdir():
            if item.is_dir():
                merge_and_resplit(item)
                break
    else:
        print("文件")



if __name__ == "__main__":
    urtl = 'https://gmas-clena.mushroomtrack.com/hls/QkTlFjb1nCtDBjWNsIbkQg/1768049370/35000/35652/35652.m3u8'
    # urtl = 'https://kumak-clonser.mushroomtrack.com/hls/PFzMIjWSX16Psbsa2N1tHw/1768043344/48000/48168/48168.m3u8'
    save_name = 'ok'
    link_name = 'N_m3u8DL-RE'
    if os.getenv('GITHUB_ACTIONS') == 'true':
        link_name = './N_m3u8DL-RE'


    # "--tmp-dir", "./temp",  # 临时目录存 TS 片段
    # "--del-after-done", "true",

    command = [
        link_name,
        urtl,
        "--save-name", "ok",
        "--check-segments-count", "false"
    ]
    subprocess.run(command)

    time.sleep(2)

    split_video_by_time(save_name)

    path = pathlib.Path(save_name)
    file_name = 'finish.m3u8'
    print(f'file_name, {file_name}')

    time.sleep(2)

    #
    my_files = []
    for item in path.joinpath('0____').glob('*.ts'):
        my_files.append(item)
    if len(my_files):
        asyncio.run(main(my_files, file_name))