# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""One current candidate/exact-tag coordinator with concrete, hash-bound checks."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .candidate import audit_clone, exact_tag_freshness, exact_tag_identity
from .compiler_provenance import digest
from .lifecycle import (
    EXACT_CHECKS,
    GROUPS,
    ValidationError,
    load_contract,
    package_identity,
    source_identity,
    write_report,
)
from .paths import repository_root

CHECK_SCHEMA = 'apm.acceptance-check.v1'


def required_checks(phase):
    if phase not in ('candidate', 'exact-tag'):
        raise ValidationError('INVALID_QUALIFICATION_PHASE')
    return [c for checks in GROUPS.values() for c in checks] + (EXACT_CHECKS if phase == 'exact-tag' else [])


def record_check(output, identifier, subject, checks, artifacts, *, observations=None):
    """Persist measured predicates and their raw inputs; a supplied PASS is insufficient."""
    refs = [{'path': str(p), 'sha256': digest(Path(p))} for p in artifacts]
    passed = bool(checks) and all(value is True for value in checks.values()) and bool(refs)
    report = {'schema': CHECK_SCHEMA, 'id': identifier, **subject,
              'status': 'PASS' if passed else 'FAIL', 'checks': checks, 'artifacts': refs,
              'observations': observations or {}}
    path = output / 'checks' / (identifier + '.json')
    write_report(path, report)
    return {'id': identifier, 'path': str(path), 'sha256': digest(path)}


def evaluate_checks(contract, results, subject, phase):
    expected = required_checks(phase)
    indexed = {r.get('id'): r for r in results}
    complete = len(results) == len(indexed) == len(expected) and set(indexed) == set(expected)
    evaluated = []
    for identifier in expected:
        record = indexed.get(identifier, {})
        reasons = []
        try:
            path = Path(record['path'])
            if digest(path) != record['sha256']:
                reasons.append('CHECK_HASH_DRIFT')
            data = json.loads(path.read_text())
            if not complete:
                reasons.append('REQUIRED_RESULT_INVENTORY_DRIFT')
            if data.get('schema') != CHECK_SCHEMA or data.get('id') != identifier:
                reasons.append('INVALID_TYPED_CHECK')
            if any(data.get(k) != v for k, v in subject.items()):
                reasons.append('STALE_SUBJECT_OR_PLAN')
            checks = data.get('checks')
            if (data.get('status') != 'PASS' or not isinstance(checks, dict) or not checks
                    or not all(v is True for v in checks.values())):
                reasons.append('UNVERIFIED_OR_FAILED_PREDICATES')
            artifacts = data.get('artifacts')
            if not isinstance(artifacts, list) or not artifacts:
                reasons.append('MISSING_RAW_EVIDENCE')
            else:
                names = [r['path'] for r in artifacts]
                if len(names) != len(set(names)):
                    reasons.append('DUPLICATE_ARTIFACT')
                for r in artifacts:
                    if digest(Path(r['path'])) != r['sha256']:
                        reasons.append('RAW_ARTIFACT_DRIFT')
        except (OSError, ValueError, KeyError, TypeError) as error:
            reasons.append('EVIDENCE_UNAVAILABLE: ' + str(error))
        evaluated.append({**record, 'id': identifier, 'status': 'FAIL' if reasons else 'PASS',
                          'reasons': reasons})
    groups = {**GROUPS, **({'release.exact_tag_requalification': EXACT_CHECKS} if phase == 'exact-tag' else {})}
    indexed_evaluated = {r['id']: r for r in evaluated}
    gates = [{'id': name, 'status': 'PASS' if all(indexed_evaluated[c]['status'] == 'PASS' for c in checks)
              else 'FAIL', 'checks': checks} for name, checks in groups.items()]
    # The active manifest is also checked independently by load_contract. This
    # check prevents a caller from silently supplying an altered in-memory plan.
    definitions = {g['id']: g for g in contract.get('gate', [])}
    manifest_valid = len(definitions) == len(contract.get('gate', [])) == len(GROUPS) + 1
    for name, checks in {**GROUPS, 'release.exact_tag_requalification': EXACT_CHECKS}.items():
        g = definitions.get(name, {})
        manifest_valid &= g.get('checks') == checks and g.get('required') is True
        manifest_valid &= g.get('phase') == ('exact-tag' if name.startswith('release.exact') else 'candidate')
    passed = complete and manifest_valid and all(g['status'] == 'PASS' for g in gates)
    return {'status': 'PASS' if passed else 'FAIL', 'gates': gates,
            'checks': evaluated, 'manifest_valid': manifest_valid,
            'required_checks': len(expected), 'passed_checks': sum(r['status'] == 'PASS' for r in evaluated)}


def qualify_release(output=None, *, phase='candidate', root=None, approval=None):
    started = datetime.now(timezone.utc).isoformat()
    root = (root or repository_root()).resolve()
    contract = load_contract(root)
    required_checks(phase)
    identity = package_identity(root)
    source = source_identity(root)
    if (contract['phase'] != 'candidate' or identity['status'] != 'PASS'
            or identity['version'] != contract['candidate_version']
            or source.get('status') != 'PASS' or not source.get('clean')):
        raise ValidationError('EXACT_CLEAN_CANDIDATE_PHASE_AND_VERSION_REQUIRED')
    if phase == 'exact-tag' and approval is None:
        raise ValidationError('SEPARATE_EXACT_TAG_APPROVAL_REQUIRED')
    if phase == 'exact-tag':
        if approval.get('schema') != 'apm.exact-tag-approval.v1':
            raise ValidationError('INVALID_EXTERNAL_APPROVAL_RECORD')
        approved = Path(approval.get('candidate_report', 'missing'))
        try:
            previous = json.loads(approved.read_text())
            if (digest(approved) != approval['candidate_report_sha256']
                    or previous['status'] != contract['ready_status']
                    or previous['subject_commit'] != approval['commit']
                    or previous['subject_tree'] != approval['tree']
                    or evaluate_checks(contract, previous['checks'],
                        {k: previous[k] for k in ('subject_commit', 'subject_tree', 'acceptance_sha256')}, 'candidate')['status'] != 'PASS'):
                raise ValidationError('APPROVED_CANDIDATE_EVIDENCE_REQUIRED')
        except (OSError, KeyError, ValueError) as error:
            raise ValidationError('APPROVED_CANDIDATE_EVIDENCE_REQUIRED') from error
    output = (output or root / '.apm/qualification/campaign').resolve()
    if not output.is_relative_to(root / '.apm'):
        raise ValidationError('QUALIFICATION_OUTPUT_MUST_BE_IGNORED_LOCAL_STATE')
    output.mkdir(parents=True, exist_ok=False)
    subject = {'subject_commit': source['commit'], 'subject_tree': source['tree'],
               'acceptance_sha256': digest(root / 'validation/acceptance.toml')}
    from .campaign import execute_campaign
    results = execute_campaign(root, output, subject)
    if phase == 'exact-tag':
        rerun_passed = evaluate_checks(contract, results, subject, 'candidate')['status'] == 'PASS'
        tag = exact_tag_identity(root, 'v' + contract['release'], approval.get('commit'),
                                 approval.get('tree'), approval.get('tag_object'))
        freshness = exact_tag_freshness(root, 'v' + contract['release'], approval.get('tag_object'), started)
        path = output / 'exact-tag.json'
        write_report(path, {'tag': tag, 'clone': audit_clone(root), 'freshness': freshness,
                           'external_approval': approval, 'campaign_started': started})
        for identifier in EXACT_CHECKS:
            predicates = {'existing_approved_tag': tag['status'] == 'PASS',
                          'fresh_clone': audit_clone(root)['status'] == 'PASS',
                          'post_tag_fresh_execution': freshness['status'] == 'PASS',
                          'full_candidate_rerun': rerun_passed}
            results.append(record_check(output, identifier, subject, predicates, [path]))
    evaluated = evaluate_checks(contract, results, subject, phase)
    status = (contract['ready_status'] if phase == 'candidate' else 'EXACT_TAG_QUALIFIED')
    report = {'schema': 'apm.release-qualification.v1', **subject,
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'status': status if evaluated['status'] == 'PASS' else 'BLOCKED',
              'phase': phase, 'version': identity['version'], **evaluated,
              'create_tag_authorized': False, 'publish_release_authorized': False,
              'output_directory': str(output)}
    report['status'] = status if evaluated['status'] == 'PASS' else 'BLOCKED'
    write_report(output / 'report.json', report)
    if report['status'] == 'BLOCKED':
        raise ValidationError(f'REQUIRED_CANDIDATE_CHECKS_FAILED: {output / "report.json"}')
    return {**report, 'report_path': str(output / 'report.json')}
