import asyncio
# from redis.asyncio import Redis
import subprocess
from pathlib import Path


async def main():


    url = 'https://gmas-clena.mushroomtrack.com/hls/Lu2ofmnUsErNx6I8yzdGug/1767970860/35000/35390/35390.m3u8'
    res = subprocess.run(['N_m3u8DL-RE', url, '--skip-merge', 'True', '--thread-count', '50'], encoding='utf-8')
    print(res)
    name = url.split('/')[-2]
    for i in Path(__file__).parent.glob(pattern=f'{name}*'):
        if i.is_dir():
            print(i)
        else:
            print(i)
    pass

if __name__ == "__main__":


    asyncio.run(main())