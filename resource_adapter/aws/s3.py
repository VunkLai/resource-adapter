from __future__ import annotations

from pathlib import Path

import pulumi
from pulumi_aws import s3

import attrs

from resource_adapter.adapter import ResourceNaming, any_resources
from resource_adapter.aws import iam


class BucketPermission:
    def __init__(self, bucket: Bucket) -> None:
        self.list = iam.Permission(
            actions=["ListAllMyBuckets"],
            resources=["*"],
        )
        self.read = iam.Permission(
            actions=["ListBucket", "GetObject"],
            resources=any_resources(parent=bucket),
        )
        self.write = iam.Permission(
            actions=["PutObject", "DeleteObject"],
            resources=any_resources(parent=bucket),
        )


@attrs.define
class Bucket:
    name: str
    tags: dict = None
    opts: pulumi.ResourceOptions = None

    bucket: s3.Bucket = None
    permission = BucketPermission = None

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)

        bucket = s3.BucketV2(
            naming.resource_name,
            bucket=self.name,
            tags=self.tags,
            opts=self.opts,
        )
        permission = BucketPermission(bucket=bucket)

        self.permission = permission
        self.bucket = bucket

    @property
    def id(self) -> pulumi.Output[str]:
        return self.bucket.id

    @property
    def arn(self) -> pulumi.Output[str]:
        return self.bucket.arn

    def upload(self, path: Path) -> None:
        assert path.is_file(), f"Invalid file, {path}"

        naming = ResourceNaming(name=self.name)
        s3.BucketObjectv2(
            f"{naming.resource_name}-{path.name}",
            bucket=self.bucket.id,
            source=pulumi.FileAsset(path),
            key=path.name,
            opts=self.opts,
        )
