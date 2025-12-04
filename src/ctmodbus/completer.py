from prompt_toolkit.completion import Completer, Completion
from ctui.commands import Commands
import re


class CommandCompleter(Completer):
    """Stable hierarchical autocompleter, ctui 0.7.x compatible."""

    def __init__(self, commands: Commands):
        assert isinstance(commands, Commands)
        self.commands = commands

        # Build command tree for multi-word commands
        self.tree = {}
        for cmd in commands:
            node = self.tree
            for part in cmd.string_parts:
                node = node.setdefault(part, {})

    def _fuzzy(self, word, pattern):
        """Simple fuzzy match."""
        if not pattern:
            return False
        regex = ".*?".join(map(re.escape, pattern))
        return re.search(regex, word, re.IGNORECASE)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor or ""
        parts = text.split()
        ends_space = text.endswith(" ")

        # No text → show root commands
        if not parts:
            for key in sorted(self.tree):
                yield Completion(key, start_position=0)
            return

        # Navigate tree
        node = self.tree
        for p in parts[:-1]:
            if p in node:
                node = node[p]
            else:
                return

        current = "" if ends_space else parts[-1]

        # After space → descend further
        if ends_space:
            last = parts[-1]
            if last in node:
                node = node[last]

            for key in sorted(node):
                yield Completion(key, start_position=0)
            return

        # Partial / fuzzy match
        for key in sorted(node):
            if key.startswith(current) or self._fuzzy(key, current):
                yield Completion(
                    key,
                    start_position=-len(current),
                )
