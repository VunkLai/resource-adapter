import pulumi

import attrs


@attrs.define
class ResourceNaming:
    name: str = None
    project_name: str = None
    stack_name: str = None

    def __attrs_post_init__(self) -> None:
        config = pulumi.Config("adapter")
        self.project_name = config.require("project_name")
        self.stack_name = config.require("stack_name")

    @property
    def prefix(self) -> str:
        return f"{self.project_name}-{self.stack_name}"

    @property
    def resource_name(self) -> str:
        if self.name is None:
            return self.prefix
        return f"{self.prefix}-{self.name}"
