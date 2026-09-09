#!/usr/bin/env python3
"""Validate saved Reports API results without printing recipient data or sending messages."""
import argparse
import json
import os
from pathlib import Path
import re
import sys


def read_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "result" in data:
        if data.get("status", 0) != 0:
            raise ValueError("Salesforce CLI response reports an error")
        return data["result"]
    return data


def record_id(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9]{15}(?:[A-Za-z0-9]{3})?", value) is not None


def validate(report, friend_describe, column_describe, column_field, first_column,
             friends=None, social_account_id=None):
    if not all(isinstance(item, dict) for item in [report, friend_describe, column_describe]):
        raise ValueError("Report and describe inputs must be JSON objects")
    prefix = friend_describe.get("keyPrefix")
    if friend_describe.get("name") != "igns__SocialFriend__c" or not prefix:
        raise ValueError("Use the target org's SocialFriend describe with keyPrefix")
    fields = {f["name"]: f for f in column_describe.get("fields", [])}
    field = fields.get(column_field, {})
    own_id = column_describe.get("name") == friend_describe["name"] and column_field == "Id" and field.get("type") == "id"
    friend_lookup = field.get("type") == "reference" and field.get("referenceTo") == [friend_describe["name"]]
    if not (own_id or friend_lookup):
        raise ValueError("First column must resolve to SocialFriend.Id or a native lookup to SocialFriend")
    metadata = report.get("reportMetadata", {})
    columns = metadata.get("detailColumns", [])
    if metadata.get("reportFormat") != "TABULAR" or not columns or columns[0] != first_column:
        raise ValueError("Report must be TABULAR with the verified SocialFriend column first")
    if report.get("allData") is not True:
        raise ValueError("Report is incomplete: allData must be true")
    rows = report.get("factMap", {}).get("T!T", {}).get("rows")
    if not isinstance(rows, list) or len(rows) > 2000:
        raise ValueError("Expected up to 2000 detail rows in T!T")
    ids = []
    for index, row in enumerate(rows, 1):
        cells = row.get("dataCells", [])
        if len(cells) != len(columns):
            raise ValueError(f"Row {index}: detail cell count does not match columns")
        value = cells[0].get("value")
        # A native Id column can be returned with the ID in label only.
        if value is None and own_id:
            value = cells[0].get("label")
        if not record_id(value) or not value.startswith(prefix):
            raise ValueError(f"Row {index}: first cell is blank or not a SocialFriend ID")
        ids.append(value)
    unique = sorted({value[:15] for value in ids})
    summary = {"rows": len(rows), "uniqueFriends": len(unique),
               "duplicateRows": len(rows) - len(unique), "firstColumnChecked": True,
               "recipientExistenceAndAccountChecked": False}
    if friends is not None:
        if not record_id(social_account_id):
            raise ValueError("A valid target social account ID is required for recipient checking")
        if not isinstance(friends, dict) or friends.get("done") is not True:
            raise ValueError("Recipient query must be complete (done=true)")
        found = {}
        for friend in friends.get("records", []):
            value = friend.get("Id")
            if not record_id(value):
                raise ValueError("Recipient query contains an invalid ID")
            found[value[:15]] = friend
        if set(unique) != set(found):
            raise ValueError("Recipient query does not exactly match all unique report IDs")
        for friend in found.values():
            account = friend.get("igns__SocialAccount__c")
            if not record_id(account) or account[:15] != social_account_id[:15]:
                raise ValueError("Recipient belongs to a different or missing social account")
        summary["recipientExistenceAndAccountChecked"] = bool(unique)
    return summary, unique


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ["report", "friend-describe", "column-describe", "column-field", "expected-first-column"]:
        parser.add_argument("--" + flag, required=True)
    parser.add_argument("--write-id-query", help="Write a read-only SOQL query to this local file")
    parser.add_argument("--friends", help="Saved sf data query --json result for all extracted IDs")
    parser.add_argument("--social-account-id")
    args = parser.parse_args()
    if bool(args.friends) != bool(args.social_account_id):
        parser.error("--friends and --social-account-id must be supplied together")
    try:
        summary, ids = validate(read_json(args.report), read_json(args.friend_describe),
                                read_json(args.column_describe), args.column_field,
                                args.expected_first_column,
                                read_json(args.friends) if args.friends else None,
                                args.social_account_id)
        if args.write_id_query:
            query = "SELECT Id, igns__SocialAccount__c FROM igns__SocialFriend__c WHERE "
            query += "Id IN (" + ",".join("'" + value + "'" for value in ids) + ")" if ids else "Id = NULL"
            path = Path(args.write_id_query)
            # IDs stay in a local file; never print report rows or personal data.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(query + "\n")
        print(json.dumps(summary, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        if isinstance(exc, json.JSONDecodeError):
            print("ERROR: invalid JSON input", file=sys.stderr)
        elif isinstance(exc, OSError):
            print("ERROR: unable to read input or exclusively create output file", file=sys.stderr)
        else:
            print("ERROR: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
