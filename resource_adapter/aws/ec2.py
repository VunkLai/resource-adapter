from __future__ import annotations

from base64 import b64encode
from typing import TYPE_CHECKING

import pulumi
from pulumi_aws import ec2

import attrs

from resource_adapter.adapter import ResourceNaming
from resource_adapter.aws import iam

if TYPE_CHECKING:
    from pathlib import Path


@attrs.define
class Vpc:
    name: str = None
    tags: dict = None
    opts: pulumi.ResourceOptions = None

    vpc: ec2.Vpc = None

    def __attrs_post_init__(self):
        naming = ResourceNaming(name=self.name)
        if self.tags is None:
            self.tags = {"Name": naming.resource_name}

        vpc = ec2.Vpc(
            naming.resource_name,
            cidr_block="10.0.0.0/16",
            enable_dns_hostnames=True,
            tags=self.tags,
            opts=self.opts,
        )

        self.vpc = vpc

    @property
    def id(self) -> pulumi.Output[str]:
        return self.vpc.id

    def create_internet_gateway(self) -> None:
        naming = ResourceNaming(name=self.name)
        internet_gateway = ec2.InternetGateway(
            naming.resource_name,
            vpc_id=self.vpc.id,
            tags=self.tags,
            opts=self.opts,
        )
        ec2.Route(
            naming.resource_name + "-default-route",
            route_table_id=self.vpc.main_route_table_id,
            gateway_id=internet_gateway.id,
            destination_cidr_block="0.0.0.0/0",
            opts=self.opts,
        )


@attrs.define
class Subnet:
    name: str
    vpc: Vpc
    availability_zone: str
    cidr_block: str
    map_public_ip_on_launch: bool = True
    tags: dict = None
    opts: pulumi.ResourceOptions = None

    subnet: ec2.Subnet = None

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=f"{self.name}-{self.availability_zone}")
        if self.tags is None:
            self.tags = {"Name": naming.resource_name}

        subnet = ec2.Subnet(
            naming.resource_name,
            availability_zone=self.availability_zone,
            cidr_block=self.cidr_block,
            map_public_ip_on_launch=self.map_public_ip_on_launch,
            vpc_id=self.vpc.id,
            tags=self.tags,
            opts=self.opts,
        )
        ec2.RouteTableAssociation(
            naming.resource_name + "-default-route-table",
            route_table_id=self.vpc.main_route_table_id,
            subnet_id=subnet.id,
            opts=self.opts,
        )

        self.subnet = subnet

    @property
    def id(self) -> pulumi.Output[str]:
        return self.subnet.id

    @classmethod
    def bulk_create(
        cls,
        name: str,
        vpc: Vpc,
        availability_zones: list[str],
        cidr_index: int,
        map_public_ip_on_launch: bool = True,
        tags: dict = None,
        opts: pulumi.ResourceOptions = None,
    ) -> list[Subnet]:
        subnets = []
        for offest, availability_zone in enumerate(availability_zones):
            subnet = cls(
                name,
                availability_zone=availability_zone,
                vpc=vpc,
                cidr_block=f"10.0.{cidr_index+offest}.0/24",
                map_public_ip_on_launch=map_public_ip_on_launch,
                tags=tags,
                opts=opts,
            )
            subnets.append(subnet)
        return subnets


@attrs.define
class SecurityGroup:
    name: str = None
    vpc: Vpc
    tags: dict = None
    opts: pulumi.ResourceOptions = None

    security_group: ec2.SecurityGroup = None

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)
        if self.tags is None:
            self.tags = {"Name": naming.resource_name}

        security_group = ec2.SecurityGroup(
            naming.resource_name,
            name=naming.resource_name,
            vpc_id=self.vpc.id,
            tags=self.tags,
            opts=self.opts,
        )
        ec2.SecurityGroupRule(
            naming.resource_name + "-default-outbound-rule",
            type="egress",
            protocol="-1",
            from_port=0,
            to_port=0,
            security_group_id=security_group.id,
            cidr_blocks=["0.0.0.0/0"],
            opts=self.opts,
        )

        self.security_group = security_group

    @property
    def id(self) -> pulumi.Output[str]:
        return self.security_group.id

    def add_ingress_rule(
        self,
        description: str,
        port: int,
        cidr_blocks: str | None = None,
        source_security_group_id: str | None = None,
        opts: pulumi.ResourceOptions = None,
    ) -> None:
        naming = ResourceNaming(name=self.name)

        ec2.SecurityGroupRule(
            f"{naming.resource_name}-{description}-{port}",
            description=description,
            from_port=port,
            to_port=port,
            cidr_blocks=cidr_blocks,
            source_security_group_id=source_security_group_id,
            security_group_id=self.security_group.id,
            type="ingress",
            protocol="tcp",
            opts=opts,
        )


class Ubuntu:
    Bionic_18: ec2.AwaitableGetAmiResult = ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],
        name_regex="ubuntu/images/hvm-ssd/ubuntu-bionic-18.04-amd64-server-*",
    )

    Focal_20: ec2.AwaitableGetAmiResult = ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],
        name_regex="ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*",
    )

    Jammy_22: ec2.AwaitableGetAmiResult = ec2.get_ami(
        most_recent=True,
        owners=["099720109477"],
        name_regex="ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*",
    )


@attrs.define
class UserData:
    user_data: str = ""

    def execute(self, file_path: Path) -> None:
        with open(file_path, "r", encoding="utf-8") as fr:
            self.user_data += fr.read()

    def append(self, *commands: list[str]) -> None:
        self.user_data += "\n".join(commands)

    def b64encode(self) -> str:
        return b64encode(self.user_data.encode()).decode()


@attrs.define
class KeyPair:
    name: str
    opts: pulumi.ResourceOptions = None

    key_pair: ec2.KeyPair = None

    def __attrs_post_init__(self):
        naming = ResourceNaming(name=self.name)

        key_pair = ec2.KeyPair(naming.resource_name, opts=self.opts)

        self.key_pair = key_pair

    @property
    def id(self) -> pulumi.Output[str]:
        return self.key_pair.id


@attrs.define
class LaunchTemplate:
    name: str
    role: iam.Role
    image: ec2.AwaitableGetAmiResult
    user_data: UserData
    key_pair: KeyPair
    security_group: SecurityGroup = None  # only for ASG
    instance_type: str = "t3.nano"
    root_volume_size: int = 10
    extra_volume_size: int = 0
    tags: dict = None
    opts: pulumi.ResourceOptions = None

    launch_template = ec2.LaunchTemplate

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)

        profile = self.role.create_instance_profile(opts=self.opts)

        block_device_mappings = [
            {
                "device_name": "/dev/sda1",
                "ebs": {
                    "delete_on_termination": True,
                    "volume_size": self.root_volume_size,
                    "volume_type": "gp3",
                },
            }
        ]
        if self.extra_volume_size > 0:
            block_device_mappings.append(
                {
                    "device_name": "/dev/sdf",
                    "ebs": {
                        "delete_on_termination": False,
                        "volume_size": self.extra_volume_size,
                        "volume_type": "gp3",
                    },
                }
            )

        vpc_security_group_ids = []
        if self.security_group:
            vpc_security_group_ids.append(self.security_group.id)

        launch_template = ec2.LaunchTemplate(
            naming.resource_name,
            iam_instance_profile={"arn": profile.arn},
            vpc_security_group_ids=vpc_security_group_ids,
            image_id=self.image.id,
            instance_type=self.instance_type,
            credit_specification={
                "cpu_credits": "standard",
            },
            user_data=self.user_data.b64encode(),
            key_name=self.key_pair.id,
            block_device_mappings=block_device_mappings,
            update_default_version=True,
            tag_specifications=[
                {"resource_type": "instance", "tags": {"Name": naming.resource_name}},
                {"resource_type": "volume", "tags": {"Name": naming.resource_name}},
            ],
            tags=self.tags,
            opts=self.opts,
        )

        self.launch_template = launch_template

    @property
    def id(self) -> pulumi.Output[str]:
        return self.launch_template.id

    def launch_instance(self, subnet: Subnet, security_group: SecurityGroup) -> None:
        naming = ResourceNaming(name=self.name)

        instance = ec2.Instance(
            naming.resource_name,
            launch_template=ec2.InstanceLaunchTemplateArgs(
                id=self.launch_template.id,
            ),
            subnet_id=subnet.id,
            vpc_security_group_ids=[security_group.id],
            tags=self.tags,
            opts=self.opts,
        )

        pulumi.export(
            naming.resource_name,
            instance.public_dns.apply(lambda url: f"ssh -i private.key ubuntu@{url}"),
        )

        return instance
