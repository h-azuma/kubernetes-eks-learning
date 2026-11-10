"""PowerShell 版と Bash 版のスクリプトが対になっていることと、手順の抽出を確認する。"""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learning-portal/content"))
from build_content import practice_sections

SCRIPT_DIRECTORIES = [ROOT / "tools", *sorted((ROOT / "phases").glob("*/scripts"))]


def scripts(suffix):
    return {path.relative_to(ROOT).with_suffix("").as_posix() for directory in SCRIPT_DIRECTORIES for path in directory.glob(f"*{suffix}")}


class ScriptPairTests(unittest.TestCase):
    def test_every_script_exists_in_both_shells(self):
        powershell, bash = scripts(".ps1"), scripts(".sh")
        self.assertTrue(powershell)
        self.assertEqual(powershell - bash, set(), ".sh がありません")
        self.assertEqual(bash - powershell, set(), ".ps1 がありません")

    def test_bash_scripts_use_lf_without_bom(self):
        for name in scripts(".sh"):
            with self.subTest(script=name):
                data = (ROOT / f"{name}.sh").read_bytes()
                self.assertTrue(data.startswith(b"#!/usr/bin/env bash\n"))
                self.assertNotIn(b"\r", data)
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"))


class PracticeSectionTests(unittest.TestCase):
    README = """## 検証

### 1. 準備

説明です。

目的：文字を表示します。

**Windows (PowerShell):**

```powershell
Write-Output a
```

**Linux / macOS / WSL (Bash):**

```bash
echo a
```

確認：a と表示されます。

補足です。

目的：共通のコマンドを実行します。

```text
common command
```

確認：何も表示されません。
"""

    def test_powershell_and_bash_blocks_become_one_step(self):
        sections = practice_sections(self.README, "practice", ["検証"])
        self.assertEqual(len(sections), 1)
        first, second = sections[0]["steps"]
        self.assertEqual((first["command"], first["linuxCommand"]), ("Write-Output a", "echo a"))
        self.assertEqual(first["description"], "文字を表示します。")
        self.assertEqual(first["expected"], "a と表示されます。\n\n補足です。")
        self.assertEqual((second["description"], second["expected"]), ("共通のコマンドを実行します。", "何も表示されません。"))
        self.assertNotIn("linuxCommand", second)
        self.assertEqual(sections[0]["body"], "説明です。")
        self.assertNotIn("PowerShell", sections[0]["body"])

    def test_missing_purpose_or_check_is_rejected(self):
        for readme in (
            "## 検証\n\n確認：なし。\n\n```text\nls\n```\n",
            "## 検証\n\n目的：一覧します。\n\n```text\nls\n```\n\n補足だけ。\n",
        ):
            with self.assertRaises(ValueError):
                practice_sections(readme, "practice", ["検証"])


if __name__ == "__main__":
    unittest.main()
