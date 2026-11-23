from pydantic import BaseModel

from state_of_soroban.extract.analyse import Analysis


class ShardLine(BaseModel):
    repo: str
    digest: str
    analysis: Analysis | None = None
    error: str | None = None
    gone: bool = False
