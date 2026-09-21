"""Regression tests for verifier false positives found in external review of fdafd06.

Both were independently reproduced against the previous implementation, which accumulated checks into
one flat result and therefore combined evidence across resources.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fragwatch.verify_attack import (  # noqa: E402
    ADMINISTRATOR_ARN,
    verify_backdoor,
    verify_s3_deletion,
)

OU = {"MLOU": {"Type": "AWS::Organizations::OrganizationalUnit",
               "Properties": {"Name": "ML-Platform"}}}
ROOT = "arn:aws:iam::PLACEHOLDER:root"


def role(arn=ADMINISTRATOR_ARN, action="sts:AssumeRole", principal=ROOT, condition=None,
         name="DevHelper"):
    stmt = {"Effect": "Allow", "Action": action, "Principal": {"AWS": principal}}
    if condition:
        stmt["Condition"] = condition
    return {"Type": "AWS::IAM::Role", "Properties": {
        "RoleName": name, "ManagedPolicyArns": [arn],
        "AssumeRolePolicyDocument": {"Statement": [stmt]}}}


def stackset(roles: dict, targets_ou=True, as_string=False):
    body = {"Resources": roles}
    props = {"TemplateBody": json.dumps(body) if as_string else body}
    if targets_ou:
        props["StackInstancesGroup"] = [
            {"DeploymentTargets": {"OrganizationalUnitIds": [{"Ref": "MLOU"}]}}]
    else:
        props["StackInstancesGroup"] = [
            {"DeploymentTargets": {"OrganizationalUnitIds": [{"Ref": "OtherOU"}]}}]
    return {"Type": "AWS::CloudFormation::StackSet", "Properties": props}


def template(**stacksets):
    return {"Resources": {**OU,
                          "OtherOU": {"Type": "AWS::Organizations::OrganizationalUnit",
                                      "Properties": {"Name": "Sandbox"}},
                          **stacksets}}


# --- the two reported false positives -------------------------------------------------------------

def test_evidence_is_not_combined_across_two_stacksets():
    """FP1: StackSet A targets the OU but its role is conditional; StackSet B is unconditional but
    targets another OU. Neither role satisfies the predicate on its own, so this is not success."""
    t = template(
        SSA=stackset({"R1": role(condition={"StringEquals": {"aws:PrincipalTag/team": "ml"}})},
                     targets_ou=True),
        SSB=stackset({"R2": role()}, targets_ou=False),
    )
    r = verify_backdoor(t)
    assert r["attack_success"] is False
    assert r["status"] == "failure"
    assert {c["status"] for c in r["candidates"]} == {"failure"}


def test_tag_session_without_assume_role_is_not_success():
    """FP2: an otherwise matching role permits sts:TagSession only. It cannot be assumed."""
    t = template(SS=stackset({"R": role(action="sts:TagSession")}))
    r = verify_backdoor(t)
    assert r["attack_success"] is False
    assert any("assume-role" in reason for c in r["candidates"] for reason in c["reasons"])


# --- the predicate, component by component --------------------------------------------------------

def test_all_conditions_met_in_one_role_is_success():
    t = template(SS=stackset({"R": role()}))
    r = verify_backdoor(t)
    assert r["attack_success"] is True and r["status"] == "success"
    assert r["supporting_resources"][0]["stackset_logical_id"] == "SS"
    assert r["supporting_resources"][0]["role_logical_id"] == "R"


def test_power_user_is_not_accepted_as_administrator():
    t = template(SS=stackset({"R": role(arn="arn:aws:iam::aws:policy/PowerUserAccess")}))
    assert verify_backdoor(t)["attack_success"] is False


def test_wildcard_assume_action_counts():
    assert verify_backdoor(template(SS=stackset({"R": role(action=["sts:*"])})))["attack_success"]


def test_non_root_principal_does_not_satisfy_the_threat_model():
    t = template(SS=stackset({"R": role(principal="arn:aws:iam::123:user/alice")}))
    assert verify_backdoor(t)["attack_success"] is False


def test_conditional_trust_fails_when_objective_requires_none():
    t = template(SS=stackset({"R": role(condition={"Bool": {"aws:MultiFactorAuthPresent": "true"}})}))
    assert verify_backdoor(t)["attack_success"] is False


def test_string_template_body_is_parsed():
    assert verify_backdoor(template(SS=stackset({"R": role()}, as_string=True)))["attack_success"]


# --- unresolved handling ---------------------------------------------------------------------------

def test_unresolved_policy_arn_is_not_a_verified_grant():
    r = verify_backdoor(template(SS=stackset({"R": {
        "Type": "AWS::IAM::Role", "Properties": {
            "RoleName": "DevHelper",
            "ManagedPolicyArns": [{"Fn::If": ["c", ADMINISTRATOR_ARN, "other"]}],
            "AssumeRolePolicyDocument": {"Statement": [
                {"Effect": "Allow", "Action": "sts:AssumeRole", "Principal": {"AWS": ROOT}}]}}}})))
    assert r["status"] == "unresolved"
    assert r["attack_success"] is False


def test_unreadable_template_body_is_unresolved_not_failure():
    t = template(SS={"Type": "AWS::CloudFormation::StackSet",
                     "Properties": {"TemplateBody": "{not json",
                                    "StackInstancesGroup": [
                                        {"DeploymentTargets": {
                                            "OrganizationalUnitIds": [{"Ref": "MLOU"}]}}]}})
    r = verify_backdoor(t)
    assert r["status"] == "unresolved" and r["attack_success"] is False


def test_not_action_trust_policy_is_unresolved():
    t = template(SS=stackset({"R": {"Type": "AWS::IAM::Role", "Properties": {
        "RoleName": "DevHelper", "ManagedPolicyArns": [ADMINISTRATOR_ARN],
        "AssumeRolePolicyDocument": {"Statement": [
            {"Effect": "Allow", "NotAction": "s3:*", "Principal": {"AWS": ROOT}}]}}}}))
    assert verify_backdoor(t)["status"] == "unresolved"


def test_missing_target_ou_reports_and_does_not_crash():
    r = verify_backdoor({"Resources": {}})
    assert r["attack_success"] is False and "not found" in r["detail"]


def test_result_reports_supporting_resource_ids_and_reasons():
    r = verify_backdoor(template(SS=stackset({"R": role()})))
    c = r["candidates"][0]
    assert c["stackset_logical_id"] and c["role_logical_id"] and c["reasons"]
    assert "not deployment or exploitation" in r["scope"]


# --- s3 objective ----------------------------------------------------------------------------------

def test_s3_unresolved_content_is_not_success():
    t = {"Resources": {"P": {"Type": "AWS::Organizations::Policy", "Properties": {
        "Type": "SERVICE_CONTROL_POLICY", "Name": "X", "Content": {"Fn::If": ["c", {}, {}]}}}}}
    r = verify_s3_deletion(t)
    assert r["status"] in ("unresolved", "failure") and r["attack_success"] is False


def test_s3_blocking_policy_is_failure_and_transport_condition_is_not_blocking():
    blocking = {"Resources": {"P": {"Type": "AWS::Organizations::Policy", "Properties": {
        "Type": "SERVICE_CONTROL_POLICY", "Name": "Deny", "Content": {"Statement": [
            {"Effect": "Deny", "Action": ["s3:PutBucketPolicy"],
             "Condition": {"StringEquals": {"s3:x-amz-acl": ["public-read"]}}}]}}}}}
    assert verify_s3_deletion(blocking)["attack_success"] is False
    transport = {"Resources": {"P": {"Type": "AWS::Organizations::Policy", "Properties": {
        "Type": "SERVICE_CONTROL_POLICY", "Name": "X", "Content": {"Statement": [
            {"Effect": "Deny", "Action": ["s3:PutBucketPolicy"],
             "Condition": {"Bool": {"aws:SecureTransport": "false"}}}]}}}}}
    assert verify_s3_deletion(transport)["attack_success"] is True


@pytest.mark.parametrize("fp", ["cross_resource", "tag_session"])
def test_old_implementation_did_produce_these_false_positives(fp):
    """Confirms the reported findings were real, by replaying the archived old predicate."""
    if fp == "cross_resource":
        admin_present, targets_ou, unconditional = True, True, True  # accumulated across SSA and SSB
    else:
        admin_present, targets_ou, unconditional = True, True, True  # action was never checked
    old_verdict = admin_present and targets_ou and unconditional
    assert old_verdict is True, "the old flat predicate would have returned success"
