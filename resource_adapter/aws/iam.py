from __future__ import annotations

import pulumi
from pulumi_aws import iam

import attrs

from resource_adapter.adapter import ResourceNaming

SERVICES = {
    "ec2": "ec2.amazonaws.com",
    "lambda": "lambda.amazonaws.com",
    "es": "es.amazonaws.com",
    "sns": "sns.amazonaws.com",
}


class Permission:
    def __init__(
        self, actions: list[str] = None, resources: list[str] = None, sid: str = None
    ) -> None:
        self.statements = []

        if actions:
            self.add_statement(actions=actions, resources=resources, sid=sid)

    def add_statement(
        self, actions: list[str], resources: list[str] = None, sid: str = None
    ) -> None:
        self.statements.append(
            iam.GetPolicyDocumentStatementArgs(
                sid=sid,
                actions=actions,
                resources=resources or ["*"],
            )
        )

    def extend(self, permission: Permission) -> None:
        self.statements.extend(permission.statements)

    def append(self, statement: iam.GetPolicyDocumentStatementArgs) -> None:
        self.statements.append(statement)

    def create_document(self) -> iam.AwaitableGetPolicyDocumentResult:
        return iam.get_policy_document(statements=self.statements)


@attrs.define
class Role:
    name: str
    tags: dict = None
    opts: pulumi.ResourceOptions = None
    service_name: str = "ec2"

    role: iam.Role

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)

        statement = iam.GetPolicyDocumentStatementArgs(
            effect="Allow",
            actions=["sts:AssumeRole"],
            principals=[
                {"type": "Service", "identifiers": [SERVICES[self.service_name]]},
            ],
        )
        assume_role_policy = iam.get_policy_document(statements=[statement])
        role = iam.Role(
            naming.resource_name,
            assume_role_policy=assume_role_policy.json,
            tags=self.tags,
            opts=self.opts,
        )

        self.role = role

    def attach(self, attachement_name: str, policy: iam.Policy) -> None:
        naming = ResourceNaming(name=self.name)
        iam.RolePolicyAttachment(
            f"{naming.resource_name}-{attachement_name}",
            role=self.role.name,
            policy_arn=policy.arn,
            opts=self.opts,
        )

    def grant(self, policy_name: str, permission: Permission) -> None:
        naming = ResourceNaming(name=self.name)
        document = permission.create_document()
        policy = iam.Policy(
            f"{naming.resource_name}-{policy_name}",
            policy=document.json,
            opts=self.opts,
        )
        self.attach(policy_name, policy)

    def create_instance_profile(self) -> iam.InstanceProfile:
        naming = ResourceNaming(name=self.name)
        return iam.InstanceProfile(
            naming.resource_name + "-instance-profile",
            role=self.role.name,  # do not use arn
            opts=self.opts,
        )


@attrs.define
class Group:
    name: str
    opts: pulumi.ResourceOptions = None

    group: iam.Group

    def __attrs_post_init__(self) -> None:
        naming = ResourceNaming(name=self.name)

        group = iam.Group(naming.resource_name, opts=self.opts)

        self.group = group

    def attach(self, attachment_name: str, policy: iam.Policy) -> None:
        naming = ResourceNaming(name=self.name)
        iam.GroupPolicyAttachment(
            f"{naming.resource_name}-{attachment_name}",
            group=self.group.name,  # do not use arn
            policy_arn=policy.arn,
            opts=self.opts,
        )

    def grant(self, policy_name: str, permission: Permission) -> None:
        naming = ResourceNaming(name=self.name)
        document = permission.create_document()
        policy = iam.Policy(
            f"{naming.resource_name}-{policy_name}",
            policy=document.json,
            opts=self.opts,
        )
        self.attach(policy_name, policy)
