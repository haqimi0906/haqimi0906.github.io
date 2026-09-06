"""选品助手 · 真原型（tool-use Agent，零依赖，可离线 demo）。

模式：
  - 默认 mock 模式：关键词路由，无需任何 API key 即可演示。
  - 真实 LLM 模式：设置环境变量 LLM_API_KEY 后，用 OpenAI 兼容接口做意图路由
    （默认 DeepSeek，可用 LLM_BASE_URL / LLM_MODEL 切换为通义/OpenAI 等）。

运行：
  python agent.py            # 交互模式
  python agent.py --demo     # 跑内置示例问题（便于验证/录屏）
"""
import os
import sys
import csv

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data", "sample_data.csv")
CATS = ["生鲜", "日用", "家电"]


def load():
    with open(DATA, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_f(x):
    return float(x)


WEEKS = sorted({r["week"] for r in load()})


def detect_cat(text):
    for c in CATS:
        if c in text:
            return c
    return None


def detect_festival(text):
    for f in ["开学季", "年货节", "618", "双11", "双十一", "中秋", "春节", "国庆"]:
        if f in text:
            return f
    return None


PRODUCT_KEYS = [
    ("叶菜", "叶菜包邮装"), ("鲜奶", "冷链鲜奶"), ("水果", "时令水果"),
    ("海鲜", "冷冻海鲜"), ("净菜", "半成品净菜"), ("抽纸", "抽纸家庭装"),
    ("洗衣液", "洗衣液"), ("垃圾袋", "垃圾袋"), ("保鲜膜", "保鲜膜"),
    ("牙刷", "牙刷牙膏套装"), ("水壶", "电热水壶"), ("空气炸锅", "空气炸锅"),
    ("扫地", "扫地机器人"), ("加湿器", "加湿器"), ("电风扇", "电风扇"),
]


def detect_product(text):
    for k, n in PRODUCT_KEYS:
        if k in text:
            return n
    return None


# ---------------- 工具（Tools） ----------------
def diagnose(category=None, week=None):
    rows = load()
    if category:
        rows = [r for r in rows if r["category"] == category]
    if week:
        rows = [r for r in rows if r["week"] == week]
    by = {}
    for r in rows:
        c = r["category"]
        d = by.setdefault(c, {"gmv": 0, "orders": 0, "margin": [], "ret": [], "cvr": [], "n": 0})
        d["gmv"] += to_f(r["gmv"])
        d["orders"] += int(r["orders"])
        d["margin"].append(to_f(r["margin_rate"]))
        d["ret"].append(to_f(r["return_rate"]))
        d["cvr"].append(to_f(r["exposure_cvr"]))
        d["n"] += 1
    lines = []
    for c, d in by.items():
        am = sum(d["margin"]) / d["n"]
        ar = sum(d["ret"]) / d["n"]
        ac = sum(d["cvr"]) / d["n"]
        health = "健康" if ar < 0.06 and ac > 0.08 else ("关注" if ar < 0.09 else "预警")
        lines.append(f"· {c}：GMV {d['gmv']:,.0f}，订单 {d['orders']:,}，"
                     f"均价毛利 {am*100:.1f}%，退货率 {ar*100:.1f}%，"
                     f"曝光转化 {ac*100:.1f}% → {health}")
    return "品类健康度诊断：\n" + "\n".join(lines)


def recommend(category=None, festival=None):
    rows = load()
    if category:
        rows = [r for r in rows if r["category"] == category]
    latest = [r for r in rows if r["week"] == WEEKS[-1]]
    latest.sort(key=lambda r: to_f(r["gmv"]), reverse=True)
    top = latest[:5]
    note = f"（{festival}）" if festival else ""
    lines = [f"· {r['product_name']}：周GMV {to_f(r['gmv']):,.0f}，"
             f"退货率 {to_f(r['return_rate'])*100:.1f}%，"
             f"曝光转化 {to_f(r['exposure_cvr'])*100:.1f}%"
             for r in top]
    return (f"建议重点招商清单{note}（基于最近周期高GMV低退货）：\n"
            + "\n".join(lines))


def find_anomalies(week=None):
    rows = load()
    last, prev = WEEKS[-1], WEEKS[-2]
    cur = {r["product_id"]: r for r in rows if r["week"] == last}
    pre = {r["product_id"]: r for r in rows if r["week"] == prev}
    out = []
    for pid, r in cur.items():
        if pid in pre:
            gmv_drop = to_f(r["gmv"]) < to_f(pre[pid]["gmv"])
            cvr_drop = to_f(r["exposure_cvr"]) < to_f(pre[pid]["exposure_cvr"])
            if gmv_drop and cvr_drop:
                out.append(
                    f"· {r['product_name']}（{r['category']}）：GMV "
                    f"{to_f(pre[pid]['gmv']):,.0f}→{to_f(r['gmv']):,.0f}，"
                    f"曝光转化 {to_f(pre[pid]['exposure_cvr'])*100:.1f}%→"
                    f"{to_f(r['exposure_cvr'])*100:.1f}%（双负，建议替换/优化）")
    return "异常品复盘（双负：GMV降 且 曝光转化降）：\n" + (
        "\n".join(out) if out else "本周期未发现双负异常品。")


def query_sales(category=None, week=None):
    rows = load()
    if category:
        rows = [r for r in rows if r["category"] == category]
    if week:
        rows = [r for r in rows if r["week"] == week]
    rows = sorted(rows, key=lambda r: to_f(r["gmv"]), reverse=True)[:8]
    lines = [f"· {r['product_name']}（{r['week']}）：GMV {to_f(r['gmv']):,.0f}，"
             f"订单 {r['orders']}，退货 {to_f(r['return_rate'])*100:.1f}%"
             for r in rows]
    return "销售概览：\n" + "\n".join(lines)


# ---- 新增工具：对比 / 排行 / 单品 / 趋势 ----
def compare(text=""):
    cats = [c for c in CATS if c in text]
    use = cats if len(cats) >= 2 else CATS
    by = {}
    for r in load():
        c = r["category"]
        if c not in use:
            continue
        d = by.setdefault(c, {"gmv": 0, "margin": [], "ret": [], "cvr": [], "n": 0})
        d["gmv"] += to_f(r["gmv"])
        d["margin"].append(to_f(r["margin_rate"]))
        d["ret"].append(to_f(r["return_rate"]))
        d["cvr"].append(to_f(r["exposure_cvr"]))
        d["n"] += 1
    lines = []
    for c in use:
        d = by[c]
        am = sum(d["margin"]) / d["n"]
        ar = sum(d["ret"]) / d["n"]
        ac = sum(d["cvr"]) / d["n"]
        lines.append(f"· {c}：累计GMV {d['gmv']:,.0f}，均价毛利 {am*100:.1f}%，"
                     f"退货率 {ar*100:.1f}%，曝光转化 {ac*100:.1f}%")
    ranked = sorted(use, key=lambda c: by[c]["gmv"], reverse=True)
    return ("品类横向对比（累计口径）：\n" + "\n".join(lines)
            + f"\n\n小结：{ranked[0]} GMV 领先，{ranked[-1]} 相对偏弱。")


def rank(text=""):
    byp = {}
    for r in load():
        p = byp.setdefault(r["product_id"],
                           {"name": r["product_name"], "cat": r["category"],
                            "gmv": 0, "ret": []})
        p["gmv"] += to_f(r["gmv"])
        p["ret"].append(to_f(r["return_rate"]))
    weak = any(k in text for k in ["差", "垫底", "最弱", "低"])
    arr = sorted(byp.values(),
                 key=lambda p: p["gmv"], reverse=not weak)
    top = arr[:5]
    label = "表现最弱（GMV 最低）TOP5" if weak else "表现最强（GMV 最高）TOP5"
    lines = [f"· {p['name']}（{p['cat']}）：累计GMV {p['gmv']:,.0f}，"
             f"退货率 {sum(p['ret'])/len(p['ret'])*100:.1f}%"
             for p in top]
    return label + "：\n" + "\n".join(lines)


def product(name):
    rows = [r for r in load() if name in r["product_name"]]
    if not rows:
        return "没匹配到这个品，可以试试：空气炸锅 / 生鲜 / 抽纸 / 洗衣液 等关键词。"
    first = rows[0]
    gmv = [to_f(r["gmv"]) for r in rows]
    latest = to_f(rows[-1]["gmv"])
    prev = to_f(rows[-2]["gmv"])
    chg = (latest - prev) / prev * 100
    ar = sum(to_f(r["return_rate"]) for r in rows) / len(rows) * 100
    return (f"【{first['product_name']}｜{first['category']}】\n"
            f"· 近8周GMV区间：{min(gmv):,.0f} ~ {max(gmv):,.0f}\n"
            f"· 最近一周：{latest:,.0f}，环比 {chg:+.1f}%\n"
            f"· 平均退货率：{ar:.1f}%")


def trend(category=None):
    rows = load()
    if category:
        rows = [r for r in rows if r["category"] == category]
    by_week = {}
    for r in rows:
        by_week[r["week"]] = by_week.get(r["week"], 0) + to_f(r["gmv"])
    weeks = [w for w in WEEKS if w in by_week]
    series = [by_week[w] for w in weeks]
    first, last = series[0], series[-1]
    chg = (last - first) / first * 100
    bars = [f"{w}: {by_week[w]:,.0f}" for w in weeks]
    return ((f"{category+'品类' if category else '全站'}近8周GMV趋势：\n"
             + "\n".join(bars)
             + f"\n整体环比 {chg:+.1f}%")
            + ("（上行，供给可维持）" if chg >= 0 else "（下行，建议排查原因）"))


TOOLS = {
    "diagnose": diagnose,
    "recommend": recommend,
    "find_anomalies": find_anomalies,
    "query_sales": query_sales,
    "compare": compare,
    "rank": rank,
    "product": product,
    "trend": trend,
}


# ---------------- 措辞轮换（让 Mock 回答更自然） ----------------
def _pick(arr, seed):
    h = 0
    for ch in str(seed):
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return arr[h % len(arr)]


OPEN = {
    "diagnose": ["好的，我拉一下该品类的健康度数据：", "没问题，先给这个品类做个体检：",
                 "收到，这是品类维度的健康诊断："],
    "recommend": ["结合最近周期“高GMV+低退货”，我筛了一份招商重点：",
                  "按表现我帮你排了份招品清单：", "这是一份建议优先招商的清单："],
    "find_anomalies": ["我对比了最近两周，把“双负”异常品捞出来了：",
                       "复盘了一下，以下品出现 GMV 和转化同时下滑：", "异常诊断结果如下："],
    "query_sales": ["这是销售概况，按 GMV 排了序：", "给你拉一份销售概览：", "销售数据如下："],
    "compare": ["我把相关品类放在一起横向对比了：", "横向对比结果（累计口径）："],
    "rank": ["按你的口径，我做了个排行：", "排名结果如下："],
    "product": ["单品维度的数据我查了：", "这个品近8周的表现："],
    "trend": ["最近8周的趋势我列出来了：", "趋势概览："],
}
CLOSE = {
    "diagnose": ["下一步建议：对“预警”品类做供给侧排查，或点“招品清单”补货。"],
    "recommend": ["需要的话，我可以按某个节庆（如年货节/618）再筛一份。"],
    "find_anomalies": ["建议对双负品做替换或详情页/价格优化，再观察一周。"],
    "query_sales": ["想看某个品类或单品，直接告诉我名字就行。"],
    "compare": ["招品优先级建议结合毛利与退货率综合判断。"],
    "rank": ["要不要我反过来看“最弱”的一批，方便你做汰换？"],
    "product": ["需要我顺便看看它和同类品的横向对比吗？"],
    "trend": ["连续下行时，建议先定位是供给、价格还是流量问题。"],
}


def wrap(intent, body, seed):
    o = _pick(OPEN.get(intent, ["这是结果："]), seed)
    c = _pick(CLOSE.get(intent, ["需要换个口径再算一遍吗？"]), seed + "x")
    return o + "\n" + body + "\n\n" + c


# ---------------- 路由（Router） ----------------
def route_mock(text):
    cat = detect_cat(text)
    fest = detect_festival(text)
    prod = detect_product(text)
    if any(k in text for k in ["对比", "pk", "比一比", "哪个好", "哪个强", "哪个更",
                               "更好卖", "卖得好", "好卖", "区别", "横向", "比哪个"]):
        return {"intent": "compare", "name": "compare", "args": {"text": text}}
    if any(k in text for k in ["排行", "排名", "最畅销", "卖得最好", "卖最好",
                               "最差", "垫底", "最弱", "top", "榜单", "榜"]):
        return {"intent": "rank", "name": "rank", "args": {"text": text}}
    if prod and any(k in text for k in ["单品", "具体", "这个品", "某款", "查一下", "看看", "怎么样"]):
        return {"intent": "product", "name": "product", "args": {"name": prod}}
    if any(k in text for k in ["趋势", "走势", "变化", "增长", "这8周", "近8周", "每周", "环比"]):
        return {"intent": "trend", "name": "trend", "args": {"category": cat}}
    if any(k in text for k in ["异常", "复盘", "双负", "下滑", "下跌", "跌"]):
        return {"intent": "find_anomalies", "name": "find_anomalies", "args": {}}
    if any(k in text for k in ["招品", "清单", "推荐", "选品", "招商", "重点", "上什么", "该进", "补货"]):
        return {"intent": "recommend", "name": "recommend",
                "args": ({"category": cat, "festival": fest} if cat else {"festival": fest})}
    if any(k in text for k in ["诊断", "健康", "动销", "毛利", "退货", "怎么样", "如何", "表现", "好不好"]):
        return {"intent": "diagnose", "name": "diagnose",
                "args": ({"category": cat} if cat else {})}
    return {"intent": "query_sales", "name": "query_sales",
            "args": ({"category": cat} if cat else {})}


def route_llm(text):
    import urllib.request
    import json
    base = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
    key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "deepseek-chat")
    if not key:
        return None
    sys_prompt = (
        "你是选品助手路由。根据用户问题只返回 JSON，不要解释："
        '{"tool":"diagnose|recommend|find_anomalies|query_sales|compare|rank|product|trend",'
        '"category":"生鲜|日用|家电|null","festival":"null或节庆名"}')
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": sys_prompt},
                     {"role": "user", "content": text}],
        "temperature": 0,
    }).encode()
    req = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=20).read())
        c = resp["choices"][0]["message"]["content"]
        return json.loads(c)
    except Exception:
        return None


def answer(text):
    decision = route_llm(text)
    if decision and decision.get("tool") in TOOLS:
        args = {k: v for k, v in decision.items() if k != "tool"}
        args = {k: (None if v in ("null", "None") else v) for k, v in args.items()}
        try:
            return wrap(decision["tool"], TOOLS[decision["tool"]](**args), text)
        except Exception as e:
            return f"[LLM 路由执行出错] {e}"
    rt = route_mock(text)
    try:
        return wrap(rt["intent"], TOOLS[rt["name"]](**rt["args"]), text)
    except Exception as e:
        return f"[执行出错] {e}"


def demo():
    qs = [
        "帮我诊断一下生鲜品类的健康度",
        "给我一份开学季的招品清单",
        "复盘上周有哪些异常品",
        "日用品类最近销售怎么样",
        "生鲜和日用哪个更好卖",
        "哪些品卖得最好",
        "空气炸锅最近怎么样",
        "全站近8周销售趋势",
    ]
    for q in qs:
        print("\n用户：" + q)
        print(answer(q))


def cli():
    mode = "真实LLM" if os.environ.get("LLM_API_KEY") else "mock"
    print(f"选品助手原型（{mode} 模式，输入 exit 退出）")
    while True:
        try:
            q = input("你：")
        except EOFError:
            break
        if q.strip().lower() in ("exit", "quit", "退出"):
            break
        if not q.strip():
            continue
        print(answer(q))


if __name__ == "__main__":
    if "--demo" in sys.argv:
        demo()
    else:
        cli()
