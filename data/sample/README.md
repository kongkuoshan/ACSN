# data/sample — 合成演示数据 (SYNTHETIC / 匿名)

**这里的全部内容都是程序合成的假数据，不对应任何真实机构、学者或论文。**
本目录存在的唯一目的，是让任何人在不接触真实机构数据的前提下复现完整流水线。

| 文件 | 对应流水线阶段 |
|------|----------------|
| `U1_SYNTHETIC.json` | Step 0 抓取产物 (结构与 OpenAlex `/works` 返回一致) |
| `0_原始导师名单_SYNTHETIC.xlsx` | Step 0 作者画像匹配的输入名单 |

数据由 `scripts/generate_sample_data.py` 以固定随机种子生成，可完全复现：

```bash
python scripts/generate_sample_data.py
```

一条命令跑通 Step 1 → Step 5 (离线，不需要联网 / Neo4j / HuggingFace 模型)：

```bash
python scripts/run_sample_pipeline.py
```

**映射表不在这里，而是由流水线自己生成**：`run_sample_pipeline.py` 把 Step 3 的
SBERT 编码器换成按合成真值分组的确定性编码器（因此不必下载 500MB 模型），
然后调用流水线**自己的** `build_cluster_mappings()` 生成簇模板，再按同一份真值
自动填写标准名称列，写出到 `data/sample/_run/`。这样「Step 3 出模板 → Step 4
读表」这条契约路径在演示里是真的被走了一遍，而不是拿一张手填的表糊过去。

真实使用时唯一的变化是：编码器换成 `paraphrase-multilingual-MiniLM-L12-v2`，
标准名称列由人工 (或 Step 3.5 的 LLM 预填) 填写。

### 演示数据里能看到什么

三个合成课题组各写了 3 种脏写法 (缩写 / 邮箱 / 中英混排 / 带邮编国名)，清洗后得到
9 条不同的机构串。Step 3 把它们聚成 3 簇，每簇选一个「排头兵」，Step 4 再坍缩成
3 个标准名 —— 跑完可以打开 `_run/1_机构映射表.xlsx` 对照簇编号与变体数。

进度条走 stderr，不影响产物正确性。
