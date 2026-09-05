# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from apm.candidate import audit_clone, create_clone, exact_tag_identity
from apm.compiler_provenance import digest
from apm.history import git_text
from apm.lifecycle import ValidationError, load_contract, package_identity
from apm.release import evaluate_checks, record_check, required_checks

ROOT = Path(__file__).resolve().parents[1]
SUBJECT = {'subject_commit': 'a' * 40, 'subject_tree': 'b' * 40, 'acceptance_sha256': 'c' * 64}


def evidence(tmp_path, phase='candidate'):
    raw = tmp_path / 'observed.json'
    raw.write_text('{"observed_count": 3}\n')
    records = [record_check(tmp_path, name, SUBJECT, {'observed_count_is_three': True}, [raw])
               for name in required_checks(phase)]
    return load_contract(ROOT), records, raw


def test_current_package_and_phase_agree():
    result = package_identity(ROOT)
    assert result['status'] == 'PASS', result
    plan = load_contract(ROOT)
    assert plan['phase'] in ('implementation', 'candidate')
    assert plan['create_tag_authorized'] is False
    assert plan['publish_release_authorized'] is False


def test_candidate_does_not_require_post_tag(tmp_path):
    contract, records, _ = evidence(tmp_path)
    result = evaluate_checks(contract, records, SUBJECT, 'candidate')
    assert result['status'] == 'PASS'
    assert len(result['gates']) == 10
    assert result['passed_checks'] == result['required_checks'] == 57
    assert evaluate_checks(contract, records, SUBJECT, 'exact-tag')['status'] == 'FAIL'


@pytest.mark.parametrize('fault', ['missing', 'empty', 'duplicate', 'unknown', 'missing_file',
                                  'hash', 'raw_hash', 'stale_commit', 'stale_tree', 'stale_plan',
                                  'empty_predicates', 'string_predicate', 'pass_string_only',
                                  'empty_artifacts', 'missing_artifact', 'duplicate_artifact',
                                  'FAIL', 'SKIPPED', 'NOT_RUN', 'UNKNOWN'])
def test_incomplete_stale_unverified_evidence_never_passes(tmp_path, fault):
    contract, records, raw = evidence(tmp_path)
    if fault == 'missing':
        records.pop()
    elif fault == 'empty':
        records.clear()
    elif fault == 'duplicate':
        records.append(copy.deepcopy(records[0]))
    elif fault == 'unknown':
        records.append({**records[0], 'id': 'unplanned'})
    elif fault == 'raw_hash':
        raw.write_text('changed')
    elif fault == 'missing_artifact':
        raw.unlink()
    else:
        path = Path(records[0]['path'])
        if fault == 'missing_file':
            path.unlink()
        elif fault == 'hash':
            path.write_text('{}')
        else:
            data = json.loads(path.read_text())
            if fault.startswith('stale_'):
                key = {'stale_commit': 'subject_commit', 'stale_tree': 'subject_tree',
                       'stale_plan': 'acceptance_sha256'}[fault]
                data[key] = 'changed'
            elif fault == 'empty_predicates':
                data['checks'] = {}
            elif fault == 'string_predicate':
                data['checks'] = {'false_claim': 'PASS'}
            elif fault == 'pass_string_only':
                data = {'status': 'PASS', 'id': data['id']}
            elif fault == 'empty_artifacts':
                data['artifacts'] = []
            elif fault == 'duplicate_artifact':
                data['artifacts'].append(copy.deepcopy(data['artifacts'][0]))
            else:
                data['status'] = fault
            path.write_text(json.dumps(data))
            records[0]['sha256'] = digest(path)
    assert evaluate_checks(contract, records, SUBJECT, 'candidate')['status'] == 'FAIL'


@pytest.mark.parametrize('fault', ['removed', 'optional', 'duplicate', 'empty_checks', 'wrong_phase'])
def test_required_manifest_cannot_be_weakened(tmp_path, fault):
    contract, records, _ = evidence(tmp_path)
    if fault == 'removed':
        contract['gate'].pop(0)
    elif fault == 'duplicate':
        contract['gate'].append(copy.deepcopy(contract['gate'][0]))
    elif fault == 'optional':
        contract['gate'][0]['required'] = False
    elif fault == 'wrong_phase':
        contract['gate'][0]['phase'] = 'exact-tag'
    else:
        contract['gate'][0]['checks'] = []
    assert evaluate_checks(contract, records, SUBJECT, 'candidate')['status'] == 'FAIL'


def test_next_release_data_does_not_require_historical_validator_chain(tmp_path):
    contract, records, _ = evidence(tmp_path)
    contract.update(release='99.0.0', candidate_version='99.0.0', ready_status='FIXTURE_READY')
    assert evaluate_checks(contract, records, SUBJECT, 'candidate')['status'] == 'PASS'


def git(root, *args):
    subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)


def repository(tmp_path):
    origin = tmp_path / 'origin'
    origin.mkdir()
    git(origin, 'init', '-b', 'main')
    git(origin, 'config', 'user.name', 'APM fixture')
    git(origin, 'config', 'user.email', 'fixture@example.invalid')
    (origin / 'data').write_text('original\n')
    (origin / '.gitignore').write_text('.apm/\n.venv/\n')
    git(origin, 'add', '.')
    git(origin, 'commit', '-m', 'synthetic source')
    return origin


def test_fresh_clone_and_exact_tag_use_only_synthetic_repository(tmp_path):
    origin = repository(tmp_path)
    commit, tree = (git_text(origin, 'rev-parse', x) for x in ('HEAD', 'HEAD^{tree}'))
    # No tag is created in the actual project; this fixture is entirely temporary.
    git(origin, 'tag', '-a', 'synthetic-release', '-m', 'synthetic approval')
    tag = git_text(origin, 'rev-parse', 'synthetic-release')
    clone = tmp_path / 'fresh'
    create_clone(clone, commit, remote=str(origin))
    assert audit_clone(clone, remote=str(origin))['status'] == 'PASS'
    assert audit_clone(clone)['status'] == 'FAIL'  # local clone is never authoritative project evidence
    assert exact_tag_identity(clone, 'synthetic-release', commit, tree, tag)['status'] == 'PASS'
    assert exact_tag_identity(clone, 'synthetic-release', commit, '0' * 40, tag)['status'] == 'FAIL'
    assert exact_tag_identity(clone, 'synthetic-release', '0' * 40, tree, tag)['status'] == 'FAIL'
    assert exact_tag_identity(clone, 'synthetic-release', commit, tree, '0' * 40)['status'] == 'FAIL'
    (clone / 'data').write_text('dirty')
    assert audit_clone(clone, remote=str(origin))['status'] == 'FAIL'
    assert exact_tag_identity(clone, 'synthetic-release', commit, tree, tag)['status'] == 'FAIL'


def test_lightweight_and_missing_tags_do_not_qualify(tmp_path):
    origin = repository(tmp_path)
    commit, tree = (git_text(origin, 'rev-parse', x) for x in ('HEAD', 'HEAD^{tree}'))
    git(origin, 'tag', 'synthetic-lightweight')
    assert exact_tag_identity(origin, 'synthetic-lightweight', commit, tree, commit)['status'] == 'FAIL'
    assert exact_tag_identity(origin, 'absent', commit, tree, commit)['status'] == 'FAIL'


def test_clone_refuses_occupied_or_symbolic_identity(tmp_path):
    with pytest.raises(ValidationError, match='OCCUPIED'):
        create_clone(tmp_path, 'a' * 40)
    with pytest.raises(ValidationError, match='EXACT_COMMIT'):
        create_clone(tmp_path / 'new', 'main')
    assert audit_clone(tmp_path)['status'] == 'FAIL'


@pytest.mark.parametrize('version', ['5.0.0', '5.0.0+main', '6.0.0+main', '0.0.0'])
def test_current_identity_rejects_obsolete_or_premature_version(monkeypatch, version):
    from apm import lifecycle
    monkeypatch.setattr(lifecycle, '__version__', version)
    assert package_identity(ROOT)['status'] == 'FAIL'


@pytest.mark.parametrize('partial', [False, True])
def test_complete_exact_tag_orchestration_in_temporary_next_release_fixture(tmp_path, monkeypatch, partial):
    from apm import campaign, release
    from apm.lifecycle import write_report
    origin = repository(tmp_path)
    (origin / 'validation').mkdir()
    contract = (ROOT / 'validation/acceptance.toml').read_text().replace('6.0.0', '99.0.0')
    contract = contract.replace('phase = "implementation"', 'phase = "candidate"').replace('V6_RELEASE_READY', 'FIXTURE_READY')
    (origin / 'validation/acceptance.toml').write_text(contract)
    git(origin, 'add', '.')
    git(origin, 'commit', '-m', 'synthetic next-release contract')
    commit, tree = (git_text(origin, 'rev-parse', x) for x in ('HEAD', 'HEAD^{tree}'))
    candidate = tmp_path / 'candidate'
    create_clone(candidate, commit, remote=str(origin))
    monkeypatch.setattr(release, 'package_identity', lambda r: {'status': 'PASS', 'version': '99.0.0'})
    monkeypatch.setattr(release, 'audit_clone', lambda r: audit_clone(r, remote=str(origin)))
    calls = []

    def fixture_campaign(root, output, subject):
        calls.append(root)
        raw = output / 'fixture-observation.json'
        raw.write_text('{"observed":true}')
        names = required_checks('candidate')
        if partial and len(calls) == 2:
            names = names[:-1]
        return [record_check(output, n, subject, {'fixture_measurement': True}, [raw]) for n in names]

    monkeypatch.setattr(campaign, 'execute_campaign', fixture_campaign)
    before = git_text(origin, 'for-each-ref', 'refs/tags')
    ready = release.qualify_release(root=candidate)
    assert ready['status'] == 'FIXTURE_READY' and ready['passed_checks'] == 57
    assert git_text(origin, 'for-each-ref', 'refs/tags') == before
    git(origin, 'tag', '-a', 'v99.0.0', '-m', 'temporary synthetic approval')
    tag = git_text(origin, 'rev-parse', 'v99.0.0')
    exact = tmp_path / 'exact'
    create_clone(exact, commit, remote=str(origin))
    approval = {'schema': 'apm.exact-tag-approval.v1', 'commit': commit, 'tree': tree, 'tag_object': tag,
                'candidate_report': ready['report_path'], 'candidate_report_sha256': digest(Path(ready['report_path']))}
    with pytest.raises(ValidationError, match='SEPARATE_EXACT_TAG_APPROVAL'):
        release.qualify_release(root=exact, phase='exact-tag')
    broken = {**approval, 'candidate_report_sha256': '0' * 64}
    with pytest.raises(ValidationError, match='APPROVED_CANDIDATE_EVIDENCE'):
        release.qualify_release(root=exact, phase='exact-tag', approval=broken)
    if partial:
        with pytest.raises(ValidationError, match='REQUIRED_CANDIDATE_CHECKS_FAILED'):
            release.qualify_release(root=exact, phase='exact-tag', approval=approval)
        result = json.loads((exact / '.apm/qualification/campaign/report.json').read_text())
        assert result['status'] == 'BLOCKED'
    else:
        result = release.qualify_release(root=exact, phase='exact-tag', approval=approval)
        assert result['status'] == 'EXACT_TAG_QUALIFIED'
        assert result['passed_checks'] == result['required_checks'] == 60
    assert calls == [candidate, exact]
    assert git_text(origin, 'rev-parse', 'v99.0.0') == tag
    write_report(tmp_path / 'orchestration-result.json', result)


def test_pre_tag_clone_cannot_be_relabelled_post_tag(tmp_path):
    from datetime import datetime, timezone

    from apm.candidate import exact_tag_freshness
    origin = repository(tmp_path)
    commit = git_text(origin, 'rev-parse', 'HEAD')
    clone = tmp_path / 'pre-tag'
    create_clone(clone, commit, remote=str(origin))
    git(origin, 'tag', '-a', 'synthetic-after-clone', '-m', 'fixture only')
    git(clone, 'fetch', '--tags')
    tag = git_text(origin, 'rev-parse', 'synthetic-after-clone')
    result = exact_tag_freshness(clone, 'synthetic-after-clone', tag, datetime.now(timezone.utc).isoformat())
    assert result['status'] == 'FAIL'
    assert result['checks']['tag_present_at_clone'] is False
