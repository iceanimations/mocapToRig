#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import pymel.core as pc
from collections import OrderedDict
import mocapToRig

defnode = pc.PyNode('MocapCharacter1')
map_hik = OrderedDict([(pc.mel.GetHIKNodeName(x), x) for x in range(212)])
map_sk = OrderedDict()

for name, num in map_hik.items():
    jnt = defnode.attr(name).inputs(type='joint')
    if jnt:
        map_sk[jnt[0].name().split(':')[-1]] = num

print map_sk 

moctor_base = op.dirname(mocapToRig.__file__)
sk_path = op.join(moctor_base, 'mappings', 'default.sk.json')
with open(sk_path, 'w') as _file:
    json.dump(map_sk, _file, indent=2)
