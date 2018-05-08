'''
Created on Mar 19, 2018

@author: qurban.ali
'''


import pymel.core as pc
import re
import cui
import os.path as osp
import qtify_maya_window as qtfy
import json
import glob
import imaya
import traceback


MEL_PROC_FILE = osp.join(
    osp.dirname(__file__), 'hikUpdateCurrentSourceFromName.mel')
pc.mel.source(MEL_PROC_FILE.replace('\\', '/'))


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


def getMappingRoot(mapping):
    for node, num in mapping.items():
        if num == 1:
            return node
    return ''


def getHikDefFromSKRoot(namespace, skRoot):
    try:
        node = pc.PyNode(namespace + skRoot)
        characterNode = node.Character.outputs(type=pc.nt.HIKCharacterNode)
        if characterNode:
            return characterNode[0].name()
    except (AttributeError, IndexError, pc.MayaNodeError):
        pc.warning ("No Character Found")
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

    except IndexError as ie:
        print str(ie)
        traceback.print_exc()
        pc.warning('Cannot find connection to definition from mapping')
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
    mapping = getHikDestinationSourceMapping()
    return mapping.get(definition, '')


def getHikDestinations(definition):
    dests = []
    mapping = getHikDestinationSourceMapping()
    for dest, source in mapping.items():
        if source == definition:
            dests.append(source)
    return dests


def mapMocapSkeleton(namespace, mocapSkeletonMappings):
    prepareHIK()
    root = getMappingRoot(mocapSkeletonMappings)
    setRange(namespace + root)
    defname = getHikDefFromSKRoot(namespace, root)
    if not defname:
        defname = createHikDefinition(name='MocapCharacter1')
    else:
        pc.mel.hikSetCurrentCharacter(defname)
        pc.mel.hikToggleLockDefinition()
    for node, num in mocapSkeletonMappings.items():
        try:
            pc.mel.setCharacterObject(namespace + node, defname, num, 0)
        except RuntimeError:
            pass
    pc.mel.hikToggleLockDefinition()
    return defname


def mapRigSkeleton(namespace, rigSkeletonMappings):
    prepareHIK()
    selection = pc.selected()
    root = getMappingRoot(rigSkeletonMappings)
    defname = getHikDefFromSKRoot(namespace, root)
    if not defname:
        defname = createHikDefinition(name='MocapCharacter1')
    else:
        pc.mel.hikSetCurrentCharacter(defname)
        pc.mel.hikToggleLockDefinition()
    for node, num in rigSkeletonMappings.items():
        try:
            pc.mel.setCharacterObject(
                    namespace + node, defname, num, 0)
        except RuntimeError as re:
            print (str(re), namespace + node, 'not found')
    pc.mel.hikToggleLockDefinition()
    pc.select(selection)
    return defname


def mapRigControls(namespace, defname, rigControlsMappings):
    prepareHIK()
    pc.mel.hikSelectDefinitionTab()  # select and update appropriate tab
    selection = pc.selected()

    if not pc.mel.hikHasCustomRig(defname):
        pc.mel.hikCreateCustomRig(defname)
    pc.mel.hikSelectCustomRigTab()

    for node, num in rigControlsMappings.items():
        try:
            pc.select(namespace + node)
            pc.mel.hikCustomRigAssignEffector(num)
        except RuntimeError:
            pass

    pc.select(selection)


def mapMocap(mappingName):
    return mapMocapSkeleton('', loadMapping(mappingName))


def mapRig(namespace, mappingName):
    mapping = loadMapping(mappingName, typ=MappingTypes.Skeleton)
    defname = mapRigSkeleton(namespace, mapping)
    mapping = loadMapping(mappingName, typ=MappingTypes.ControlRig)
    mapRigControls(namespace, defname, mapping)
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


def linkMocapHikToRigHik(mocapDefinition, rigDefinition):
    prepareHIK()
    pc.mel.hikSetCurrentCharacter(rigDefinition)
    pc.mel.hikUpdateCurrentSourceFromName(mocapDefinition)


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
    if select:
        pc.select(controls)
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
    pc.mel.hikCreateCharacter(hikDefinitionName)
    pc.mel.hikUpdateCharacterList()  # update the character list
    pc.mel.hikSelectDefinitionTab()  # select and update appropriate tab
    return hikDefinitionName


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
    if not rigPath:
        dialog = cui.SingleInputBox(
                parent=qtfy.getMayaWindow(), title='Rig Path',
                label='Path', browseButton=True, fileFilter='*.ma;*.mb')
        if dialog.exec_():
            rigPath = dialog.getValue().strip('"')
        else:
            return "-1"
    namespace = getNamespaceFromReferencePath(rigPath)
    if namespace == "-1":
        namespace = imaya.addRef(rigPath).namespace
    return namespace


def deleteMocap(mapName):
    mapping = loadMapping(mapName)
    root = getMappingRoot(mapping)
    print mapping, root
    pc.delete(root)


def cleanupHIK(mocapRoot):
        pc.mel.hikDeleteCustomRig(pc.mel.hikGetCurrentCharacter())
        pc.mel.hikDeleteDefinition()
        pc.mel.hikSelectDefinitionTab()
        pc.mel.hikDeleteDefinition()
        pc.delete(mocapRoot)


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
        if refFile.namespace == namespace:
            return ref.referenceFile().path
    return ''


def prepareHIK(startFrame=0):
    pc.mel.HIKCharacterControlsTool()
    pc.playbackOptions(minTime=startFrame)
    pc.currentTime(startFrame)


def setRange(mocapRoot):
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
        pc.importReference(refFile)
        if cleanup:
            pc.namespace(namespace, mnr=True)
            pc.delete(pc.ls(type='unknown'))


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


def applyMocapToRig(mocapPath=None):
    pc.mel.HIKCharacterControlsTool()
    startFrame = 0
    pc.playbackOptions(minTime=startFrame)
    pc.currentTime(startFrame)
    try:
        control = pc.selected()[0]
    except IndexError:
        pc.warning('No selection found in the scene')
        return
    rigNamespace = control.namespace()
    
    # bring the mocap in
    if not mocapPath:
        dialog = cui.SingleInputBox(parent=qtfy.getMayaWindow(),
                                    title='Mocap Skeleton Path', label='Path',
                                    browseButton=True)
        if dialog.exec_():
            mocapPath = dialog.getValue().strip('"')
        else: return
    if not osp.exists(mocapPath):
        pc.warning('Mocap Path does not exist')
        return
    
    mocapNamespace = osp.splitext(osp.basename(mocapPath))[0]
    pc.importFile(mocapPath, namespace=mocapNamespace)
    mocapNamespace = ''
    
    # define HIK Skeleton
    hikDefinitionName = createHikDefinition()
    mapMocapSkeleton(mocapNamespace, hikDefinitionName)
    pc.mel.hikToggleLockDefinition()
    
    rigHikDefinitionName = createHikDefinition()
    mapRigSkeleton(rigNamespace, rigHikDefinitionName)
    pc.mel.hikToggleLockDefinition()
    
    pc.mel.hikCreateCustomRig(rigHikDefinitionName)
    mapRigControls(rigNamespace)
    pc.mel.hikUpdateCurrentSourceFromName(hikDefinitionName)
    pc.select(getRigControls(rigNamespace))

#     TODO: enable following code for maya 2018 and change the code in
#     launch.mel
#     animCurves = pc.listConnections("Hip", d=0, s=1, scn=0)
#     frames = pc.keyframe(animCurves[0], q=1)
#     endFrame = frames[-1]
#     pc.playbackOptions(maxTime=endFrame)
#
#     pc.mel.eval('bakeResults -simulation true -t "%s:%s" -sampleBy 1 -disableImplicitControl true -preserveOutsideKeys true -sparseAnimCurveBake false -removeBakedAttributeFromLayer false -removeBakedAnimFromLayer false -bakeOnOverrideLayer false -minimizeRotation true -controlPoints false -shape true `ls -sl`;'%(startFrame, endFrame))
#
#     pc.mel.hikDeleteCustomRig(pc.mel.hikGetCurrentCharacter())
#     pc.mel.hikDeleteDefinition()
#     pc.mel.hikSelectDefinitionTab()
#     pc.mel.hikDeleteDefinition()
#     pc.delete("Hip")
