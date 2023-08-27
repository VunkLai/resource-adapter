import pulumi
from pulumi_aws import ec2

import attrs

from resource_adapter.adapter import ResourceNaming


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
class SecurityGroup:
    vpc: Vpc
    name: str = None
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
