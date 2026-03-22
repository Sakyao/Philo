import os
import re
import json
import shutil
from pathlib import Path


class SkillsLoader(object):
    def __init__(self, pcfg):
        self.pcfg = pcfg
        self.workspaceSkillsDir: Path = pcfg.workspace / "skills"
        self.builtInSkillsDir = Path(__file__).parent.parent / "resources/skills"

    def listSkills(self, filterUnavailable) -> list[dict[str, str]]:
        skills = []
        if self.workspaceSkillsDir.exists():
            for skillDir in self.workspaceSkillsDir.iterdir():
                if skillDir.is_dir():
                    skillFile = skillDir / "SKILL.md"
                    if skillFile.exists():
                        skills.append({"name": skillDir.name, "path": str(skillFile), "source": "workspace"})
        if self.builtInSkillsDir and self.builtInSkillsDir.exists():
            for skillDir in self.builtInSkillsDir.iterdir():
                if skillDir.is_dir():
                    skillFile = skillDir / "SKILL.md"
                    if skillFile.exists() and not any(s["name"] == skillDir.name for s in skills):
                        skills.append({"name": skillDir.name, "path": str(skillFile), "source": "builtin"})
        if filterUnavailable:
            return [s for s in skills if self.checkRequirements(self.getSkillMeta(s["name"]))]
        return skills

    def loadSkill(self, name: str):
        workspaceSkill = self.workspaceSkillsDir / name / "SKILL.md"
        if workspaceSkill.exists():
            return workspaceSkill.read_text(encoding="utf-8")
        if self.builtInSkillsDir:
            builtinSkill = self.builtInSkillsDir / name / "SKILL.md"
            if builtinSkill.exists():
                return builtinSkill.read_text(encoding="utf-8")
        return None

    def loadSkillsForContext(self, skillNames: list[str]) -> str:
        parts = []
        for name in skillNames:
            content = self.loadSkill(name)
            if content:
                content = self.stripFrontmatter(content)
                parts.append(f"### Skill: {name}\n\n{content}")
        return "\n\n---\n\n".join(parts) if parts else ""

    def buildSkillsSummary(self) -> str:
        """
        Build a summary of all skills (name, description, path, availability).
        This is used for progressive loading - the agent can read the full
        skill content using read_file when needed.
        Returns:
            XML-formatted skills summary.
        """
        allSkills = self.listSkills(filterUnavailable=False)
        def escapeXml(s: str) -> str:
            return s.replace("&", "&").replace("<", "<").replace(">", ">")
        lines = ["<skills>"]
        for s in allSkills:
            name = escapeXml(s["name"])
            path = s["path"]
            desc = escapeXml(self.getSkillDescription(s["name"]))
            skillMeta = self.getSkillMeta(s["name"])
            available = self.checkRequirements(skillMeta)
            lines.append(f"  <skill available=\"{str(available).lower()}\">")
            lines.append(f"    <name>{name}</name>")
            lines.append(f"    <description>{desc}</description>")
            lines.append(f"    <location>{path}</location>")
            lines.append("  </skill>")
        lines.append("</skills>")
        return "\n".join(lines)

    def getSkillDescription(self, name: str) -> str:
        meta = self.getSkillMetadata(name)
        if meta and meta.get("description"):
            return meta["description"]
        return name  # Fallback to skill name

    def stripFrontmatter(self, content: str) -> str:
        if content.startswith("---"):
            match = re.match(r"^---\n.*?\n---\n", content, re.DOTALL)
            if match:
                return content[match.end():].strip()
        return content

    def parseNanobotMetadata(self, raw: str) -> dict:
        """Parse skill metadata JSON from frontmatter (supports nanobot and openclaw keys)."""
        try:
            data = json.loads(raw)
            return data.get("nanobot", data.get("openclaw", {})) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def checkRequirements(self, skillMeta: dict) -> bool:
        requires = skillMeta.get("requires", {})
        for b in requires.get("bins", []):
            if not shutil.which(b):
                return False
        for env in requires.get("env", []):
            if not os.environ.get(env):
                return False
        return True

    def getSkillMeta(self, name: str) -> dict:
        meta = self.getSkillMetadata(name) or {}
        return self.parseNanobotMetadata(meta.get("metadata", ""))

    def getActiveSkills(self) -> list[str]:
        result = []
        for s in self.listSkills(filterUnavailable=True):
            meta = self.getSkillMetadata(s["name"]) or {}
            skillMeta = self.parseNanobotMetadata(meta.get("metadata", ""))
            if skillMeta.get("always") or meta.get("always"):
                result.append(s["name"])
        return result

    def getSkillMetadata(self, name: str):
        content = self.loadSkill(name)
        if not content:
            return None
        if content.startswith("---"):
            match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            if match:
                metadata = {}
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, value = line.split(":", 1)
                        metadata[key.strip()] = value.strip().strip('"\'')
                return metadata
        return None
