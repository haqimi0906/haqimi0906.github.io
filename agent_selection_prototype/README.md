# 选品助手 · 真原型（作品集案例四）

把《案例一｜AI 选品排期助手》从概念设计落地为**可运行的 tool-use Agent**。
基于公开/合成零售数据集，**不涉及任何公司机密**（数据隔离原则）。

> ✅ 状态：已构建并通过 mock 模式验证（见 `demo_output.txt`）。真实 LLM 模式需自备 key。

## 目录
- `generate_data.py`：生成合成零售数据集 `data/sample_data.csv`
- `agent.py`：选品助手 Agent（工具 + 路由 + mock/LLM 双模式）
- `data/sample_data.csv`：合成数据（由 generate_data.py 生成）

## 快速开始
```bash
# 1) 生成数据（首次运行）
python generate_data.py

# 2) 跑内置示例（mock 模式，无需 key，可直接录屏）
python agent.py --demo

# 3) 交互模式
python agent.py
```

## 两种模式
- **mock 模式（默认）**：关键词路由，零依赖、零 key 即可演示核心 loop。
- **真实 LLM 模式**：设置环境变量后，用 OpenAI 兼容接口做意图路由。
  ```bash
  export LLM_API_KEY=你的key
  export LLM_BASE_URL=https://api.deepseek.com/v1   # 可换通义/OpenAI
  export LLM_MODEL=deepseek-chat
  python agent.py --demo
  ```

## 能力（MVP）
- 品类健康度诊断（GMV/订单/毛利/退货/曝光转化）
- 招品清单生成（最近周期高 GMV 低退货）
- 异常品复盘（双负：GMV 降且曝光转化降）
- 销售概览

## 架构
```
用户(中文) → 路由(LLM或mock) → 工具(pandas/csv分析) → 自然语言结论
记忆：会话上下文（当前品类/周期）  |  护栏：口径校验 + mock 兜底
```
详见上层目录 `选品助手真原型_PRD.md`。
