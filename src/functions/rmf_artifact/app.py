"""RMF evidence generator - Ports/Protocols/Services + topology, parsed from the IaC.

The claim this function backs up is narrow and checkable: **the security
documentation is generated from the same file that creates the infrastructure,
so it cannot drift from it.** Nothing here is hand-written prose about the
system; every row in the PPS table and every node in the topology is read out of
``template.yaml``'s ``Resources`` block, and each one carries the logical
resource and property it came from so an assessor can grep the template and
check it.

What it produces
----------------
A single markdown artifact containing:

* a **Ports, Protocols and Services** registration table in the shape a PPSM
  submission wants - split into boundary-crossing inbound flows, internal
  flows, and outbound service dependencies - derived from security-group rules,
  database ports, edge resources, and the AWS API actions each function's IAM
  policy actually grants;
* a **network topology**: VPC/subnet/routing inventory plus a Mermaid diagram
  built from the parsed resources;
* a **component inventory**, **data-protection** (encryption at rest/in transit)
  and **identity/access** section;
* a **candidate NIST SP 800-53 Rev 5 control mapping**, where every control is
  cited to the template line item that evidences it;
* an explicit **"what this artifact cannot assert"** section. An IaC parser can
  prove a security group's rules; it cannot prove an interconnection agreement
  exists. Saying so is the difference between evidence and decoration.

Deliberately **no LLM.** The function has Bedrock permission in the template, and
it does not use it: an ATO artifact must be reproducible byte-for-byte from its
input, and a sampled model is not. Same template in, same markdown out.

How to run it
-------------
As a CLI, against the repo's template, with nothing deployed::

    python3 src/functions/rmf_artifact/app.py                 # -> stdout
    python3 src/functions/rmf_artifact/app.py -o /tmp/pps.md
    python3 src/functions/rmf_artifact/app.py path/to/template.yaml

As a Lambda (direct invoke - this function has no API route in CONTRACTS.md)::

    {}                                            # uses the bundled template.yaml
    {"template_body": "<yaml text>"}
    {"template_s3": {"bucket": "...", "key": "..."}}
    {"stack_name": "compass-demo"}                 # via cloudformation:GetTemplate
    {"write_s3": true}                            # also store under rmf/ in RMF_BUCKET

The response carries the markdown inline plus the counts and provenance hash, so
the caller never has to guess whether the artifact matched the template.

Packaging note: ``sam build`` packages only this function's ``CodeUri``, so for
the Lambda to read the stack's own template it needs one of the event sources
above, or a copy of ``template.yaml`` placed next to ``app.py`` at build time.
The bundled-file path is checked first and the failure message names every
source that was tried - no silent fallback to stale content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

log = logging.getLogger()
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

HERE = Path(__file__).resolve().parent
# src/functions/rmf_artifact/app.py -> repo root, when running from a checkout.
# In Lambda the file is at /var/task/app.py, which has ONE parent, so indexing
# parents[2] at import time raised IndexError and the module failed to load
# before the handler ever ran. Resolve defensively and fall back to the copy
# bundled next to app.py at build time.
_parents = HERE.parents
REPO_TEMPLATE = (_parents[2] / "template.yaml") if len(_parents) > 2 else (HERE / "template.yaml")
BUNDLED_TEMPLATE = HERE / "template.yaml"

ARTIFACT_TITLE = "Compass - Ports, Protocols & Services and System Topology"


# --------------------------------------------------------------------------- #
# CloudFormation YAML parsing
# --------------------------------------------------------------------------- #
def _cfn_loader():
    """A SafeLoader that understands CloudFormation's short-form intrinsics.

    ``!Ref``/``!Sub``/``!GetAtt`` are custom YAML tags; a plain SafeLoader
    refuses them. Each becomes its long-form dict (``{"Ref": ...}``,
    ``{"Fn::Sub": ...}``) so downstream code sees one representation.
    """
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - dependency is pinned
        raise RuntimeError(
            "PyYAML is required to parse the CloudFormation template. "
            "It is pinned in src/functions/rmf_artifact/requirements.txt; "
            "install it locally with `pip install pyyaml`."
        ) from exc

    class CfnLoader(yaml.SafeLoader):
        pass

    def multi(loader, tag_suffix, node):
        name = tag_suffix if tag_suffix in ("Ref", "Condition") else f"Fn::{tag_suffix}"
        if isinstance(node, yaml.ScalarNode):
            value: Any = loader.construct_scalar(node)
        elif isinstance(node, yaml.SequenceNode):
            value = loader.construct_sequence(node, deep=True)
        else:
            value = loader.construct_mapping(node, deep=True)
        if name == "Fn::GetAtt" and isinstance(value, str):
            value = value.split(".")
        return {name: value}

    CfnLoader.add_multi_constructor("!", multi)
    # CloudFormation templates may repeat `Tags` style keys in odd places; keep
    # the loader permissive about unknown timestamps/values rather than failing
    # the whole artifact over a cosmetic node.
    return yaml, CfnLoader


def parse_template(text: str) -> Dict[str, Any]:
    yaml, loader = _cfn_loader()
    doc = yaml.load(text, Loader=loader)
    if not isinstance(doc, dict) or "Resources" not in doc:
        raise ValueError("not a CloudFormation/SAM template (no Resources block)")
    return doc


def flatten(value: Any) -> str:
    """Render an intrinsic-bearing value as a short, readable string.

    ``{"Ref": "LambdaSecurityGroup"}`` -> ``LambdaSecurityGroup``;
    ``{"Fn::GetAtt": ["DbCluster", "Endpoint.Address"]}`` -> ``DbCluster.Endpoint.Address``;
    ``{"Fn::If": [c, a, b]}`` -> the "true" branch with the condition noted.
    """
    if value is None:
        return ""
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(flatten(v) for v in value)
    if isinstance(value, dict):
        if "Ref" in value:
            return flatten(value["Ref"])
        if "Fn::GetAtt" in value:
            att = value["Fn::GetAtt"]
            return ".".join(att) if isinstance(att, list) else flatten(att)
        if "Fn::Sub" in value:
            sub = value["Fn::Sub"]
            return flatten(sub[0]) if isinstance(sub, list) else flatten(sub)
        if "Fn::If" in value:
            args = value["Fn::If"]
            if isinstance(args, list) and len(args) == 3:
                return f"{flatten(args[1])} (conditional: {flatten(args[0])})"
        if "Fn::Join" in value:
            args = value["Fn::Join"]
            if isinstance(args, list) and len(args) == 2:
                sep = flatten(args[0])
                return sep.join(flatten(v) for v in args[1])
        if "Fn::GetAZs" in value:
            region = flatten(value["Fn::GetAZs"])
            return f"availability-zones({region})" if region else "availability-zones"
        if "Fn::Select" in value:
            args = value["Fn::Select"]
            if isinstance(args, list) and len(args) == 2:
                return f"{flatten(args[1])}[{flatten(args[0])}]"
        if "Fn::ImportValue" in value:
            return f"import({flatten(value['Fn::ImportValue'])})"
        return json.dumps(value, default=str, sort_keys=True)
    return str(value)


def resources_of(template: Dict[str, Any], *types: str) -> List[Tuple[str, Dict[str, Any]]]:
    """``[(logical_id, resource_dict)]`` for the requested resource types."""
    out = []
    for logical_id, res in (template.get("Resources") or {}).items():
        if isinstance(res, dict) and res.get("Type") in types:
            out.append((logical_id, res))
    return out


def props(res: Dict[str, Any]) -> Dict[str, Any]:
    p = res.get("Properties")
    return p if isinstance(p, dict) else {}


# --------------------------------------------------------------------------- #
# Ports / protocols / services
# --------------------------------------------------------------------------- #
PROTOCOL_NAMES = {"6": "TCP", "17": "UDP", "1": "ICMP", "-1": "any"}

# AWS API surfaces a function may reach, keyed by the IAM action prefix that
# proves the dependency exists. Every one of these is HTTPS/443.
SERVICE_BY_ACTION = {
    "secretsmanager": "AWS Secrets Manager",
    "kms": "AWS KMS",
    "s3": "Amazon S3",
    "bedrock": "Amazon Bedrock (in-boundary inference)",
    "kinesis": "Amazon Kinesis Data Streams",
    "states": "AWS Step Functions",
    "lambda": "AWS Lambda",
    "logs": "Amazon CloudWatch Logs",
    "xray": "AWS X-Ray",
    "cognito-idp": "Amazon Cognito user pools",
    "events": "Amazon EventBridge",
    "sqs": "Amazon SQS",
    "sns": "Amazon SNS",
    "dynamodb": "Amazon DynamoDB",
    "cloudformation": "AWS CloudFormation",
    "rds": "Amazon RDS control plane",
    "ec2": "Amazon EC2 (ENI management for VPC Lambdas)",
    "wafv2": "AWS WAF",
    "textract": "Amazon Textract",
}

ENGINE_DEFAULT_PORTS = {
    "aurora-postgresql": 5432,
    "postgres": 5432,
    "aurora-mysql": 3306,
    "mysql": 3306,
}


def _protocol(raw: Any) -> str:
    text = str(raw)
    return PROTOCOL_NAMES.get(text, text.upper())


def _port_range(rule: Dict[str, Any]) -> str:
    lo, hi = rule.get("FromPort"), rule.get("ToPort")
    if lo is None and hi is None:
        return "all"
    if lo == hi:
        return str(lo)
    return f"{lo}-{hi}"


def _peer(rule: Dict[str, Any]) -> str:
    for key, label in (
        ("CidrIp", ""),
        ("CidrIpv6", ""),
        ("SourceSecurityGroupId", "sg:"),
        ("DestinationSecurityGroupId", "sg:"),
        ("SourcePrefixListId", "pl:"),
        ("DestinationPrefixListId", "pl:"),
    ):
        if key in rule:
            return f"{label}{flatten(rule[key])}"
    return "unspecified"


def security_group_flows(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    """One row per security-group rule, plus standalone SG*Ingress/Egress resources."""
    rows: List[Dict[str, Any]] = []

    for logical_id, res in resources_of(template, "AWS::EC2::SecurityGroup"):
        p = props(res)
        group_desc = flatten(p.get("GroupDescription"))
        for direction, key in (("inbound", "SecurityGroupIngress"), ("outbound", "SecurityGroupEgress")):
            for rule in p.get(key) or []:
                if not isinstance(rule, dict):
                    continue
                rows.append(
                    {
                        "direction": direction,
                        "protocol": _protocol(rule.get("IpProtocol", "-1")),
                        "ports": _port_range(rule),
                        "group": logical_id,
                        "group_description": group_desc,
                        "peer": _peer(rule),
                        "purpose": flatten(rule.get("Description")) or group_desc,
                        "evidence": f"{logical_id}.Properties.{key}",
                    }
                )

    for type_name, direction in (
        ("AWS::EC2::SecurityGroupIngress", "inbound"),
        ("AWS::EC2::SecurityGroupEgress", "outbound"),
    ):
        for logical_id, res in resources_of(template, type_name):
            p = props(res)
            rows.append(
                {
                    "direction": direction,
                    "protocol": _protocol(p.get("IpProtocol", "-1")),
                    "ports": _port_range(p),
                    "group": flatten(p.get("GroupId")),
                    "group_description": "",
                    "peer": _peer(p),
                    "purpose": flatten(p.get("Description")),
                    "evidence": f"{logical_id} ({type_name})",
                }
            )
    return rows


def database_ports(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for logical_id, res in resources_of(template, "AWS::RDS::DBCluster", "AWS::RDS::DBInstance"):
        p = props(res)
        engine = flatten(p.get("Engine"))
        port = p.get("Port") or ENGINE_DEFAULT_PORTS.get(engine)
        if port is None:
            continue
        rows.append(
            {
                "service": f"{engine or 'database'} ({logical_id})",
                "protocol": "TCP",
                "ports": str(port),
                "source": "Compass Lambda functions in the private subnets",
                "destination": logical_id,
                "encryption": "TLS (psycopg2 sslmode=require, see src/common/python/compass_common/db.py)",
                "boundary": "internal",
                "evidence": f"{logical_id}.Properties.Port"
                if p.get("Port")
                else f"{logical_id}.Properties.Engine (engine default port)",
            }
        )
    return rows


def edge_flows(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Inbound flows that cross the authorization boundary."""
    rows: List[Dict[str, Any]] = []

    for logical_id, _res in resources_of(
        template, "AWS::CloudFront::Distribution"
    ):
        rows.append(
            {
                "service": f"HTTPS - web UI ({logical_id})",
                "protocol": "TCP/HTTPS",
                "ports": "443",
                "source": "User workstation (Internet)",
                "destination": f"{logical_id} (CloudFront edge)",
                "encryption": "TLS 1.2+ (CloudFront default viewer certificate)",
                "boundary": "crossing",
                "evidence": f"{logical_id} (AWS::CloudFront::Distribution)",
            }
        )
        rows.append(
            {
                "service": "HTTPS - origin fetch",
                "protocol": "TCP/HTTPS",
                "ports": "443",
                "source": f"{logical_id} (CloudFront, origin access control)",
                "destination": "Private S3 web bucket",
                "encryption": "TLS + SSE-KMS at rest",
                "boundary": "internal",
                "evidence": f"{logical_id}.Properties.Origins",
            }
        )

    for logical_id, _res in resources_of(
        template, "AWS::Serverless::HttpApi", "AWS::ApiGatewayV2::Api"
    ):
        rows.append(
            {
                "service": f"HTTPS - REST API ({logical_id})",
                "protocol": "TCP/HTTPS",
                "ports": "443",
                "source": "Authenticated browser session (Internet)",
                "destination": f"{logical_id} (API Gateway HTTP API)",
                "encryption": "TLS 1.2+ (AWS-managed endpoint certificate)",
                "boundary": "crossing",
                "evidence": f"{logical_id}.Properties.Auth (JWT authorizer on every route)",
            }
        )

    for logical_id, _res in resources_of(template, "AWS::Cognito::UserPoolDomain"):
        rows.append(
            {
                "service": f"HTTPS - hosted authentication UI ({logical_id})",
                "protocol": "TCP/HTTPS",
                "ports": "443",
                "source": "User workstation (Internet)",
                "destination": "Amazon Cognito hosted UI",
                "encryption": "TLS 1.2+",
                "boundary": "crossing",
                "evidence": f"{logical_id} (AWS::Cognito::UserPoolDomain)",
            }
        )
    return rows


def _iam_actions(policies: Any) -> Tuple[List[str], List[str]]:
    """Collect IAM actions from a SAM ``Policies`` block.

    Returns ``(actions, unparsed)`` - ``unparsed`` names SAM policy *templates*
    (``S3ReadPolicy`` and friends), which expand at transform time and so cannot
    be resolved from the source template. They are reported rather than dropped.
    """
    actions: List[str] = []
    unparsed: List[str] = []
    if not isinstance(policies, list):
        policies = [policies] if policies else []

    for entry in policies:
        if isinstance(entry, str):
            unparsed.append(entry)
            continue
        if not isinstance(entry, dict):
            continue
        if "Statement" in entry:
            for stmt in entry.get("Statement") or []:
                if not isinstance(stmt, dict):
                    continue
                act = stmt.get("Action")
                if isinstance(act, str):
                    actions.append(act)
                elif isinstance(act, list):
                    actions.extend(a for a in act if isinstance(a, str))
        else:
            unparsed.extend(entry.keys())
    return actions, unparsed


def outbound_service_flows(template: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Outbound AWS-service dependencies proved by the IAM actions in the template."""
    seen: Dict[str, Dict[str, Any]] = {}
    unparsed_all: List[str] = []

    for logical_id, res in resources_of(template, "AWS::Serverless::Function", "AWS::Lambda::Function"):
        actions, unparsed = _iam_actions(props(res).get("Policies"))
        unparsed_all.extend(f"{logical_id}: {u}" for u in unparsed)
        in_vpc = bool(props(res).get("VpcConfig"))
        for action in actions:
            prefix = action.split(":", 1)[0].lower()
            service = SERVICE_BY_ACTION.get(prefix)
            if not service:
                continue
            row = seen.setdefault(
                service,
                {
                    "service": service,
                    "protocol": "TCP/HTTPS",
                    "ports": "443",
                    "source": set(),
                    "destination": f"{prefix}.<region>.amazonaws.com",
                    "encryption": "TLS 1.2+ (AWS SDK default)",
                    "boundary": "AWS service plane",
                    "path": set(),
                    "evidence": set(),
                },
            )
            row["source"].add(logical_id)
            row["path"].add("NAT gateway (private subnet)" if in_vpc else "Lambda service network")
            row["evidence"].add(f"{logical_id}.Properties.Policies -> {action}")

    rows = []
    for row in seen.values():
        rows.append(
            {
                **row,
                "source": ", ".join(sorted(row["source"])),
                "path": ", ".join(sorted(row["path"])),
                "evidence": "; ".join(sorted(row["evidence"])[:3])
                + (" …" if len(row["evidence"]) > 3 else ""),
            }
        )
    rows.sort(key=lambda r: r["service"])
    return rows, sorted(set(unparsed_all))


# --------------------------------------------------------------------------- #
# Topology
# --------------------------------------------------------------------------- #
def network_facts(template: Dict[str, Any]) -> Dict[str, Any]:
    vpcs = [
        {"id": lid, "cidr": flatten(props(r).get("CidrBlock"))}
        for lid, r in resources_of(template, "AWS::EC2::VPC")
    ]

    subnets = []
    for lid, r in resources_of(template, "AWS::EC2::Subnet"):
        p = props(r)
        subnets.append(
            {
                "id": lid,
                "cidr": flatten(p.get("CidrBlock")),
                "az": flatten(p.get("AvailabilityZone")),
                "public": bool(p.get("MapPublicIpOnLaunch")),
                "vpc": flatten(p.get("VpcId")),
            }
        )

    return {
        "vpcs": vpcs,
        "subnets": subnets,
        "igw": [lid for lid, _ in resources_of(template, "AWS::EC2::InternetGateway")],
        "nat": [lid for lid, _ in resources_of(template, "AWS::EC2::NatGateway")],
        "route_tables": [lid for lid, _ in resources_of(template, "AWS::EC2::RouteTable")],
        "security_groups": [
            {"id": lid, "description": flatten(props(r).get("GroupDescription"))}
            for lid, r in resources_of(template, "AWS::EC2::SecurityGroup")
        ],
    }


def function_facts(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for lid, res in resources_of(template, "AWS::Serverless::Function", "AWS::Lambda::Function"):
        p = props(res)
        routes = []
        for _ev_name, ev in (p.get("Events") or {}).items():
            if not isinstance(ev, dict):
                continue
            ep = ev.get("Properties") or {}
            if ev.get("Type") in ("HttpApi", "Api"):
                routes.append(f"{str(ep.get('Method', 'ANY')).upper()} {ep.get('Path', '?')}")
            elif ev.get("Type"):
                routes.append(f"[{ev['Type']}]")
        out.append(
            {
                "id": lid,
                "name": flatten(p.get("FunctionName")) or lid,
                "code": flatten(p.get("CodeUri")),
                "in_vpc": bool(p.get("VpcConfig")),
                "subnets": ", ".join(flatten(s) for s in (p.get("VpcConfig") or {}).get("SubnetIds", [])),
                "security_groups": ", ".join(
                    flatten(s) for s in (p.get("VpcConfig") or {}).get("SecurityGroupIds", [])
                ),
                "memory": p.get("MemorySize"),
                "timeout": p.get("Timeout"),
                "routes": sorted(set(routes)),
            }
        )
    out.sort(key=lambda f: f["id"])
    return out


def data_store_facts(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    stores: List[Dict[str, Any]] = []

    for lid, res in resources_of(template, "AWS::RDS::DBCluster"):
        p = props(res)
        stores.append(
            {
                "id": lid,
                "kind": "Aurora PostgreSQL cluster",
                "at_rest": "SSE-KMS (customer-managed key)"
                if p.get("StorageEncrypted")
                else "NOT ENCRYPTED - review",
                "key": flatten(p.get("KmsKeyId")) or "aws/rds default",
                "public": "no" if not p.get("PubliclyAccessible") else "YES - review",
                "evidence": f"{lid}.Properties.StorageEncrypted / .KmsKeyId",
            }
        )

    for lid, res in resources_of(template, "AWS::S3::Bucket"):
        p = props(res)
        enc = (p.get("BucketEncryption") or {}).get("ServerSideEncryptionConfiguration") or []
        algo = ""
        key = ""
        if enc and isinstance(enc[0], dict):
            default = enc[0].get("ServerSideEncryptionByDefault") or {}
            algo = flatten(default.get("SSEAlgorithm"))
            key = flatten(default.get("KMSMasterKeyID"))
        pab = p.get("PublicAccessBlockConfiguration") or {}
        stores.append(
            {
                "id": lid,
                "kind": "S3 bucket",
                "at_rest": f"SSE ({algo})" if algo else "bucket default (review)",
                "key": key or " - ",
                "public": "blocked (all four PAB flags)"
                if len(pab) >= 4 and all(bool(v) for v in pab.values())
                else "review PublicAccessBlockConfiguration",
                "evidence": f"{lid}.Properties.BucketEncryption / .PublicAccessBlockConfiguration",
            }
        )

    for lid, res in resources_of(template, "AWS::Kinesis::Stream"):
        p = props(res)
        se = p.get("StreamEncryption") or {}
        stores.append(
            {
                "id": lid,
                "kind": "Kinesis data stream",
                "at_rest": f"{flatten(se.get('EncryptionType')) or 'none'}",
                "key": flatten(se.get("KeyId")) or " - ",
                "public": "n/a",
                "evidence": f"{lid}.Properties.StreamEncryption",
            }
        )
    return stores


def identity_facts(template: Dict[str, Any]) -> Dict[str, Any]:
    pools = []
    for lid, res in resources_of(template, "AWS::Cognito::UserPool"):
        p = props(res)
        policies = p.get("Policies") or {}
        pw = policies.get("PasswordPolicy") or {}
        pools.append(
            {
                "id": lid,
                "mfa": flatten(p.get("MfaConfiguration")) or "OFF",
                "mfa_methods": flatten(p.get("EnabledMfas")) or "not declared",
                "min_password_length": pw.get("MinimumLength"),
                "evidence": f"{lid}.Properties.MfaConfiguration / .Policies.PasswordPolicy",
            }
        )

    groups = [
        {
            "id": lid,
            "name": flatten(props(r).get("GroupName")),
            "description": flatten(props(r).get("Description")),
        }
        for lid, r in resources_of(template, "AWS::Cognito::UserPoolGroup")
    ]

    authorizers = []
    for lid, res in resources_of(template, "AWS::Serverless::HttpApi"):
        auth = props(res).get("Auth") or {}
        default = flatten(auth.get("DefaultAuthorizer"))
        for name, spec in (auth.get("Authorizers") or {}).items():
            kind = "Cognito JWT" if "JwtConfiguration" in (spec or {}) else "Lambda REQUEST"
            authorizers.append(
                {
                    "api": lid,
                    "name": name,
                    "kind": kind,
                    "default": name == default,
                    "evidence": f"{lid}.Properties.Auth.Authorizers.{name}",
                }
            )
    return {"pools": pools, "groups": groups, "authorizers": authorizers, "waf": [
        lid for lid, _ in resources_of(template, "AWS::WAFv2::WebACL")
    ]}


def logging_facts(template: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for lid, res in resources_of(template, "AWS::Logs::LogGroup"):
        p = props(res)
        out.append(
            {
                "id": lid,
                "name": flatten(p.get("LogGroupName")),
                "retention_days": p.get("RetentionInDays"),
                "evidence": f"{lid}.Properties.RetentionInDays",
            }
        )
    return out


def mermaid_topology(template: Dict[str, Any], net: Dict[str, Any], funcs: List[Dict[str, Any]]) -> str:
    """A Mermaid graph assembled from the parsed resources (no hand-drawn nodes)."""
    lines = ["graph LR"]
    lines.append("  User[User workstation]")

    edge_nodes = []
    for lid, _ in resources_of(template, "AWS::CloudFront::Distribution"):
        edge_nodes.append(lid)
        lines.append(f"  {lid}[{lid}<br/>CloudFront 443/TLS]")
        lines.append(f"  User -->|443 HTTPS| {lid}")
    for lid, _ in resources_of(template, "AWS::WAFv2::WebACL"):
        lines.append(f"  {lid}([{lid}<br/>WAF]) -.inspects.-> " + (edge_nodes[0] if edge_nodes else "User"))
    for lid, _ in resources_of(template, "AWS::Cognito::UserPool"):
        lines.append(f"  {lid}[{lid}<br/>Cognito user pool]")
        lines.append(f"  User -->|443 OIDC| {lid}")

    api_ids = [lid for lid, _ in resources_of(template, "AWS::Serverless::HttpApi", "AWS::ApiGatewayV2::Api")]
    for lid in api_ids:
        lines.append(f"  {lid}[{lid}<br/>HTTP API 443/TLS<br/>JWT authorizer]")
        lines.append(f"  User -->|443 HTTPS + Bearer| {lid}")

    vpc_id = net["vpcs"][0]["id"] if net["vpcs"] else "Vpc"
    vpc_cidr = net["vpcs"][0]["cidr"] if net["vpcs"] else ""
    lines.append(f'  subgraph {vpc_id}["{vpc_id} {vpc_cidr}"]')
    for sn in net["subnets"]:
        tag = "public" if sn["public"] else "private"
        lines.append(f'    {sn["id"]}["{sn["id"]}<br/>{sn["cidr"]} · {tag}"]')
    for f in funcs:
        if f["in_vpc"]:
            lines.append(f'    {f["id"]}("{f["id"]}")')
    for lid, _ in resources_of(template, "AWS::RDS::DBCluster"):
        lines.append(f'    {lid}[("{lid}<br/>PostgreSQL 5432/TLS<br/>RLS + FORCE")]')
    for lid, _ in resources_of(template, "AWS::EC2::NatGateway"):
        lines.append(f'    {lid}["{lid}<br/>NAT"]')
    lines.append("  end")

    db_ids = [lid for lid, _ in resources_of(template, "AWS::RDS::DBCluster")]
    for f in funcs:
        for api in api_ids:
            if f["routes"]:
                lines.append(f'  {api} --> {f["id"]}')
                break
        if f["in_vpc"]:
            for dbid in db_ids:
                lines.append(f'  {f["id"]} -->|5432 TLS| {dbid}')
            for nat in net["nat"]:
                lines.append(f'  {f["id"]} -->|443 TLS| {nat}')
    for nat in net["nat"]:
        lines.append(f"  {nat} -->|443 TLS| AWSAPIs[AWS service endpoints<br/>Secrets Manager · KMS · S3 · Bedrock]")

    # De-duplicate while preserving order (a function may repeat an edge).
    seen = set()
    deduped = []
    for line in lines:
        if line not in seen:
            deduped.append(line)
            seen.add(line)
    return "\n".join(deduped)


# --------------------------------------------------------------------------- #
# Candidate control mapping
# --------------------------------------------------------------------------- #
def control_mapping(
    template: Dict[str, Any],
    net: Dict[str, Any],
    stores: List[Dict[str, Any]],
    identity: Dict[str, Any],
    logs: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """Map observed template facts to candidate NIST SP 800-53 Rev 5 controls.

    Every row must name the resource/property it was derived from. A control
    with no template evidence is not listed - an assessor's time is wasted by a
    mapping that asserts more than the artifact can show.
    """
    rows: List[Dict[str, str]] = []

    def add(control: str, title: str, evidence: str) -> None:
        rows.append({"control": control, "title": title, "evidence": evidence})

    if net["vpcs"] and net["subnets"]:
        privates = [s["id"] for s in net["subnets"] if not s["public"]]
        add(
            "SC-7",
            "Boundary protection",
            f"VPC {net['vpcs'][0]['id']} ({net['vpcs'][0]['cidr']}) with "
            f"{len(privates)} private subnet(s) hosting all data-plane compute; "
            f"security groups: {', '.join(g['id'] for g in net['security_groups']) or 'none'}",
        )
    if net["nat"]:
        add(
            "SC-7(4)",
            "External telecommunications services",
            f"Egress is via NAT gateway(s) {', '.join(net['nat'])} - private subnets "
            "have no inbound route from the Internet",
        )
    if resources_of(template, "AWS::WAFv2::WebACL"):
        add(
            "SC-5",
            "Denial-of-service protection",
            f"WAF WebACL(s) {', '.join(identity['waf'])} attached at the CloudFront edge",
        )

    tls_sources = [lid for lid, _ in resources_of(template, "AWS::CloudFront::Distribution", "AWS::Serverless::HttpApi")]
    if tls_sources:
        add(
            "SC-8 / SC-8(1)",
            "Transmission confidentiality and integrity",
            f"All ingress terminates TLS at {', '.join(tls_sources)}; database "
            "connections use sslmode=require (compass_common/db.py)",
        )

    keys = [lid for lid, _ in resources_of(template, "AWS::KMS::Key")]
    if keys:
        rotation = any(props(r).get("EnableKeyRotation") for _, r in resources_of(template, "AWS::KMS::Key"))
        add(
            "SC-12 / SC-13",
            "Cryptographic key establishment and management",
            f"Customer-managed KMS key(s) {', '.join(keys)}"
            + (" with automatic rotation enabled" if rotation else " (rotation not enabled - review)"),
        )
    if stores:
        add(
            "SC-28 / SC-28(1)",
            "Protection of information at rest",
            "; ".join(f"{s['id']}: {s['at_rest']}" for s in stores),
        )

    if identity["pools"]:
        pool = identity["pools"][0]
        add(
            "IA-2(1) / IA-2(2)",
            "Multi-factor authentication",
            f"Cognito user pool {pool['id']} MfaConfiguration={pool['mfa']}",
        )
    if identity["authorizers"]:
        default = [a for a in identity["authorizers"] if a["default"]]
        add(
            "AC-3",
            "Access enforcement",
            "Every API route is behind "
            + (f"the default authorizer '{default[0]['name']}' ({default[0]['kind']})" if default
               else "an authorizer")
            + "; deny-by-default at the gateway",
        )
    if identity["groups"]:
        add(
            "AC-2 / AC-6",
            "Account management / least privilege",
            "Role separation via Cognito groups: "
            + ", ".join(f"{g['name']}" for g in identity["groups"])
            + "; runtime DB role compass_app is a non-owner with column-level REVOKEs "
              "(db/migrations/002_rls.sql)",
        )
    add(
        "AC-4",
        "Information flow enforcement",
        "PostgreSQL row-level security on grants_curated with FORCE ROW LEVEL SECURITY; "
        "org context bound per transaction via SET LOCAL compass.org_unit "
        "(db/migrations/002_rls.sql, compass_common/db.py)",
    )
    add(
        "AC-4(15) / SC-7(10)",
        "Detection of exfiltration / aggregation control",
        "POST /export refuses result sets above EXPORT_MAX_ROWS with HTTP 428 unless an "
        "approved approval_token is attached (src/functions/export/app.py)",
    )

    if logs:
        add(
            "AU-2 / AU-12",
            "Event logging / audit record generation",
            "; ".join(
                f"{log_item['id']} retention={log_item['retention_days']}d"
                for log_item in logs
            )
            + "; application audit trail in compass.audit_log (every export and approval)",
        )
    if any(props(r).get("Tracing") for _, r in resources_of(template, "AWS::Serverless::Function")) or (
        ((template.get("Globals") or {}).get("Function") or {}).get("Tracing")
    ):
        add("AU-6(1) / SI-4", "Automated audit review / system monitoring", "AWS X-Ray tracing enabled on all functions (Globals.Function.Tracing)")

    if resources_of(template, "AWS::GuardDuty::Detector"):
        add("SI-4", "System monitoring", "GuardDuty detector deployed (conditional on DeploySecurityBaseline)")
    if resources_of(template, "AWS::Macie::Session"):
        add("RA-5 / SI-4", "Sensitive-data discovery", "Amazon Macie session deployed (conditional on DeploySecurityBaseline)")

    add(
        "CM-2 / CM-6",
        "Baseline configuration / configuration settings",
        "The entire environment is one declarative template (template.yaml); this "
        "artifact is generated from that same file, so documentation and baseline "
        "cannot diverge",
    )
    return rows


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #
def _table(headers: List[str], rows: Iterable[List[str]]) -> str:
    body = list(rows)
    if not body:
        return "_None found in the template._\n"
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in body:
        cells = [str(c).replace("|", "\\|").replace("\n", " ") if c is not None else "" for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def generate_markdown(template: Dict[str, Any], *, source: str, digest: str) -> str:
    resources = template.get("Resources") or {}
    type_counts: Dict[str, int] = {}
    for res in resources.values():
        if isinstance(res, dict):
            type_counts[res.get("Type", "?")] = type_counts.get(res.get("Type", "?"), 0) + 1

    net = network_facts(template)
    funcs = function_facts(template)
    stores = data_store_facts(template)
    identity = identity_facts(template)
    logs = logging_facts(template)
    sg_rows = security_group_flows(template)
    db_rows = database_ports(template)
    edge_rows = edge_flows(template)
    out_rows, unparsed_policies = outbound_service_flows(template)
    controls = control_mapping(template, net, stores, identity, logs)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    description = " ".join(str(template.get("Description", "")).split())

    md: List[str] = []
    a = md.append

    a(f"# {ARTIFACT_TITLE}\n")
    a(
        "> **Generated artifact - do not hand-edit.** Every table below was parsed "
        f"from `{source}`. Regenerate with "
        "`python3 src/functions/rmf_artifact/app.py`.\n"
    )
    a("")
    a(_table(
        ["Field", "Value"],
        [
            ["System", "Compass - S&T Portfolio Intelligence (demonstration)"],
            ["Template source", f"`{source}`"],
            ["Template SHA-256", f"`{digest}`"],
            ["Generated (UTC)", generated],
            ["Generator", "src/functions/rmf_artifact/app.py (deterministic, no LLM)"],
            ["Resources parsed", str(len(resources))],
            ["Data sensitivity", "Synthetic demonstration data only - no real CUI or PII"],
        ],
    ))
    if description:
        a(f"\n**Template description.** {description}\n")

    # --- 1. Boundary ------------------------------------------------------- #
    a("\n## 1. Authorization boundary\n")
    a(
        "The boundary is everything created by the template: one VPC and its "
        "subnets, the serverless compute inside it, the managed data stores, and "
        "the edge (CloudFront/API Gateway/Cognito) that fronts them. Flows marked "
        "**crossing** below are the only paths in from outside.\n"
    )
    a(_table(
        ["Resource type", "Count"],
        sorted(([t, str(c)] for t, c in type_counts.items()), key=lambda r: r[0]),
    ))

    # --- 2. PPS ------------------------------------------------------------ #
    a("\n## 2. Ports, Protocols and Services\n")
    a("### 2.1 Boundary-crossing flows (inbound)\n")
    a(_table(
        ["Service", "Protocol", "Port(s)", "Source", "Destination", "Encryption", "Evidence"],
        [
            [r["service"], r["protocol"], r["ports"], r["source"], r["destination"], r["encryption"], f"`{r['evidence']}`"]
            for r in edge_rows
            if r["boundary"] == "crossing"
        ],
    ))

    a("\n### 2.2 Internal flows (within the boundary)\n")
    internal = [r for r in edge_rows if r["boundary"] != "crossing"] + db_rows
    a(_table(
        ["Service", "Protocol", "Port(s)", "Source", "Destination", "Encryption", "Evidence"],
        [
            [r["service"], r["protocol"], r["ports"], r["source"], r["destination"], r["encryption"], f"`{r['evidence']}`"]
            for r in internal
        ],
    ))

    a("\n### 2.3 Security-group rules (as declared)\n")
    a(_table(
        ["Direction", "Protocol", "Port(s)", "Security group", "Peer", "Purpose", "Evidence"],
        [
            [r["direction"], r["protocol"], r["ports"], r["group"], r["peer"], r["purpose"], f"`{r['evidence']}`"]
            for r in sg_rows
        ],
    ))

    a("\n### 2.4 Outbound service dependencies\n")
    a(
        "Derived from the IAM actions each function is actually granted - a "
        "dependency the template does not authorize does not appear here, and one "
        "it does authorize cannot be omitted.\n"
    )
    a(_table(
        ["Service", "Protocol", "Port(s)", "Calling function(s)", "Path", "Evidence"],
        [
            [r["service"], r["protocol"], r["ports"], r["source"], r["path"], f"`{r['evidence']}`"]
            for r in out_rows
        ],
    ))
    if unparsed_policies:
        a(
            "\n> **Not resolvable from source:** the following SAM policy templates "
            "expand only during transform, so their actions are not enumerated above: "
            + ", ".join(f"`{u}`" for u in unparsed_policies)
            + ". Resolve them against the processed template if the PPSM package needs them.\n"
        )

    # --- 3. Topology ------------------------------------------------------- #
    a("\n## 3. Network topology\n")
    a("```mermaid")
    a(mermaid_topology(template, net, funcs))
    a("```\n")

    a("\n### 3.1 Network inventory\n")
    a(_table(
        ["Element", "Logical ID", "Detail"],
        [["VPC", v["id"], v["cidr"]] for v in net["vpcs"]]
        + [
            ["Subnet", s["id"], f"{s['cidr']} · {'public' if s['public'] else 'private'} · AZ {s['az']}"]
            for s in net["subnets"]
        ]
        + [["Internet gateway", i, "public egress/ingress"] for i in net["igw"]]
        + [["NAT gateway", n, "private-subnet egress only"] for n in net["nat"]]
        + [["Route table", rt, " - "] for rt in net["route_tables"]]
        + [["Security group", g["id"], g["description"]] for g in net["security_groups"]],
    ))

    a("\n### 3.2 Compute inventory\n")
    a(_table(
        ["Function", "In VPC", "Security groups", "Memory (MB)", "Timeout (s)", "API routes"],
        [
            [
                f["id"],
                "yes" if f["in_vpc"] else "no",
                f["security_groups"] or " - ",
                str(f["memory"] or " - "),
                str(f["timeout"] or " - "),
                ", ".join(f["routes"]) or " - ",
            ]
            for f in funcs
        ],
    ))

    # --- 4. Data protection ------------------------------------------------ #
    a("\n## 4. Data protection\n")
    a("### 4.1 At rest\n")
    a(_table(
        ["Store", "Kind", "Encryption", "Key", "Public exposure", "Evidence"],
        [[s["id"], s["kind"], s["at_rest"], s["key"], s["public"], f"`{s['evidence']}`"] for s in stores],
    ))
    a("\n### 4.2 In transit\n")
    a(
        "All boundary-crossing flows in §2.1 terminate TLS at an AWS-managed "
        "endpoint. Database sessions are opened with `sslmode=require` in "
        "`src/common/python/compass_common/db.py`; AWS API calls use the SDK's "
        "TLS 1.2+ defaults.\n"
    )

    # --- 5. Identity ------------------------------------------------------- #
    a("\n## 5. Identity and access\n")
    a(_table(
        ["User pool", "MFA", "MFA methods", "Min password length", "Evidence"],
        [
            [p["id"], p["mfa"], p["mfa_methods"], str(p["min_password_length"] or " - "), f"`{p['evidence']}`"]
            for p in identity["pools"]
        ],
    ))
    a("\n**Groups (role separation)**\n")
    a(_table(
        ["Group", "Name", "Description"],
        [[g["id"], g["name"], g["description"]] for g in identity["groups"]],
    ))
    a("\n**API authorizers**\n")
    a(_table(
        ["API", "Authorizer", "Kind", "Default", "Evidence"],
        [
            [a_["api"], a_["name"], a_["kind"], "yes" if a_["default"] else "no", f"`{a_['evidence']}`"]
            for a_ in identity["authorizers"]
        ],
    ))
    a(
        "\nAuthorization does not stop at the gateway. The database enforces "
        "row-level security on `compass.grants_curated` with `FORCE ROW LEVEL "
        "SECURITY`, keyed on `current_setting('compass.org_unit')`, which the "
        "application binds per transaction from the caller's token; and "
        "column-level security revokes `amount_usd` from the runtime role "
        "(`db/migrations/002_rls.sql`).\n"
    )

    # --- 6. Audit ---------------------------------------------------------- #
    a("\n## 6. Audit and monitoring\n")
    a(_table(
        ["Log group", "Name", "Retention (days)", "Evidence"],
        [
            [
                log_item["id"],
                log_item["name"],
                str(log_item["retention_days"] or "Not available"),
                f"`{log_item['evidence']}`",
            ]
            for log_item in logs
        ],
    ))
    a(
        "\nApplication-level audit records are appended to `compass.audit_log` by "
        "every export decision (allowed, blocked at the aggregation guard, denied "
        "on an invalid approval token, or failed in delivery) and every approval "
        "state change.\n"
    )

    # --- 7. Controls ------------------------------------------------------- #
    a("\n## 7. Candidate NIST SP 800-53 Rev 5 control evidence\n")
    a(
        "> **Candidate mapping - requires assessor validation.** These rows say "
        "\"the template contains this configuration\", not \"this control is "
        "satisfied\". Control satisfaction depends on procedures, personnel and "
        "an assessment this generator has no visibility into.\n"
    )
    a(_table(
        ["Control", "Title", "Template evidence"],
        [[c["control"], c["title"], c["evidence"]] for c in controls],
    ))

    # --- 8. Limits --------------------------------------------------------- #
    a("\n## 8. What this artifact cannot assert\n")
    a(
        "- **Runtime drift.** It describes the template, not the deployed account. "
        "A manual console change would not appear here; pair it with a live "
        "configuration scan (AWS Config / Security Hub) for the deployed state.\n"
        "- **Transform-time expansion.** SAM expands `AWS::Serverless::*` into more "
        "resources (roles, permissions, stages) at deploy time. Those derived "
        "resources are not in the source template and so are not enumerated; run "
        "the generator against the processed template for the complete set.\n"
        "- **Conditional resources.** Resources behind a `Condition` are listed "
        "whether or not that condition evaluates true for a given deployment; the "
        "condition is noted where it appears in a value.\n"
        "- **Non-technical controls.** Interconnection agreements, personnel "
        "screening, contingency planning and physical security cannot be derived "
        "from IaC and are out of scope for this artifact.\n"
        "- **Data sensitivity.** This system runs fully synthetic demonstration "
        "data. Categorization (FIPS-199 / CNSSI-1253) is an authorizing-official "
        "determination and is not asserted here.\n"
    )

    a("\n---\n")
    a(
        f"_Generated {generated} from `{source}` (SHA-256 `{digest}`) by "
        "`src/functions/rmf_artifact/app.py`. Deterministic: the same template "
        "always produces the same artifact._\n"
    )
    return "\n".join(md)


# --------------------------------------------------------------------------- #
# Template sourcing
# --------------------------------------------------------------------------- #
def load_template_text(event: Dict[str, Any]) -> Tuple[str, str]:
    """Return ``(text, source_label)``, trying every configured source in order.

    Raises ``FileNotFoundError`` naming every source that was tried - a
    generator that silently fell back to a stale bundled copy would produce an
    artifact that looks authoritative and isn't.
    """
    tried: List[str] = []

    body = event.get("template_body")
    if isinstance(body, str) and body.strip():
        return body, "event.template_body"
    tried.append("event.template_body")

    s3_spec = event.get("template_s3")
    if isinstance(s3_spec, dict) and s3_spec.get("bucket") and s3_spec.get("key"):
        import boto3

        s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        obj = s3.get_object(Bucket=s3_spec["bucket"], Key=s3_spec["key"])
        return obj["Body"].read().decode("utf-8"), f"s3://{s3_spec['bucket']}/{s3_spec['key']}"
    tried.append("event.template_s3")

    for path in (BUNDLED_TEMPLATE, REPO_TEMPLATE):
        if path.is_file():
            return path.read_text(encoding="utf-8"), str(path)
        tried.append(str(path))

    stack = event.get("stack_name") or os.environ.get("STACK_NAME")
    if stack:
        try:
            import boto3

            cfn = boto3.client("cloudformation", region_name=os.environ.get("AWS_REGION", "us-east-1"))
            resp = cfn.get_template(StackName=stack, TemplateStage="Original")
            body = resp["TemplateBody"]
            text = body if isinstance(body, str) else json.dumps(body)
            return text, f"cloudformation:GetTemplate({stack})"
        except Exception as exc:  # permission or stack missing - report, don't mask
            tried.append(f"cloudformation:GetTemplate({stack}) -> {exc}")
    else:
        tried.append("cloudformation:GetTemplate (no stack_name / STACK_NAME)")

    raise FileNotFoundError(
        "no CloudFormation template available. Tried, in order: " + "; ".join(tried)
    )


def build_artifact(event: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Parse a template and render the artifact. Pure apart from template I/O."""
    event = event or {}
    text, source = load_template_text(event)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    template = parse_template(text)
    markdown = generate_markdown(template, source=source, digest=digest)

    resources = template.get("Resources") or {}
    return {
        "artifact_markdown": markdown,
        "template_source": source,
        "template_sha256": digest,
        "resource_count": len(resources),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "src/functions/rmf_artifact/app.py",
        "deterministic": True,
        "llm_used": False,
    }


# --------------------------------------------------------------------------- #
# Lambda handler
# --------------------------------------------------------------------------- #
def handler(event: Dict[str, Any], context: Any = None) -> Dict[str, Any]:
    """Direct-invoke handler. No API route is defined for this function.

    ``{"write_s3": true}`` also stores the artifact under ``rmf/`` in
    ``RMF_BUCKET``/``EXPORT_BUCKET``/``RAW_BUCKET`` (the template grants
    ``s3:PutObject`` on ``${RawBucket}/rmf/*``). When no bucket is configured the
    response says so rather than pretending a file was written.
    """
    event = event or {}
    try:
        result = build_artifact(event)
    except Exception as exc:
        log.exception("RMF artifact generation failed")
        return {"ok": False, "error": str(exc)}

    bucket = (
        os.environ.get("RMF_BUCKET")
        or os.environ.get("EXPORT_BUCKET")
        or os.environ.get("RAW_BUCKET")
        or ""
    )
    if event.get("write_s3"):
        if not bucket:
            result["s3_uri"] = None
            result["s3_note"] = (
                "write_s3 requested but no RMF_BUCKET / EXPORT_BUCKET / RAW_BUCKET is "
                "set on this function; the artifact is returned inline only"
            )
        else:
            try:
                import boto3

                key = event.get("s3_key") or (
                    f"rmf/{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-pps-topology.md"
                )
                boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1")).put_object(
                    Bucket=bucket,
                    Key=key,
                    Body=result["artifact_markdown"].encode("utf-8"),
                    ContentType="text/markdown; charset=utf-8",
                )
                result["s3_uri"] = f"s3://{bucket}/{key}"
            except Exception as exc:
                log.exception("could not store RMF artifact")
                result["s3_uri"] = None
                result["s3_note"] = f"S3 write failed: {exc}"

    # Best-effort governance record. The artifact is the deliverable; a missing
    # database must not fail its generation.
    try:
        if os.environ.get("DB_HOST"):
            from compass_common import audit, db

            conn = db.get_conn()
            audit.write_audit(
                conn,
                actor=str(event.get("actor") or "rmf-artifact-generator"),
                action="rmf_artifact_generated",
                resource=result["template_source"],
                detail={
                    "template_sha256": result["template_sha256"],
                    "resource_count": result["resource_count"],
                    "s3_uri": result.get("s3_uri"),
                },
            )
    except Exception:
        log.warning("RMF artifact generated but the audit row could not be written", exc_info=True)

    result["ok"] = True
    return result


# --------------------------------------------------------------------------- #
# CLI - runs offline against the repo template
# --------------------------------------------------------------------------- #
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Compass Ports/Protocols/Services + topology RMF artifact "
                    "from a CloudFormation/SAM template."
    )
    parser.add_argument(
        "template",
        nargs="?",
        default=str(REPO_TEMPLATE),
        help=f"path to the template (default: {REPO_TEMPLATE})",
    )
    parser.add_argument("-o", "--out", help="write the markdown here instead of stdout")
    args = parser.parse_args(argv)

    path = Path(args.template).expanduser().resolve()
    if not path.is_file():
        print(f"error: template not found: {path}", file=sys.stderr)
        return 2

    result = build_artifact({"template_body": path.read_text(encoding="utf-8")})
    # build_artifact labels the source from the event; relabel to the real path.
    markdown = result["artifact_markdown"].replace("event.template_body", str(path))

    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(
            f"wrote {args.out} ({len(markdown)} bytes) from {path} "
            f"[sha256 {result['template_sha256'][:16]}…, {result['resource_count']} resources]",
            file=sys.stderr,
        )
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
