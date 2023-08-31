import pulumi
from pulumi_aws import ecr

import attrs

from resource_adapter.adapter import ResourceNaming
from resource_adapter.aws import iam


class RepositoryPermission:
    def __init__(self, repository: ecr.Repository) -> None:
        self.pull = iam.Permission(
            actions=["BatchCheckLayerAvailability", "BatchGetImage"],
            resources=[repository.arn],
        )
        self.push = iam.Permission(
            actions=["PutImage"],
            resources=[repository.arn],
        )


@attrs.define
class Repository:
    name: str
    image_tag_mutability: str = "IMMUTABLE"
    opts: pulumi.ResourceOptions = None

    repositor: ecr.Repository
    permission: RepositoryPermission

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)
        repository = ecr.Repository(
            naming.resource_name,
            name=self.name,
            image_tag_mutability=self.image_tag_mutability,
            opts=self.opts,
        )
        permission = RepositoryPermission(repository=repository)

        self.repositor = repository
        self.permission = permission

    @property
    def arn(self) -> pulumi.Output[str]:
        return self.repositor.arn


@attrs.define
class Registry:
    image_tag_mutability: str = ("IMMUTABLE",)
    opts: pulumi.ResourceOptions = None

    repositories: dict[str, Repository] = attrs.field(factory=dict)

    def create_repository(self, name: str) -> None:
        repository = Repository(
            name=name,
            image_tag_mutability=self.image_tag_mutability,
            opts=self.opts,
        )
        self.repositories[name] = repository
