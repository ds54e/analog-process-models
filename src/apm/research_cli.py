# SPDX-FileCopyrightText: 2026 APM contributors
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from .paths import repository_root
from .research import describe, load_profile, sample, save
from .research_mapping import ReferenceMapper
from .research_spice import execute
from .toolchain import resolve_toolchain


def read_request(path: Path) -> dict:
    value=json.loads(path.read_text())
    value['circuit']=str((path.parent/value['circuit']).resolve())
    return value


def research_command(args) -> dict:
    root=repository_root()
    if args.research_command=='describe':
        return describe(root)
    tool=resolve_toolchain(root)
    if args.research_command=='sample':
        if args.output.exists() or args.output.is_symlink():
            from .research_numerics import ResearchError
            raise ResearchError('REALIZATION_OUTPUT_OCCUPIED: choose a new path; preserve saved draws')
        profile=load_profile(args.profile,allow_artificial=args.allow_artificial,root=root)
        request=read_request(args.request)
        mapper=ReferenceMapper(root,tool.ngspice,args.state.resolve(),profile)
        result=sample(profile,request,args.seed,args.index,mapper)
        save(args.output,result)
        return {'status':result['status'],'realization_id':result['content_id'],'path':str(args.output)}
    if args.research_command=='run':
        request=read_request(args.request)
        realization=json.loads(args.realization.read_text())
        result=execute(root,tool.ngspice,args.output.resolve(),request,realization,
                       temperature_c=args.temperature_c)
        return {'status':result['status'],'run_id':result['run_id'],'directory':result['directory'],
                'errors':result['errors'],'source_tier':realization['profile_tier']}
    from .research_qualification import qualify
    return qualify(root,tool.ngspice,args.output.resolve(),args.suite)
