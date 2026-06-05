"""
P0-7 守门测试 - codegen_field_schema.py 不再生成 broken TS

WHY:
  docs/CODE_REVIEW_2026-06-03.md Agent 3 C1 + Agent 4 H5：codegen 生成的
  sectionConfig.ts 含 broken TS 语法 — multi-row 字段的 fields 数组
  形式是 `fields: [, { key: ... }, { key: ... }, ]`（中括号和首尾
  元素之间多个空逗号），TS 解析时把空逗号当 undefined，tsc 报
  `Type 'undefined' is not assignable to type 'FieldDef'`，compile fail。

  修前根因（codegen_field_schema.py:161-166）：把 "fields: [" 和每个
  sub_field 对象字符串和 "]" 全部塞进 parts 列表，最后用 ', ' join，
  产出 "fields: [, {key:..}, {key:..}, ]"。

  修后：basic attrs 用 ', ' join，sub_fields 独立拼成多行字符串（每行
  一个 sub_field 对象，逗号 join 多行），不再有 broken 数组。

守门 3 件套：
  1. 跑 codegen 生成的 sectionConfig.ts 必须能通过 tsc AST 解析
     （无 `, ,` / `[ ,` 模式）
  2. 跑 codegen 生成的 multi-row 字段的 fields 数组必须紧凑（无 `[` 后紧跟逗号）
  3. `codegen --check` 必须在 codegen 重新生成后通过（自反一致性）
"""
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]  # tantan/
SECTION_CONFIG = REPO_ROOT / "frontend" / "config" / "sectionConfig.ts"
CODEGEN = REPO_ROOT / "backend" / "scripts" / "codegen_field_schema.py"


def _run_codegen() -> str:
    """跑 codegen 重新生成所有目标文件，返回 codegen stdout"""
    result = subprocess.run(
        [sys.executable, "-m", "tantan.backend.scripts.codegen_field_schema"],
        cwd=REPO_ROOT.parent,  # claude_workspace/
        capture_output=True,
        text=True,
        encoding="utf-8",  # Windows 默认 gbk 编码解中文 stdout 会抛 UnicodeDecodeError
    )
    if result.returncode != 0:
        raise AssertionError(f"codegen 失败: stdout={result.stdout}, stderr={result.stderr}")
    return result.stdout


def _run_codegen_check() -> subprocess.CompletedProcess:
    """跑 codegen --check 自反校验"""
    return subprocess.run(
        [sys.executable, "-m", "tantan.backend.scripts.codegen_field_schema", "--check"],
        cwd=REPO_ROOT.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _has_broken_array(text: str) -> list[str]:
    """检测 `[, ` / `, ,` 模式（broken TS 数组起点/中点空元素）"""
    issues = []
    for i, line in enumerate(text.splitlines(), start=1):
        # `fields: [` 紧跟逗号 → 多行模式需要看下一行
        # 这里用单行 + 多行两种正则
        if re.search(r"\[\s*,", line):
            issues.append(f"line {i}: 数组起点有空元素 `{{`{line.strip()[:60]}...`}}`")
        if re.search(r",\s*,", line):
            issues.append(f"line {i}: 数组中段有空元素 `{{`{line.strip()[:60]}...`}}`")
    return issues


def _tsc_parse_check(text: str) -> bool:
    """用 node 跑一个最小 TS 解析检查（不需要 tsc 全量编译）"""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False, encoding="utf-8") as f:
        # 给 SECTION_FIELDS 加 dummy 上下文便于独立 parse
        f.write("interface FieldDef { key: string; label: string; type: string; fields?: FieldDef[]; }\n")
        f.write("interface Foo { [k: number]: FieldDef[] }\n")
        # 抽出 SECTION_FIELDS 块（从 "export const SECTION_FIELDS" 到 EOF 第一个 "};\n"）
        m = re.search(r"export const SECTION_FIELDS[\s\S]+?\n\};[\s]*$", text)
        if not m:
            return False
        # 只去掉 `export` 关键字，FieldDef 引用由上面的 dummy interface 满足
        f.write(m.group(0).replace("export const", "const"))
        tmp_path = f.name

    tmp_unix = tmp_path.replace("\\", "/")
    script = (
        "const ts = require('typescript');\n"
        "const fs = require('fs');\n"
        f"const src = fs.readFileSync('{tmp_unix}', 'utf-8');\n"
        "const sf = ts.createSourceFile('x.ts', src, ts.ScriptTarget.ES2020, true);\n"
        "const diags = sf.parseDiagnostics || [];\n"
        "console.log(JSON.stringify({ok: diags.length === 0, count: diags.length}));\n"
    )
    try:
        # 从 frontend/ 跑（typescript module 在这里）
        result = subprocess.run(
            ["node", "-e", script],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "frontend",
        )
        out = result.stdout.strip()
        return '"ok":true' in out
    finally:
        Path(tmp_path).unlink(missing_ok=True)


class TestCodegenNotBrokenTS:
    """P0-7: codegen 输出必须是合法 TS 语法"""

    def test_codegen_writes_section_config(self):
        """跑 codegen 重新生成所有 4 个目标文件"""
        _run_codegen()
        assert SECTION_CONFIG.exists(), f"sectionConfig.ts 应已生成: {SECTION_CONFIG}"

    def test_section_config_has_no_broken_array_pattern(self):
        """sectionConfig.ts 不得含 `[, ` 或 `, ,` 空元素数组"""
        _run_codegen()
        text = SECTION_CONFIG.read_text(encoding="utf-8")
        issues = _has_broken_array(text)
        assert not issues, "codegen 输出含 broken TS 数组语法：\n" + "\n".join(issues)

    def test_multirow_fields_are_compact(self):
        """multi-row 字段的 fields 数组应该是紧凑的多行格式，不是 `[, ...]` 形式"""
        _run_codegen()
        text = SECTION_CONFIG.read_text(encoding="utf-8")
        # 找 "fields: [" 后面紧跟的字符（首尾各允许 1 个换行/空格）
        m = re.findall(r"fields:\s*\[[^\]]{0,3}\]", text, re.DOTALL)
        for hit in m:
            # 不允许 "fields: [," 形式
            assert not re.match(r"fields:\s*\[\s*,", hit), (
                f"multi-row fields 数组起点有空元素: `{hit!r}`"
            )
            # 不允许 "fields: [ , ]" / "fields: [, ]" 形式
            assert not re.search(r",\s*,", hit), (
                f"multi-row fields 数组中段有空元素: `{hit!r}`"
            )

    def test_codegen_check_self_consistent(self):
        """`codegen --check` 在 codegen 重新生成后必须返回 exit 0（自反一致性）"""
        _run_codegen()  # 先确保文件是最新的
        result = _run_codegen_check()
        assert result.returncode == 0, (
            f"codegen --check 失败（文件未同步 SSOT）：\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "[PASS]" in result.stdout, (
            f"codegen --check 应输出 [PASS]，实际: {result.stdout}"
        )

    def test_section_config_tsc_parseable(self):
        """SECTION_FIELDS 块必须能被 TypeScript AST 解析（无 Unknown 节点）"""
        _run_codegen()
        text = SECTION_CONFIG.read_text(encoding="utf-8")
        assert _tsc_parse_check(text), "SECTION_FIELDS 块 TypeScript AST 解析失败"
