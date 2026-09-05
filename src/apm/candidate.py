# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
"""Fresh-clone and exact-tag orchestration. This module never creates a tag."""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .compiler_provenance import digest
from .history import git_text, require_history
from .lifecycle import ValidationError, source_identity
from .research import save, seal, verify

REMOTE = 'https://github.com/ds54e/analog-process-models.git'
SCHEMA = 'apm.fresh-candidate.v1'


def create_clone(destination, commit, *, remote=REMOTE):
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValidationError('FRESH_CLONE_DESTINATION_OCCUPIED')
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValidationError('EXACT_COMMIT_REQUIRED')
    if any(p.is_symlink() for p in destination.parents):
        raise ValidationError('FRESH_CLONE_SYMLINK_PARENT')
    started = datetime.now(timezone.utc).isoformat()
    subprocess.run(['git', 'clone', '--no-local', remote, str(destination)], check=True)
    subprocess.run(['git', 'checkout', '--detach', commit], cwd=destination, check=True)
    require_history(destination)
    observed = source_identity(destination)
    if observed['commit'] != commit or not observed['clean']:
        raise ValidationError('FRESH_CLONE_IDENTITY')
    if any((destination / p).exists() for p in ('.apm', '.venv')):
        raise ValidationError('GENERATED_STATE_BEFORE_ATTESTATION')
    git_text(destination, 'merge-base', '--is-ancestor', commit, 'origin/main')
    if (destination / '.git/objects/info/alternates').exists():
        raise ValidationError('SHARED_OBJECT_ALTERNATES')
    receipt = seal({'schema': SCHEMA, 'created_utc': started, 'commit': commit,
                    'tree': observed['tree'], 'root': str(destination), 'remote': remote,
                    'origin_main': git_text(destination, 'rev-parse', 'origin/main'),
                    'fresh_generated_state_absent': True, 'no_alternates': True,
                    'git_dir': git_text(destination, 'rev-parse', '--absolute-git-dir'),
                    'tags_at_clone': dict(line.split(' ', 1)[::-1] for line in git_text(
                        destination, 'for-each-ref', '--format=%(objectname) %(refname)', 'refs/tags').splitlines()),
                    'method': 'git clone --no-local; detached exact commit; observed before bootstrap',
                    'creator_sha256': digest(Path(__file__))})
    return save(destination / '.apm/qualification/clone.json', receipt)


def audit_clone(root, *, remote=REMOTE):
    try:
        require_history(root)
        path = root / '.apm/qualification/clone.json'
        receipt = verify(json.loads(path.read_text()), SCHEMA)
        source = source_identity(root)
        checks = {
            'commit_tree': source['commit'] == receipt['commit'] and source['tree'] == receipt['tree'],
            'clean_source': source['clean'],
            'remote': receipt['remote'] == remote == git_text(root, 'remote', 'get-url', 'origin'),
            'root': str(root.resolve()) == receipt['root'],
            'git_dir': receipt['git_dir'] == git_text(root, 'rev-parse', '--absolute-git-dir'),
            'observed_main': receipt['origin_main'] == git_text(root, 'rev-parse', 'origin/main'),
            'fresh': receipt['fresh_generated_state_absent'] is True,
            'independent_objects': receipt['no_alternates'] is True
                and not (root / '.git/objects/info/alternates').exists(),
            'creator': receipt['creator_sha256'] == digest(Path(__file__)),
        }
        git_text(root, 'merge-base', '--is-ancestor', receipt['commit'], receipt['origin_main'])
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                'receipt_sha256': digest(path), 'receipt': str(path)}
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        return {'status': 'FAIL', 'error': str(error)}


def exact_tag_freshness(root, tag, tag_object, campaign_started):
    """A clone made before the tag, or a reused campaign directory, is insufficient."""
    try:
        receipt = verify(json.loads((root / '.apm/qualification/clone.json').read_text()), SCHEMA)
        clone_time = datetime.fromisoformat(receipt['created_utc'])
        start = datetime.fromisoformat(campaign_started)
        tag_time = int(git_text(root, 'for-each-ref', '--format=%(taggerdate:unix)', 'refs/tags/' + tag))
        checks = {'tag_present_at_clone': receipt['tags_at_clone'].get('refs/tags/' + tag) == tag_object,
                  'created_after_tag': clone_time.timestamp() >= tag_time,
                  'campaign_after_clone': start >= clone_time}
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks}
    except (OSError, KeyError, ValueError, RuntimeError) as error:
        return {'status': 'FAIL', 'error': str(error)}


def exact_tag_identity(root, tag, approved_commit, approved_tree, expected_tag_object):
    """Require external exact approval/identity; only read an existing annotated tag."""
    try:
        require_history(root)
        if not all(re.fullmatch('[0-9a-f]{40}', x or '')
                   for x in (approved_commit, approved_tree, expected_tag_object)):
            raise ValidationError('EXACT_APPROVED_IDENTITIES_REQUIRED')
        actual = git_text(root, 'rev-parse', 'refs/tags/' + tag)
        checks = {
            'annotated_object': actual == expected_tag_object
                and git_text(root, 'cat-file', '-t', actual) == 'tag',
            'approved_commit': git_text(root, 'rev-parse', actual + '^{commit}') == approved_commit,
            'approved_tree': git_text(root, 'rev-parse', actual + '^{tree}') == approved_tree,
            'executed_source': git_text(root, 'rev-parse', 'HEAD') == approved_commit,
            'clean': source_identity(root)['clean'],
        }
        return {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks,
                'tag': tag, 'tag_object': actual, 'approved_commit': approved_commit,
                'approved_tree': approved_tree}
    except (OSError, ValueError, RuntimeError) as error:
        return {'status': 'FAIL', 'error': str(error)}
