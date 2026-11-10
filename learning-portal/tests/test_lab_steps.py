"""ラボ README から抽出した手順が「1手順1コマンド」「目的と確認つき」であることを確認する。"""

from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "learning-portal/content"))
from build_content import LABS, PRACTICE_HEADINGS, practice_sections, read

# コマンドを持つ Phase 0〜8 のラボ。Phase 9 は机上の比較でコマンドがない。
LAB_READMES = LABS[:9]
CURRICULUM = ROOT / "learning-portal/content/curriculum.json"
BOILERPLATE = "リポジトリ直下で、説明と実行条件を確認してから手動実行してください。"
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)")


def command_count(script):
    """空行とコメント行を除いたコマンド数。行継続（末尾のバックスラッシュとバッククォート）とヒアドキュメントは1コマンドと数える。"""
    count, continued, terminator = 0, False, None
    for line in script.splitlines():
        text = line.strip()
        if terminator:
            terminator = None if text == terminator else terminator
            continue
        if not continued and (not text or text.startswith("#")):
            continue
        count += 0 if continued else 1
        continued = text.endswith(("\\", "`"))
        heredoc = HEREDOC.search(text)
        terminator = heredoc.group(1) if heredoc else None
    return count


def lab_steps(path):
    return [step for section in practice_sections(read(path), "practice", PRACTICE_HEADINGS) for step in section.get("steps", [])]


class CommandCountTests(unittest.TestCase):
    def test_counts_commands(self):
        self.assertEqual(command_count("# メモ\n\nkubectl get pods\n"), 1)
        self.assertEqual(command_count("a\nb"), 2)
        self.assertEqual(command_count("docker run `\n  --rm `\n  image"), 1)
        self.assertEqual(command_count("docker run \\n  image"), 1)
        self.assertEqual(command_count("cat <<EOF\nx\n\ny\nEOF"), 1)


SAMPLE = """## 検証コマンド・期待結果

導入文。

### 1. 最初

目的：共通を実行する。

```text
echo a
```

確認：表示される。

### 2. 次

目的：Windows だけ。

```powershell
Get-Date
```

確認：日時が出る。
"""


class PracticeSectionTests(unittest.TestCase):
    def test_introduction_only_in_first_subsection_and_single_shell_is_marked(self):
        first, second = practice_sections(SAMPLE, "p", PRACTICE_HEADINGS)
        self.assertIn("導入文。", first["body"])
        self.assertNotIn("導入文。", second["body"])
        self.assertNotIn("shell", first["steps"][0])
        self.assertEqual(second["steps"][0]["shell"], "powershell")


class LessonTitleTests(unittest.TestCase):
    """curriculum.json の解説節が、実習と見出しを重ねず、実在する実習だけを参照することを確認する。"""

    def test_explanation_titles_differ_from_practice_and_references_exist(self):
        for phase in json.loads(CURRICULUM.read_text(encoding="utf-8"))["phases"]:
            practice = {s["title"].removeprefix("実習: ") for s in phase["sections"] if s.get("kind") == "practice"}
            for section in phase["sections"]:
                if section.get("kind") == "practice":
                    continue
                with self.subTest(phase=phase["id"], section=section["id"]):
                    self.assertNotIn("steps", section)
                    self.assertNotIn(re.sub(r"^\d+\. ", "", section["title"]), {re.sub(r"^\d+\. ", "", title) for title in practice})
                    for reference in re.findall(r"「([^」]+)」", section["body"].split("→ 実習", 1)[-1]) if "→ 実習" in section["body"] else []:
                        self.assertIn(reference, practice)


class LabStepTests(unittest.TestCase):
    def test_each_step_has_one_command_with_purpose_and_check(self):
        for path in LAB_READMES:
            steps = lab_steps(path)
            self.assertTrue(steps, path)
            for step in steps:
                with self.subTest(readme=path, title=step["title"], command=step["command"][:60]):
                    for key in ("command", "linuxCommand"):
                        if key in step:
                            self.assertEqual(command_count(step[key]), 1, key)
                    for key in ("description", "expected"):
                        self.assertTrue(step[key].strip(), key)
                        self.assertNotEqual(step[key], BOILERPLATE, key)
                    self.assertNotIn("目的：", step["description"])
                    self.assertFalse(step["expected"].startswith("確認："))


if __name__ == "__main__":
    unittest.main()
