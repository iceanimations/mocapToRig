'''
Created on Mar 19, 2018

@author: qurban.ali
'''
import pymel.core as pc
import re
import cui
import os.path as osp
import qtify_maya_window as qtfy

melProcedure = '''
global proc hikUpdateCurrentSourceFromName(string $source)
//
// Description:
//        Updates the source of the character when the drop-down
//        list is changed
//
{
    waitCursor -state true;

    // string $source = `optionMenuGrp -q -v hikSourceList`;

    // if there`s a white space before, we must remove it
    $source = stringRemovePrefix( $source, " " );

    hikSetCurrentSource( $source );

    int $isRemote = ( endsWith( $source, "(remote)" ) ) ? true : false;

    string $character = hikGetCurrentCharacter();

    // Disable the character. This disconnects the retargeter
    hikEnableCharacter( $character, 2 );

    // Next, reconnect to the new source...
    if ( hikIsNoneCharacter( $source ) ) {
        // If definition is locked, disable the character
        // (which is done above). So do nothing here.
        // If definition is not locked, what should happen??
        if( hikIsDefinitionLocked($character) ) {
            // do nothing
        }
        else {

        }
    }
    else {
        string $labelControlRig = (uiRes("m_hikGlobalUtils.kControlRig"));
        string $labelStance= (uiRes("m_hikGlobalUtils.kStance"));
        if( $source == $labelControlRig ) {
            // if we don't already have a control rig, create one.
            // hikCreateControlRig will try to do the auto-locking
            // of the definition.
            //
            int $hasControlRig = hikHasControlRig($character);
            if( $hasControlRig ) {
                hikSetRigInput($character);
                hikSetLiveState( $character, 1 );
                hikSelectControlRigTab();
            }
            else {
                // Note: hikCreateControlRig will select the
                // appropriate tab. If the definition was not
                // valid, creation will fail and we'll select
                // the definition tab...
                //
                hikCreateControlRig();
            }
        }
        else {
            // If the definition is not locked yet, try to lock it
            if( !hikCheckDefinitionLocked($character) ) {
                hikSelectDefinitionTab();    // select definition tab
                waitCursor -state false;
                return;
            }

            if( $source == $labelStance) {
                hikSetStanceInput($character);
            }
            else {
                hikEnableCharacter( $character, 1 );

                if ( $isRemote )
                    hikSetLiveCharacterInput( $character );
                else
                    hikSetCharacterInput( $character, $source );

                if ( hikHasCustomRig( $character ) )
                    hikSelectCustomRigTab;
                else
                    hikSelectControlRigTab;
            }
        }
    }

    hikUpdateLiveConnectionUI;
    waitCursor -state false;
}

'''

pc.mel.eval(melProcedure)

mocapSkeletonMappings = {
    'Hip': 1,
    'LThigh': 2,
    'LShin': 3,
    'LFoot': 4,
    'RThigh': 5,
    'RShin': 6,
    'RFoot': 7,
    'LowerSpine': 8,
    'LShoulder': 9,
    'LForearm': 10,
    'LHand': 11,
    'RShoulder': 12,
    'RForearm': 13,
    'RHand': 14,
    'Head': 15,
    'LClavicle': 18,
    'RClavicle': 19,
    'Neck': 20,
    'MiddleSpine': 23
}


def mapMocapSkeleton(namespace, hikDefinitionName):
    for node, num in mocapSkeletonMappings.items():
        pc.mel.setCharacterObject(namespace + node, hikDefinitionName, num, 0)


rigSkeletonMappings = {
    'Root_M': 1,
    'Hip_L': 2,
    'Knee_L': 3,
    'Ankle_L': 4,
    'Hip_R': 5,
    'Knee_R': 6,
    'Ankle_R': 7,
    'Spine2_M': 8,
    'Shoulder_L': 9,
    'Elbow_L': 10,
    'Wrist_L': 11,
    'Shoulder_R': 12,
    'Elbow_R': 13,
    'Wrist_R': 14,
    'Head_M': 15,
    'Scapula_L': 18,
    'Scapula_R': 19,
    'Neck_M': 20,
    'Spine1_M': 23
}


def mapRigSkeleton(namespace, hikDefinitionName):
    for node, num in rigSkeletonMappings.items():
        pc.mel.setCharacterObject(namespace + node, hikDefinitionName, num, 0)


rigControlsMappings = {
    'RootX_M': 1,
    'IKLeg_L': 4,
    'IKLeg_R': 7,
    'FKSpine1_M': 8,
    'FKShoulder_L': 9,
    'FKElbow_L': 10,
    'FKWrist_L': 11,
    'FKShoulder_R': 12,
    'FKElbow_R': 13,
    'FKWrist_R': 14,
    'FKHead_M': 15,
    'FKScapula_L': 18,
    'FKScapula_R': 19,
    'FKNeck_M': 20,
    'FKSpine2_M': 23
}


def mapRigControls(namespace):
    for node, num in rigControlsMappings.items():
        pc.select(namespace + node)
        pc.mel.hikCustomRigAssignEffector(num)
    pc.select(cl=True)


def getRigControls(namespace):
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
    mapMocapSkeleton(mocapNamespace, hikDefinitionName)
    pc.mel.hikToggleLockDefinition()

    rigHikDefinitionName = createHikDefinition()
    mapRigSkeleton(rigNamespace, rigHikDefinitionName)
    pc.mel.hikToggleLockDefinition()

    pc.mel.hikCreateCustomRig(rigHikDefinitionName)
    mapRigControls(rigNamespace)
    pc.mel.hikUpdateCurrentSourceFromName(hikDefinitionName)
    pc.select(getRigControls(rigNamespace))


#     TODO: enable following code for maya 2018 and change the code in launch.mel
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
