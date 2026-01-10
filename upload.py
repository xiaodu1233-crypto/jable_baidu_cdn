# 百度cdn

import json
import os.path
import time
from pathlib import Path

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Locator
import playwright
import asyncio

from aiofiles import open

sep3 = asyncio.Semaphore(5)
err = 0
base_path = r'./ok/0____'
err_list = []


async def upload(path: str, page, img_Btn, i):
    try:

        async with page.expect_file_chooser() as fc_info:
            await img_Btn.click(timeout=1111111)
        file_chooser = await fc_info.value
        # print(path)
        await file_chooser.set_files(path)
        if i < 22:
            await asyncio.sleep(0.2)
    except Exception as e:
        print('1111')
        print(e)
        pass
        # print(e)


sep = asyncio.Semaphore(16)


async def safe_get_url(page, img_Btn, path, i):
    async with sep:
        return await get_url(page, img_Btn, path, i)


async def get_url(page, img_Btn, path, i):
    await upload(path, page, img_Btn, i)
    return 'ok'


async def main():

    await ts_png(base_path)

    start = time.perf_counter()

    async with async_playwright() as p:
        chrome = p.chromium
        browser = await chrome.launch(headless=False, devtools=True)
        page = await browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36 Edg/89.0.774.54", )

        finish_upload = []

        m3_path = Path(base_path)
        lens = []
        for i in m3_path.glob('*.png'):
            lens.append(i)


        print(len(lens))

        async def save_to_m3u8(file_urls, output_path=base_path.split(os.sep)[0] + '.m3u8', default_duration=10.0):
            """
            将 ts 文件 URL 列表保存为 m3u8 播放列表

            :param file_urls: List[str] - 已上传的 .ts 文件完整 URL 列表
            :param output_path: str - 输出的 m3u8 文件路径
            :param default_duration: float - 每个片段的默认时长（秒）
            """
            print('开始保存')
            async with open(Path(base_path).parent.parent.joinpath(output_path), "w",
                      encoding="utf-8") as f:
                await f.write("#EXTM3U\n")
                await f.write("#EXT-X-VERSION:3\n")
                await f.write(f"#EXT-X-TARGETDURATION:{int(default_duration) + 1}\n")  # 必须 ≥ 最大片段时长
                await f.write("#EXT-X-MEDIA-SEQUENCE:0\n")
                await f.write("\n")

                for url in file_urls:
                    if url:  # 跳过 None 或空
                        await f.write(f"#EXTINF:{default_duration:.3f},\n")
                        await f.write(f"{url}\n")

                await f.write("#EXT-X-ENDLIST\n")

            print(f"✅ M3U8 playlist saved to: {output_path}")

            end = time.perf_counter()
            print(f"✅ 耗时: {end - start:.2f}s")

        async def response_handler(response):
            global err
            if 'https://chat.baidu.com/aichat/api/file/upload' in response.url:

                try:

                    k = await page.locator('//div[@class="ai-chat-input-file-delete"]').all()

                    for o in k:
                        await o.locator('..').hover(timeout=1000)
                        await o.wait_for(state="visible", timeout=1000)
                        await o.click(timeout=1000)
                except Exception as e:
                    pass
                    # print(e)

                result = await response.json()
                post_data = json.loads(response.request.post_data)
                if result['status'] == 0 and result['data'] and post_data['name']:
                    url = result['data']['file_url']
                    name = post_data['name']
                    # print(name, url)
                    finish_upload.append({'name': name, 'url': url})
                    print(len(finish_upload), err, len(err_list))
                    if name in err_list:
                        err_list.remove(name)
                        err = err - 1
                else:

                    print('error', result)
                    name = post_data['name']
                    # err_list.append(name)

                    if name in err_list:
                        err = err + 1
                    # retry1
                    else:
                        img_Btn = page.locator('//*[@class="tool-item_1e6GD "]').last
                        asyncio.create_task(safe_get_url(page, img_Btn, base_path + os.sep+ name, 111))
                        err_list.append(name)

                if len(finish_upload) >= (len(lens) - len(err_list) - 1):
                    # await page.wait_for_load_state('networkidle')
                    print(len(finish_upload))
                    print('总个数')
                    sorted_filenames = sorted(finish_upload, key=lambda x: int(x['name'].split('_')[1]))
                    datas = []
                    for item in sorted_filenames:
                        datas.append(item['url'])
                    print('排序完毕')
                    await save_to_m3u8(datas)

        page.on('response', response_handler)

        result = await page.goto("https://www.baidu.com/")

        img_Btn = page.locator('//*[@class="tool-item_1e6GD "]').last

        tasks = []

        for i in range(0, len(lens)):
            img_path = rf'{base_path}{os.sep}tan_{i}_lang.png'
            # print(img_path)
            task = asyncio.create_task(safe_get_url(page, img_Btn, img_path, i))
            tasks.append(task)

        # print(tasks)
        results = await asyncio.gather(*tasks)
        await asyncio.sleep(400)


async def ts_png(dir_path):


    ts_path = Path(dir_path)
    # print(ts_path)

    png_path = Path(dir_path).parent.parent.joinpath('hide.png')

    ts_lists = ts_path.glob('*.ts')
    for index, ts_file in enumerate(ts_lists):
        print(png_path)
        await embed_ts_in_png(png_path, ts_file, ts_path.joinpath(f'tan_{index}_lang.png'))


async def embed_ts_in_png(png_path, ts_path, output_path):
    """
    将 TS 文件追加到 PNG 文件末尾，生成一个可伪装的文件。

    - 改后缀为 .png → 显示图片
    - 改后缀为 .ts → 可用 ffplay/VLC 播放（部分播放器需跳过前N字节）
    """
    async with open(png_path, 'rb') as f:
        png_data = await f.read()

    async with open(ts_path, 'rb') as f:
        ts_data = await f.read()

    async with open(output_path, 'wb') as f:
        await f.write(png_data)  # 先写入合法 PNG
        await f.write(ts_data)  # 再追加 TS 数据

    print(f"✅ 已生成: {output_path}")
    print(f"   PNG size: {len(png_data)} bytes")
    print(f"   TS size:  {len(ts_data)} bytes")

    if ts_path.exists():
        ts_path.unlink()


if __name__ == "__main__":
    asyncio.run(main())