import requests
import re


# 源地址
urls = [
    "https://raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv4.m3u",
    "https://raw.githubusercontent.com/vbskycn/iptv/refs/heads/master/tv/iptv6.m3u",
    "https://live.iptv-free.com/iptv/categories/general.m3u",
    "https://live.iptv-free.com/iptv/categories/movies.m3u"
]
# 输出文件名
OUTPUT_FILE = "iptv.m3u"


def update_m3u():
    try:
        all_text = ""
        for SOURCE_URL in urls:
            print(f"正在拉取: {SOURCE_URL}")
            response = requests.get(SOURCE_URL, timeout = 30)
            response.encoding = 'utf - 8'  # 强制UTF - 8防止乱码
            lines = response.text.split('\n')

            filtered_lines = ["#EXTM3U"]  # 头部必须保留

            # 遍历每一行寻找匹配项
            # 逻辑：M3U格式通常是两行一组：
            # Line 1: #EXTINF:-1 group - title="...", 频道名
            # Line 2: http://...

            for i in range(len(lines)):
                line = lines[i].strip()
                if line.startswith("#EXTINF"):
                    # 如果匹配，保留这一行（频道信息）
                    filtered_lines.append(line)
                    # 并且保留下一行（播放链接）
                    if i + 1 < len(lines):
                        url_line = lines[i + 1].strip()
                        filtered_lines.append(url_line)
            all_text += '\n'.join(filtered_lines) + '\n'

        # 写入文件
        with open(OUTPUT_FILE, "w", encoding="utf - 8") as f:
            f.write(all_text)

        print(f"更新成功！共筛选出 {len(all_text.splitlines()) // 2} 个频道。")

    except Exception as e:
        print(f"更新失败: {e}")
        exit(1)  # 报错退出，通知Action失败


if __name__ == "__main__":
    update_m3u()
