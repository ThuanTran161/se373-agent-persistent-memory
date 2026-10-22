import json
from datetime import datetime
from src.config import CONVENTIONS_FILE, MARKDOWN_CONVENTIONS_FILE, MEMORY_HISTORY_FILE

class MemoryManager:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        if not CONVENTIONS_FILE.exists():
            with open(CONVENTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2, ensure_ascii=False)
        if not MEMORY_HISTORY_FILE.exists():
            with open(MEMORY_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2, ensure_ascii=False)
        if not MARKDOWN_CONVENTIONS_FILE.exists():
            self._write_markdown({})

    def load_conventions(self):
        try:
            with open(CONVENTIONS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _load_history(self):
        try:
            with open(MEMORY_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def _save_history(self, history):
        with open(MEMORY_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

    def _write_markdown(self, conventions):
        lines = [
            "# PROJECT PERSISTENT CONVENTIONS",
            "Auto-generated and synchronized by Memory Harness",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]
        if not conventions:
            lines.append("*No conventions recorded yet.*")
        else:
            by_category = {}
            for item in conventions.values():
                cat = item.get("category", "General")
                by_category.setdefault(cat, []).append(item)

            for cat, items in sorted(by_category.items()):
                lines.append(f"## {cat.upper()}")
                for it in items:
                    lines.append(f"- **{it['rule_key']}**: `{it['value']}` (v{it.get('version', 1)})")
                    if it.get("description"):
                        lines.append(f"  - *Mô tả:* {it['description']}")
                lines.append("")

        with open(MARKDOWN_CONVENTIONS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def save_or_update(self, rule_key, value, category=None, description=None, reason="initial"):
        conventions = self.load_conventions()
        history = self._load_history()
        now_str = datetime.now().isoformat()

        if rule_key in conventions:
            old_item = conventions[rule_key]
            old_val = old_item["value"]
            if old_val == value:
                return {"status": "unchanged", "rule_key": rule_key, "value": value}

            new_version = old_item.get("version", 1) + 1
            updated_item = {
                "rule_key": rule_key,
                "value": value,
                "category": category if category is not None else old_item.get("category", "general"),
                "description": description if description is not None else old_item.get("description", ""),
                "version": new_version,
                "updated_at": now_str,
            }
            conventions[rule_key] = updated_item
            history.append({
                "timestamp": now_str,
                "action": "UPDATE_OVERWRITE",
                "rule_key": rule_key,
                "old_value": old_val,
                "new_value": value,
                "version": new_version,
                "reason": reason,
            })
            action_type = "updated"
        else:
            new_item = {
                "rule_key": rule_key,
                "value": value,
                "category": category or "general",
                "description": description or "",
                "version": 1,
                "created_at": now_str,
                "updated_at": now_str,
            }
            conventions[rule_key] = new_item
            history.append({
                "timestamp": now_str,
                "action": "CREATE",
                "rule_key": rule_key,
                "value": value,
                "version": 1,
                "reason": reason,
            })
            action_type = "created"

        with open(CONVENTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(conventions, f, indent=2, ensure_ascii=False)

        self._save_history(history)
        self._write_markdown(conventions)
        return {"status": action_type, "rule_key": rule_key, "value": value}

    def get_injected_context(self):
        conventions = self.load_conventions()
        if not conventions:
            return "No persistent project conventions are currently stored."

        formatted_rules = []
        for key, item in sorted(conventions.items()):
            formatted_rules.append(
                f"- [{item.get('category', 'general').upper()}] {key} = '{item['value']}' "
                f"(v{item.get('version', 1)}): {item.get('description', '')}"
            )

        return (
            "=== ACTIVE PROJECT PERSISTENT CONVENTIONS ===\n"
            "The following rules were agreed upon in previous sessions. "
            "You MUST strictly follow and apply them in all solutions:\n"
            + "\n".join(formatted_rules)
            + "\n=============================================="
        )

    def clear(self):
        with open(CONVENTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)
        with open(MEMORY_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        self._write_markdown({})
