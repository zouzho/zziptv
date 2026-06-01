import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

# 配置参数
OUTPUT_DIR = "output"          # 输出目录
OUTPUT_FILE = "live_sources.m3u"  # 输出文件名
MAX_SOURCES_PER_CHANNEL = 5   # 每个频道保留的最快源数量
TIMEOUT = 5                   # 连接和读取超时时间（秒）
TEST_SIZE = 1024 * 75        # 测速下载的字节数 (512KB --> 75KB)
MAX_WORKERS = 50              # 并发线程数

def fetch_live_sources():
    """
    从公开的直播源仓库获取最新的国内电视直播源
    这里使用著名的开源直播源仓库 IPTV 的 API
    """
    print("正在从远程仓库获取最新直播源...")
    urls = [
        #"https://t.freetv.fun/m3u/playlist_original.m3u"
        #"https://t.freetv.fun/m3u/playlist_all.m3u",
        #"https://t.freetv.fun/m3u/playlist_ipv6.m3u",
        #"https://iptv-org.github.io/iptv/countries/cn.m3u",
        "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"
    ]
    
    m3u_content = ""
    for url in urls:
        try:
            print("开始解析：" + url)
            response = requests.get(url, timeout=10)            
            print("response.text : " + response.text)
            if response.status_code == 200:
                m3u_content += response.text + "\n"
                print(f"共获取直播源{len(m3u_content)} 个" + url)
        except Exception as e:
            print(f"获取 {url} 失败: {e}")
            
    if not m3u_content:
        print("未能获取任何直播源数据。")
        return {}
        
    return parse_m3u(m3u_content)

def parse_m3u(content):
    """
    解析 M3U 内容，提取频道名和对应的 URL
    """
    channels = {}
    lines = content.strip().split('\n')
    current_channel_name = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('#EXTINF'):
            # 提取频道名称，通常在逗号后面
            match = re.search(r',(.+)$', line)
            if match:
                # 清理频道名，去除画质标签等冗余信息，统一归类
                raw_name = match.group(1).strip()
                current_channel_name = re.sub(r'[（(].*?[）)]|高清|HD|hd|4K|超清', '', raw_name).strip()
        elif line.startswith('http'):
            if current_channel_name:
                if current_channel_name not in channels:
                    channels[current_channel_name] = []
                channels[current_channel_name].append(line)
                current_channel_name = None
                
    return channels

def test_speed(url):
    """
    测试单个直播源的可用性和下载速度
    返回: (url, 速度KB/s, 状态码) 如果失败则速度为0
    """
    try:
        start_time = time.time()
        # 使用 stream=True 以便在不下载整个文件的情况下测速
        with requests.get(url, stream=True, timeout=TIMEOUT, allow_redirects=True) as response:
            if response.status_code != 200:
                return url, 0, response.status_code
            
            # 检查是否为视频流
            content_type = response.headers.get('Content-Type', '')
            if 'video' not in content_type and 'octet-stream' not in content_type:
                return url, 0, 404
                
            downloaded = 0
            for chunk in response.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                # 下载达到测试大小或超时即停止
                if downloaded >= TEST_SIZE:
                    break
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            if elapsed > 0:
                speed_kbps = (downloaded / 1024) / elapsed
                return url, speed_kbps, 200
            return url, 0, 200
            
    except requests.exceptions.RequestException:
        return url, 0, 0
    except Exception:
        return url, 0, 0

def process_channels(channels):
    """
    多线程处理所有频道：测速、排序、筛选
    """
    result_channels = {}
    total_channels = len(channels)
    
    for idx, (channel_name, urls) in enumerate(channels.items(), 1):
        print(f"正在处理 [{idx}/{total_channels}]: {channel_name} (共 {len(urls)} 个源)")
        
        unique_urls = list(set(urls)) # 去重
        valid_sources = []
        
        # 使用线程池并发测速
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_url = {executor.submit(test_speed, url): url for url in unique_urls}
            for future in as_completed(future_to_url):
                url, speed, status = future.result()
                print(f"实时测速 url: {url} / speed: {speed}")
                if speed > 0: # 仅保留可用且测到速度的源
                    valid_sources.append((url, speed))
        
        # 按速度降序排序
        valid_sources.sort(key=lambda x: x[1], reverse=True)

        print(f"有效源个数：{len(valid_sources)}")
        
        # 保留前 N 个最快的源
        result_channels[channel_name] = valid_sources[:MAX_SOURCES_PER_CHANNEL]
        
    return result_channels

def generate_m3u(result_channels):
    """
    生成 M3U 文件并保存到指定目录
    """
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    filepath = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('#EXTM3U\n')
        for channel_name, sources in result_channels.items():
            print("channel_name: " + channel_name + " / sources: " + sources)
            if not sources:
                continue
            for url, speed in sources:
                speed_str = f"{speed:.2f}"
                # 在频道名后加上测速信息方便查看
                f.write(f'#EXTINF:-1 group-title="国内直播",{channel_name} ({speed_str}KB/s)\n')
                f.write(f'{url}\n')
                
    print(f"\n处理完成！M3U文件已保存至: {os.path.abspath(filepath)}")

def main():
    # 1. 获取直播源
    print("开始拉取并解析直播源 ... fetch_live_sources")
    channels = fetch_live_sources()
    if not channels:
        return
        
    print(f"共获取到 {len(channels)} 个频道分类，开始测速筛选...\n")
    
    # 2. 测速与筛选
    result_channels = process_channels(channels)
    
    # 3. 生成文件
    generate_m3u(result_channels)

if __name__ == "__main__":
    main()
