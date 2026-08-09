# RoomReceipt

[English](README.md) | [在线演示](https://kanadek.github.io/roomreceipt/) | [示例报告](https://kanadek.github.io/roomreceipt/demo/)

RoomReceipt 把入住和退租照片整理成完全离线、可检测篡改的证据包。它会保留原始图片字节，记录尺寸、EXIF 拍摄时间、时区是否存在、GPS 是否存在和 SHA-256；使用稳定视角名配对前后照片；生成打印友好的 HTML 报告；并提供可独立运行的目录和 ZIP 验证器。

它不是界面空壳。像素差异来自真实图片计算，验证结果来自真实文件字节。缺失、被修改、未登记、重名或带路径穿越风险的 ZIP 成员都会让验证失败。

## 它解决什么问题

[NSW Fair Trading](https://www.nsw.gov.au/housing-and-construction/rules/rental-property-condition-reports)、[Consumer Affairs Victoria](https://www.consumer.vic.gov.au/housing/renting/rent-bond-bills-and-condition-reports/condition-reports) 和 [英国政府租房清单](https://www.gov.uk/government/publications/how-to-rent/how-to-rent-the-checklist-for-renting-in-england) 都建议保存详细房屋状况报告、带日期的照片和双方副本。

现实中这些材料常常仍散落在手机相册和临时文档里。商业应用不少，但 2026 年 8 月的检索没有找到成熟的、同时具备离线前后配对、可移植字节验证和透明能力边界的开源项目。检索方法和竞品差异见 [docs/research.md](docs/research.md)。

## 快速开始

需要 Python 3.11 或更高版本，推荐使用 [`uv`](https://docs.astral.sh/uv/)。

```bash
uv tool install "git+https://github.com/KanadeK/roomreceipt.git@v0.1.0"
roomreceipt --version
```

从源码运行：

```bash
git clone https://github.com/KanadeK/roomreceipt.git
cd roomreceipt
uv sync --all-extras
uv run roomreceipt --version
```

运行完整合成示例：

```bash
uv run python scripts/generate_example_data.py --check
uv run python scripts/build_example.py --output build/bright-street
uv run roomreceipt verify build/bright-street/bright-street-demo.roomreceipt.zip
```

示例中的 8 张 JPEG 都由仓库脚本确定性生成，带固定 EXIF 时间，不代表真实人物、地址或租赁关系。

## 创建真实案例

```bash
roomreceipt init apartment-case \
  --title "Apartment move-in" \
  --property "14 Bright Street" \
  --unit "4B"

roomreceipt add apartment-case move-in IMG_1001.jpg \
  --slot living-north-wall \
  --room "Living room" \
  --item "North wall" \
  --view "Wide" \
  --note "Light scuff above baseboard" \
  --captured-at "2026-03-01T09:12:00-08:00"
```

批量清单必须包含 `source,slot,room,item,view`，可选 `note,captured_at`：

```bash
roomreceipt import apartment-case move-in move-in.csv
roomreceipt import apartment-case move-out move-out.csv
roomreceipt compare apartment-case
roomreceipt audit apartment-case
roomreceipt seal apartment-case
roomreceipt report apartment-case
roomreceipt bundle apartment-case
roomreceipt verify apartment-case
```

`slot` 是稳定视角键。入住和退租使用同一个 `slot` 才会配成一组。缺失视角不会被猜测或自动补齐。

## 验证边界

验证成功只表示：封存清单列出的文件，在验证时仍与记录的字节数和 SHA-256 一致。

它不能证明：

- 相机真正拍摄时间；
- 作者或拍摄者身份；
- 图片在第一次封存前从未编辑；
- EXIF 一定真实；
- 视觉变化就是损坏；
- 谁造成了变化；
- 证据一定被法律程序采纳或争议结果。

RoomReceipt 是文档工具，不提供法律意见。完整边界见 [docs/threat-model.md](docs/threat-model.md)。

## 验收命令

```bash
uv sync --all-extras
uv run python scripts/release_check.py
```

发布门禁包括 Ruff、严格 mypy、90% 分支覆盖率、48 项首发测试、示例确定性重建、两次分隔构建字节比对、目录/ZIP 验证、站点链接与无障碍检查、密钥扫描、wheel/sdist 构建、Twine 元数据验证、干净虚拟环境安装和 Release SHA-256 校验。

## 失败修复

- `HASH_MISMATCH`：不要直接重新封存。先从备份恢复预期原件；若变化确实经过审核且是有意的，再执行 `roomreceipt seal CASE`。
- `MOVE_IN_MISSING`：补入正确的入住基线图，再重新审计。
- `TIMEZONE_UNKNOWN`：EXIF 常不带时区。保留旁证，或用带时区的 ISO 8601 `captured_at` 重新导入。
- 示例确定性失败：先看二进制差异；只有生成器修改确实有意时，才运行 `uv run python scripts/generate_example_data.py` 更新夹具。
- 下载包验证失败：重新下载，并与 Release 的 `SHA256SUMS` 比较。
- CI 失败：用 `gh run view RUN_ID --log-failed` 读取远程日志，本地复现后再修改。

更完整的逐项修复命令见 [docs/repair.md](docs/repair.md)。

## 隐私

所有处理都在本机完成，没有遥测，也没有上传命令。报告只记录 GPS 是否存在，不输出坐标，但地址、备注、室内图和原始文件仍可能敏感。分享前必须人工审阅。

## 开发

```bash
uv sync --all-extras
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest --cov=roomreceipt --cov-report=term-missing
```

许可证：[MIT](LICENSE)。贡献说明见 [CONTRIBUTING.md](CONTRIBUTING.md)。
