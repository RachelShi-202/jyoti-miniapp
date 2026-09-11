"""Synchronize the local development URL with the active Mac network."""
import re,subprocess,ipaddress
from pathlib import Path

def sync():
 config=Path(__file__).resolve().parents[1]/'miniprogram/config.js'
 text=config.read_text()
 match=re.search(r"'http://([\d.]+):8000'",text)
 if not match or not ipaddress.ip_address(match[1]).is_private:
  return None  # Never overwrite a production HTTPS endpoint.
 output=subprocess.check_output(['/sbin/ifconfig'],text=True)
 candidates=[]
 for block in re.split(r'(?=^\w[^\n]*: flags=)',output,flags=re.M):
  if not re.match(r'en\d+:',block) or 'status: active' not in block:continue
  found=re.search(r'\binet (\d+\.\d+\.\d+\.\d+) ',block)
  if found and ipaddress.ip_address(found[1]).is_private:candidates.append(found[1])
 if len(set(candidates))!=1:
  raise RuntimeError('无法确定唯一局域网地址，请检查 Wi-Fi 或网线连接。')
 address=candidates[0]
 config.write_text(text[:match.start(1)]+address+text[match.end(1):])
 print('小程序局域网地址已同步：http://'+address+':8000；请重新编译并扫码。')
 return address
if __name__=='__main__':sync()
