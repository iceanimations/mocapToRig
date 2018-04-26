'''
Created on Mar 19, 2018

@author: qurban.ali
'''
import pymel.core as pc
import shot_subm.src.backend as ss_be
import re
import cui
import os.path as osp
import qtify_maya_window as qtfy
import json
import glob


MEL_PROC_FILE = osp.join(
    osp.dirname(__file__), 'hikUpdateCurrentSourceFromName.mel')
pc.mel.source(MEL_PROC_FILE)


##################################
#  Storing and Loading Mappings  #
##################################


MAPPINGS_DIR = osp.join(osp.dirname(__file__), 'mappings')


class MappingTypes:
    sk = Skeleton = 'sk'
    cr = ControlRig = 'cr'


def getMappingNames(typ=MappingTypes.sk):
    return [osp.basename(_file).split('.')[0]
            for _file in glob.glob(osp.join(MAPPINGS_DIR, '*.%s.json' % typ))]


def writeMapping(data, name, typ=MappingTypes.sk):
    with open(osp.join(MAPPINGS_DIR, '%s.%s.json' % (name, typ)), 'w+') as _fl:
        return json.dump(data, _fl, indent=2)


def loadMapping(name, typ=MappingTypes.sk):
    with open(osp.join(MAPPINGS_DIR, '%s.%s.json' % (name, typ))) as _file:
        return json.read(_file)

#######################
#  Applying mappings  #
#######################


def checkMapping(mapping, namespace):
    found = 0
    for node, num in mapping.items():
        if pc.objExists(namespace+node):
            found += 1
    return found


def getMappingRoot(mapping):
    for node, num in mapping.items():
        if num == 1:
            return node


def mapMocapSkeleton(namespace, hikDefinitionName, mocapSkeletonMappings):
    for node, num in mocapSkeletonMappings.items():
        pc.mel.setCharacterObject(namespace + node, hikDefinitionName, num, 0)


def mapRigSkeleton(namespace, hikDefinitionName, rigSkeletonMappings):
    for node, num in rigSkeletonMappings.items():
        pc.mel.setCharacterObject(namespace + node, hikDefinitionName, num, 0)


def mapRigControls(namespace, rigControlsMappings):
    for node, num in rigControlsMappings.items():
        pc.select(namespace + node)
        pc.mel.hikCustomRigAssignEffector(num)
    pc.select(cl=True)


#######################
#  Utility functions  #
#######################


def getRigControls(namespace, rigControlsMappings):
    return [namespace + x for x in rigControlsMappings.keys()]


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


def createHikDefinition():
    hikDefinitionName = getUniqueName('Character1')
    pc.mel.hikCreateCharacter(hikDefinitionName)
    pc.mel.hikUpdateCharacterList()  # update the character list
    pc.mel.hikSelectDefinitionTab()  # select and update appropriate tab
    return hikDefinitionName


###############################
#  Main Application Function  #
###############################


def applyMocapToRig(
        mocapPath=None, rigNamespace=None,
        sourceName='iPi', targetName='AdvancedSkeleton'):
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
    mocapSkeletonMappings = loadMapping(sourceName, MappingTypes.sk)
    rigSkeletonMappings = loadMapping(targetName, MappingTypes.sk)
    rigControlsMappings = loadMapping(targetName, MappingTypes.cr)
    pc.mel.HIKCharacterControlsTool()
    startFrame = 0
    pc.playbackOptions(minTime=startFrame)
    pc.currentTime(startFrame)

    if rigNamespace is None:
        try:
            control = pc.selected()[0]
        except IndexError:
            pc.warning('No selection found in the scene')
            return
        rigNamespace = control.namespace()

    # bring the mocap in
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

    mocapNamespace = osp.splitext(osp.basename(mocapPath))[0]
    pc.importFile(mocapPath, namespace=mocapNamespace)
    mocapNamespace = ''

    # define HIK Skeleton
    hikDefinitionName = createHikDefinition()
    mapMocapSkeleton(mocapNamespace, hikDefinitionName, mocapSkeletonMappings)
    pc.mel.hikToggleLockDefinition()

    # define HIK skeleton for rig
    rigHikDefinitionName = createHikDefinition()
    mapRigSkeleton(rigNamespace, rigHikDefinitionName, rigSkeletonMappings)
    pc.mel.hikToggleLockDefinition()

    # define HIK custom_rig for rig
    pc.mel.hikCreateCustomRig(rigHikDefinitionName)
    mapRigControls(rigNamespace, rigControlsMappings)
    pc.mel.hikUpdateCurrentSourceFromName(hikDefinitionName)
    pc.select(getRigControls(rigNamespace), rigControlsMappings)

    # To stop maya 2016 from hanging on bake call this in MEL instead
    if pc.about(v=True) >= 2018:
        # TODO: enable following code for maya 2018 and change the code in
        # launch.mel
        animCurves = pc.listConnections("Hip", d=0, s=1, scn=0)
        frames = pc.keyframe(animCurves[0], q=1)
        endFrame = frames[-1]
        pc.playbackOptions(maxTime=endFrame)

        pc.mel.eval((
                'bakeResults -simulation true -t "%s:%s" -sampleBy 1'
                '-disableImplicitControl true -preserveOutsideKeys true'
                '-sparseAnimCurveBake false'
                '-removeBakedAttributeFromLayer false'
                '-removeBakedAnimFromLayer false -bakeOnOverrideLayer false'
                '-minimizeRotation true -controlPoints false -shape true `ls'
                '-sl`;') % (startFrame, endFrame))

        pc.mel.hikDeleteCustomRig(pc.mel.hikGetCurrentCharacter())
        pc.mel.hikDeleteDefinition()
        pc.mel.hikSelectDefinitionTab()
        pc.mel.hikDeleteDefinition()
        pc.delete(getMappingRoot(mocapSkeletonMappings))
