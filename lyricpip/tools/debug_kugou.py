# python tools/debug_kugou.py "Eminem" "Talkin 2 Myself" 240
import json
import sys

import requests

from ..lyrics.matching import score
from ..models import TrackInfo

artist, title = sys.argv[1], sys.argv[2]
dur = float(sys.argv[3]) if len(sys.argv) > 3 else None
t = TrackInfo(title, artist, duration=dur)

r = requests.get(
    "https://mobileservice.kugou.com/api/v3/search/song",
    timeout=8,
    params={
        "format": "json",
        "keyword": f"{artist} {title}",
        "page": 1,
        "pagesize": 8,
        "showtype": 1,
    },
)
infos = r.json()["data"]["info"]
for i in infos:
    s = score(t, i["songname"], i["singername"], i.get("duration"))
    print(
        f"{s:.2f}  {i['songname']!r} / {i['singername']!r}  {i.get('duration')}s  hash={i['hash'][:8]}"
    )

# What does the lyric-candidate step return for the top-scoring hit?
top = max(
    infos, key=lambda i: score(t, i["songname"], i["singername"], i.get("duration"))
)
r = requests.get(
    "https://lyrics.kugou.com/search",
    timeout=8,
    params={
        "ver": 1,
        "man": "yes",
        "client": "pc",
        "hash": top["hash"],
        "keyword": f"{top['singername']} - {top['songname']}",
        "duration": int((top.get("duration") or 0) * 1000),
    },
)
print(json.dumps(r.json().get("candidates"), indent=1, ensure_ascii=False)[:1500])
