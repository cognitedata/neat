from dataclasses import dataclass

@dataclass
class Affix:
    prefix: str = "prefix"
    suffix: str = "suffix"

    def applyPrefix(self, base: str) -> str:
        return f"{self.prefix}_{base}"

    def applySuffix(self, base: str) -> str:
        return f"{base}_{self.suffix}"