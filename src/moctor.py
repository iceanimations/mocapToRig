'''
Created on Mar 19, 2018

@author: qurban.ali talha.ahmed

A library of convenience functions used for transferring iPi motion capture
data in FBX format to Maya Rigs. This code uses Maya's HumanIK technology for
motion retargetting. The script has been tested to work on Maya 2016.

Currently only advanced skeleton rigs are only
supported.

'''


import pymel.core as pc
import re
import cui
import os.path as osp
import qtify_maya_window as qtfy
import json
import glob
import imaya


MEL_PROC_FILE = osp.join(
    osp.dirname(__file__), 'hikUpdateCurrentSourceFromName.mel')
pc.mel.source(MEL_PROC_FILE.replace('\\', '/'))


pc.loadPlugin('fbxmaya')
pc.loadPlugin('mayaHIK')


##################################
#  Storing and Loading Mappings  #
##################################


MAPPINGS_DIR = osp.join(osp.dirname(osp.dirname(__file__)), 'mappings')


class MappingTypes:
    sk = Skeleton = 'sk'
    cr = ControlRig = 'cr'


def getMappingNames(typ=MappingTypes.sk):
    return [osp.basename(_file).split('.')[0]
            for _file in glob.glob(osp.join(MAPPINGS_DIR, '*.%s.json' % typ))]


def dumpMapping(data, name, typ=MappingTypes.sk):
    with open(osp.join(MAPPINGS_DIR, '%s.%s.json' % (name, typ)), 'w+') as _fl:
        return json.dump(data, _fl, indent=2)


def loadMapping(name, typ=MappingTypes.sk):
    with open(osp.join(MAPPINGS_DIR, '%s.%s.json' % (name, typ))) as _file:
        return json.load(_file)


#######################
#  Applying mappings  #
#######################

def mappingMatches(mapping, namespace=''):
    found = 0
    for node, num in mapping.items():
        if pc.objExists(namespace+node):
            found += 1
    return found, len(mapping)


def checkMappingCount(mappingName, namespace='', typ=MappingTypes.sk):
    mapping = loadMapping(mappingName, typ=typ)
    return mappingMatches(mapping, namespace)


def checkMappingRoot(mappingName, namespace='', typ=MappingTypes.sk):
    mapping = loadMapping(mappingName, typ=typ)
    root = getMappingRoot(mapping)
    if pc.objExists(namespace + root):
        return namespace+root
    return ''


def getMappingElement(mapping, index):
    for node, num in mapping.items():
        if num == index:
            return node
    return ''


def getMappingRoot(mapping):
    return getMappingElement(mapping, 1)


def getHikDefFromSKRoot(namespace, skRoot):
    try:
        node = pc.PyNode(namespace + skRoot)
        characterNode = node.Character.outputs(type=pc.nt.HIKCharacterNode)
        if characterNode:
            return characterNode[0].name()
    except (AttributeError, IndexError, pc.MayaNodeError):
        pass
    return ''


def getHikDefFromCRRoot(namespace, crRoot):
    crRoot = pc.PyNode(namespace + crRoot)

    try:
        mappingNode = crRoot.message.outputs(
                type='CustomRigDefaultMappingNode')[0]
        skeletonRoot = mappingNode.destinationSkeleton.inputs(
                type='CustomRigDefaultMappingNode')[0]
        characterNode = skeletonRoot.Character.outputs(
                type='HIKCharacterNode')

        if characterNode:
            return characterNode[0].name()
        else:
            ''

    except IndexError:
        return ''


def getHikDestinationSourceMapping():
    destSourceMapping = {}
    for node in pc.ls(type='HIKRetargeterNode'):
        source = ''
        try:
            destination = node.InputCharacterDefinitionDst.inputs()[0]
        except IndexError:
            continue
        try:
            source = node.InputCharacterDefinitionSrc.inputs()[0]
        except IndexError:
            pass
        destSourceMapping[str(destination)] = str(source)
    return destSourceMapping


def getHikSource(definition):
    return pc.mel.hikGetCharacterInputString(definition)


def getHikDestinations(definition):
    dests = []
    mapping = getHikDestinationSourceMapping()
    for dest, source in mapping.items():
        if source == definition:
            dests.append(source)
    return dests


def lockDefinition(defname):
    pc.mel.hikReadStancePoseTRSOffsets(defname)
    pc.setAttr(defname + '.InputCharacterizationLock', True)


def unlockDefinition(defname):
    pc.setAttr(defname + '.InputCharacterizationLock', False)


def mapMocapSkeleton(namespace, mocapSkeletonMappings):
    prepareHIK()
    selection = pc.selected()
    root = getMappingRoot(mocapSkeletonMappings)
    defname = getHikDefFromSKRoot(namespace, root)

    if not defname:
        defname = createHikDefinition(name='MocapCharacter1')
    else:
        pc.mel.hikSetCurrentCharacter(defname)
        unlockDefinition(defname)

    for name, num in mocapSkeletonMappings.items():
        node = namespace + name
        try:
            pc.mel.setCharacterObject(node, defname, num, 0)
        except (pc.MayaNodeError, RuntimeError) as re:
            pc.warning(str(re), namespace + node, 'not found')

    lockDefinition(defname)
    pc.select(selection)
    return defname


def mocapZeroOut(namespace, mocapSkeletonMappings):
    for name, num in mocapSkeletonMappings.items():
        node = namespace + name
        if pc.objExists(node):
            pc.setAttr(node + '.rx', 0)
            pc.setAttr(node + '.ry', 0)
            pc.setAttr(node + '.rz', 0)


def mocapSetKeyframe(namespace, mocapSkeletenmappings):
    for name, num in mocapSkeletenmappings.items():
        node = namespace + name
        if pc.objExists(node):
            pc.setKeyframe(node + '.rx')
            pc.setKeyframe(node + '.ry')
            pc.setKeyframe(node + '.rz')


def mapRigSkeleton(namespace, rigSkeletonMappings):
    prepareHIK()
    selection = pc.selected()
    root = getMappingRoot(rigSkeletonMappings)
    defname = getHikDefFromSKRoot(namespace, root)
    if not defname:
        defname = createHikDefinition(name='MocapCharacter1')
    else:
        pc.mel.hikSetCurrentCharacter(defname)
        unlockDefinition(defname)
    for name, num in rigSkeletonMappings.items():
        node = namespace + name
        try:
            pc.mel.setCharacterObject(
                    node, defname, num, 0)
            pc.setAttr(node + '.drawStyle', 2)
        except (pc.MayaNodeError, RuntimeError) as re:
            pc.warning(str(re), namespace + node, 'not found')
    lockDefinition(defname)
    pc.select(selection)
    return defname


def hideSkeleton(namespace, mapping):
    for node in mapping:
        try:
            pc.PyNode(namespace + node).drawStyle.set(2)
        except:
            pass


def mapRigControls(namespace, defname, rigControlsMappings):
    prepareHIK()
    selection = pc.selected()

    retargeter = pc.mel.RetargeterGetName(defname)

    if not pc.mel.RetargeterExists(retargeter):
        pc.mel.RetargeterCreate(defname)

    for name, num in rigControlsMappings.items():
        node = namespace + name

        try:
            retargeter = pc.mel.RetargeterGetName(defname)
            body = pc.mel.hikCustomRigElementNameFromId(defname, num)

            if not isLocked(node, 'rotate'):
                pc.mel.RetargeterAddMapping(retargeter, body, "R", node, num)
            if 'FK' not in node and not isLocked(node, 'translate'):
                pc.mel.RetargeterAddMapping(retargeter, body, "T", node, num)

        except (RuntimeError, pc.MayaNodeError, AttributeError,
                pc.MayaAttributeError) as error:
            pc.warning("problem in mapping to %s: %s)" % (
                       namespace+node, str(error)))

    pc.select(selection)


def mapMocap(mappingName):
    mapping = loadMapping(mappingName)
    defname = mapMocapSkeleton('', mapping)
    return defname


def mapRig(namespace, mappingName):
    sk_mapping = loadMapping(mappingName, typ=MappingTypes.Skeleton)
    defname = mapRigSkeleton(namespace, sk_mapping)
    cr_mapping = loadMapping(mappingName, typ=MappingTypes.ControlRig)
    mapRigControls(namespace, defname, cr_mapping)
    return defname


def getMocapHikDefinition(mappingName):
    mapping = loadMapping(mappingName)
    root = getMappingRoot(mapping)
    return getHikDefFromSKRoot('', root)


def getRigHikDefinition(namespace, mappingName):
    mapping = loadMapping(mappingName, typ=MappingTypes.sk)
    root = getMappingRoot(mapping)
    return getHikDefFromSKRoot(namespace, root)


#######################
#  Utility functions  #
#######################


def makeArmHorizontal(sh, el, ctrl):
    p1 = pc.dt.Point(pc.xform(sh, q=True, ws=True, t=True))
    p2 = pc.dt.Point(pc.xform(el, q=True, ws=True, t=True))
    v = (p2-p1).normal()

    x = v.dot(pc.dt.Vector.xAxis)
    z = v.dot(pc.dt.Vector.zAxis)

    proj = pc.dt.Vector(x, 0, z).normal()
    quat = v.rotateTo(proj)
    rot = pc.dt.degrees(quat.asEulerRotation())

    pc.rotate(ctrl, pc.dt.degrees(quat.asEulerRotation()), ws=True, r=True)

    return rot


def makeIKFollow(fk, ik, rot):
    pos = pc.xform(fk, q=True, ws=True, t=True)
    # rot = pc.xform(fk, q=True, ws=True, ro=True)
    pc.xform(ik, ws=True, t=pos)
    pc.rotate(ik, rot, ws=True, r=True)


def fixRigTPose(namespace, mappingName):
    skeletonMapping = loadMapping(mappingName, MappingTypes.sk)
    controlsMapping = loadMapping(mappingName, MappingTypes.cr)

    ls_ctrl = getMappingElement(controlsMapping, 9)
    ls_jnt = getMappingElement(skeletonMapping, 9)
    le_jnt = getMappingElement(skeletonMapping, 10)
    l_rot = makeArmHorizontal(
            namespace+ls_jnt, namespace+le_jnt, namespace+ls_ctrl)

    larm_ik = getMappingElement(controlsMapping, 11)
    lwrist_fk = getMappingElement(skeletonMapping, 11)
    makeIKFollow(namespace+lwrist_fk, namespace+larm_ik, l_rot)

    rs_ctrl = getMappingElement(controlsMapping, 12)
    rs_jnt = getMappingElement(skeletonMapping, 12)
    re_jnt = getMappingElement(skeletonMapping, 13)
    r_rot = makeArmHorizontal(
            namespace+rs_jnt, namespace+re_jnt, namespace+rs_ctrl)

    rarm_ik = getMappingElement(controlsMapping, 14)
    rwrist_fk = getMappingElement(skeletonMapping, 14)
    makeIKFollow(namespace+rwrist_fk, namespace+rarm_ik, r_rot)


def fixMocapTPose(namespace, mappingName):
    skeletonMapping = loadMapping(mappingName, MappingTypes.sk)

    ls_ctrl = getMappingElement(skeletonMapping, 18)
    ls_jnt = getMappingElement(skeletonMapping, 9)
    le_jnt = getMappingElement(skeletonMapping, 10)
    makeArmHorizontal(
            namespace+ls_jnt, namespace+le_jnt, namespace+ls_ctrl)

    rs_ctrl = getMappingElement(skeletonMapping, 19)
    rs_jnt = getMappingElement(skeletonMapping, 12)
    re_jnt = getMappingElement(skeletonMapping, 13)
    makeArmHorizontal(
            namespace+rs_jnt, namespace+re_jnt, namespace+rs_ctrl)


def linkMocapHikToRigHik(mocapDefinition, rigDefinition):
    prepareHIK()
    pc.mel.hikSetCurrentCharacter(rigDefinition)
    pc.mel.hikSetCharacterInput(rigDefinition, mocapDefinition)


def bakeRig(namespace, mocapMappingName, rigMappingName):
    mocapMapping = loadMapping(mocapMappingName, typ=MappingTypes.sk)
    rigMapping = loadMapping(rigMappingName, typ=MappingTypes.cr)

    mocapRoot = getMappingRoot(mocapMapping)
    startFrame, endFrame = getAnimRange(mocapRoot)

    selection = pc.selected()
    getRigControls(namespace, rigMapping, True)
    pc.mel.eval((
            'bakeResults -simulation true -t "%s:%s" -sampleBy 1'
            '-disableImplicitControl true -preserveOutsideKeys true'
            '-sparseAnimCurveBake false'
            '-removeBakedAttributeFromLayer false'
            '-removeBakedAnimFromLayer false -bakeOnOverrideLayer false'
            '-minimizeRotation true -controlPoints false -shape true `ls'
            '-sl`;') % (startFrame, endFrame))
    pc.select(selection)


def getRigControls(namespace, rigControlsMappings, select=False):
    controls = [namespace + x for x in rigControlsMappings.keys()]
    pc.select(cl=True)
    if select:
        for ctrl in controls:
            if pc.objExists(ctrl):
                pc.select(ctrl, add=True)
            else:
                pc.warning('Object %s not found' % ctrl)
    return controls


def getUniqueName(name):
    cnt = 1
    while pc.objExists(name):
        match = re.search('\d+', name)
        if match:
            name = name.replace(match.group(), str(cnt))
        else:
            name += str(cnt)
        cnt += 1
    return name


def createHikDefinition(name='MocapCharacter1'):
    hikDefinitionName = getUniqueName(name)
    defname = pc.mel.hikCreateCharacter(hikDefinitionName)
    return defname


def importMocap(mocapPath, namespace=None):
    if not mocapPath:
        dialog = cui.SingleInputBox(
            parent=qtfy.getMayaWindow(),
            title='Mocap Skeleton Path',
            label='Path',
            browseButton=True)
        if dialog.exec_():
            mocapPath = dialog.getValue().strip('"')
        else:
            return
    if not osp.exists(mocapPath):
        pc.warning('Mocap Path does not exist')
        return

    if namespace is None:
        namespace = osp.splitext(osp.basename(mocapPath))[0]
    pc.importFile(mocapPath)
    return ''


def importRig(rigPath):
    namespace = '-1'
    if not rigPath:
        dialog = cui.SingleInputBox(
                parent=qtfy.getMayaWindow(), title='Rig Path',
                label='Path', browseButton=True, fileFilter='*.ma;*.mb')
        if dialog.exec_():
            rigPath = dialog.getValue().strip('"')
        else:
            return namespace
    refFile = getRefFileFromPath(rigPath)
    if not refFile:
        namespace = imaya.addRef(rigPath).namespace
    else:
        namespace = refFile.namespace
        refFile.load()

    return namespace


def deleteMocap(mapName):
    mapping = loadMapping(mapName)
    root = getMappingRoot(mapping)
    pc.delete(root)


def cleanupMocapHIK(definition):
    retargeter = pc.mel.RetargeterGetName(definition)
    if pc.objExists(retargeter):
        pc.mel.RetargeterDelete(retargeter)
    pc.delete(definition)


def cleanupRigHIK(definition):
    retargeter = pc.mel.RetargeterGetName(definition)
    if pc.objExists(retargeter):
        pc.mel.RetargeterDelete(retargeter)
    pc.delete(definition)


def cleanupHIK(mocapRoot):
    cleanupMocapHIK()
    cleanupRigHIK()


def getNamespaceFromSelection():
    # resolve rig namespace
    try:
        control = pc.selected()[0]
    except IndexError:
        pc.warning('No selection found in the scene')
        return "-1"
    rigNamespace = control.namespace()
    return rigNamespace


def getRefFileFromPath(path):
    rigPath = osp.normcase(osp.normpath(path))
    for ref in pc.ls(type='reference'):
        refFile = ref.referenceFile()
        if not refFile:
            continue
        refPath = osp.normpath(osp.normcase(refFile.path))
        if rigPath == refPath:
            return refFile


def getNamespaceFromReferencePath(rigPath):
    refFile = getRefFileFromPath(rigPath)
    if refFile:
        return refFile.namespace
    return '-1'


def getReferencePathFromNamespace(namespace):
    namespace = namespace.strip(':')
    for ref in pc.ls(type='reference'):
        refFile = ref.referenceFile()
        if not refFile:
            continue
        if refFile.namespace == namespace:
            return ref.referenceFile().path
    return ''


def prepareHIK(startFrame=0):
    pc.currentTime(startFrame)


def setRange(arg):
    if isinstance(arg, dict):
        mocapRoot = getMappingRoot(arg)
    else:
        mocapRoot = arg
    startFrame, endFrame = getAnimRange(mocapRoot)
    pc.playbackOptions(minTime=startFrame, maxTime=endFrame)


def getAnimRange(mocapRoot):
    animCurves = pc.listConnections(
            mocapRoot, d=0, s=1, scn=0, type='animCurve')
    if not animCurves:
        return (pc.playbackOptions(q=True, minTime=True),
                pc.playbackOptions(q=True, maxTime=True))
    frames = pc.keyframe(animCurves[0], q=1)
    startFrame = frames[0]
    endFrame = frames[-1]
    return startFrame, endFrame


def importRigFromReference(rigPath, cleanup=True):
    refFile = getRefFileFromPath(rigPath)
    if refFile:
        namespace = refFile.namespace
        refFile.importContents()
        if cleanup:
            pc.namespace(removeNamespace=namespace, mnr=True)
            pc.delete(pc.ls(type='unknown'))


def isLocked(node, attr):
    if not attr.startswith('.'):
        attr = '.' + attr
    for add in ('', 'X', 'Y', 'Z'):
        if pc.getAttr(node + attr + add, l=True):
            return True
    return False


###############################
#  Main Application Function  #
###############################


def apply(
        mocapPath=None, rigNamespace=None,
        mocapMapping='iPi', rigMapping='AdvancedSkeleton', rigPath=None):
    '''
    ###########################################################################
    #            Procedure for mapping mocap data to a custom Rig             #
    ###########################################################################

    move to frame 0
    for mocap skeleton
        Define skeleton
        map joins
        save file as ma
    move to frame 0
    for character
        Define skeleton
        map joins
        lock mapping
        create custom rig node
        map controls
    move to frame 0
    for applying mocap to character
        import saved mocap skeleton in character file
        select mocap skeleton as source
        select character as Character
    '''
    mocapSkeletonMappings = loadMapping(mocapMapping, MappingTypes.sk)
    rigSkeletonMappings = loadMapping(rigMapping, MappingTypes.sk)
    rigControlsMappings = loadMapping(rigMapping, MappingTypes.cr)

    startFrame = 0
    prepareHIK(startFrame)

    # resolve rig namespace or import
    if rigPath:
        rigNamespace = importRig(rigPath)
    if rigNamespace is None or rigNamespace == '-1':
        rigNamespace = getNamespaceFromSelection()
    if not rigNamespace.endswith(':'):
        rigNamespace += ':'

    mocapNamespace = importMocap(mocapPath)
    if mocapNamespace and not mocapNamespace.endswith(':'):
        mocapNamespace += ':'

    # check if mocap is successfully imported
    mocapRoot = mocapNamespace + getMappingRoot(mocapSkeletonMappings)
    if not pc.objExists(mocapRoot):
        pc.error("Could not find mocap Root node")

    setRange(mocapRoot)
    # define HIK Skeleton
    mocapDefinition = mapMocapSkeleton(mocapNamespace, mocapSkeletonMappings)

    # define HIK skeleton for rig
    rigDefinition = mapRigSkeleton(rigNamespace, rigSkeletonMappings)

    # define HIK custom_rig for rig
    mapRigControls(rigNamespace, rigDefinition, rigControlsMappings)

    # set mocap as source for this rig
    linkMocapHikToRigHik(mocapDefinition, rigDefinition)

    # select the controls
    pc.select(getRigControls(rigNamespace), rigControlsMappings)

    setRange(mocapRoot)

    # To stop maya 2016 from hanging on bake call this in MEL instead
    if pc.about(v=True) >= 2018:
        # TODO: enable following code for maya 2018 and change the code in
        # launch.mel

        bakeRig()

        cleanupHIK(mocapRoot)

