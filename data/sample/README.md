# data/sample — 合成演示数据 (SYNTHETIC / 匿名)

**这里的全部内容都是程序合成的假数据，不对应任何真实机构、学者或论文。**
本目录存在的唯一目的，是让任何人在不接触真实机构数据的前提下复现完整流水线。

| 文件 | 对应流水线阶段 |
|------|----------------|
| `U1_SYNTHETIC.json` | Step 0 抓取产物 (结构与 OpenAlex `/works` 返回一致) |
| `0_原始导师名单_SYNTHETIC.xlsx` | Step 0 作者画像匹配的输入名单 |
| `1_机构映射表_SYNTHETIC_已填.xlsx` | Step 4 机构映射 (已填好，跳过人工填写) |
| `2_研究领域映射表_SYNTHETIC_已填.xlsx` | Step 4 领域映射 (已填好) |

数据由 `scripts/generate_sample_data.py` 以固定随机种子生成，可完全复现：

```bash
python scripts/generate_sample_data.py
```

一条命令跑通 Step 1 → Step 5 (离线，不需要联网 / Neo4j / HuggingFace 模型)：

```bash
python scripts/run_sample_pipeline.py
```

> 说明：演示流程**跳过 Step 3 的 SBERT 语义聚类**（样本量太小，聚类的意义不大），
> 改用恒等映射 + 预填映射表，从而不必下载 500MB 模型。
> 真实使用时 Step 3 会调用 `paraphrase-multilingual-MiniLM-L12-v2` 自动生成排头兵。

### 运行时会看到的告警（属正常现象）

跑演示时会打印若干条 `⚠️ 重名冲突: ...都映射为...`。这是**预期行为**：
演示数据故意让同一个课题组的 3–4 种脏写法都收敛到同一个标准名，
Step 4 发现多个「排头兵」指向同一标准名时就会提示合并。

在真实数据上这类告警值得人工核对（它意味着两个不同实体被合并了）；
在演示数据里它正是「坍缩生效」的证据。
进度条与告警走 stderr，不影响产物正确性。
