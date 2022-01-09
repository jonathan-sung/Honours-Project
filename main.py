import pybullet as p
import math
import numpy as np
import pybullet_data
import time
import bezier
import abc


class Gait:

    def __init__(self, duration):
        self.duration = duration
        self.legSequences = []
        for j in range(6):
            ls = LegSequence(duration, (j % 2))
            self.legSequences.append(ls)

    def evaluate(self, elapsed_time):
        leg_positions = []
        for ls in self.legSequences:
            leg_positions.append(ls.evaluate((elapsed_time % self.duration) / self.duration))
        return leg_positions


class LegSequence:
    def __init__(self, duration, cheese):
        self.duration = duration
        self.motions = []
        if cheese == 0:
            self.motions.append(
                (0.0, BezierMotion(np.array([[0, 0, 0.0, 0.0], [-0.5, 0.5, 1.5, 0.5], [0.0, 1.0, 0.5, 0.0]]))))
            self.motions.append((0.5, LineMotion([0.0, 0.5, 0.0], [0.0, -0.5, 0.0])))
        else:
            self.motions.append((0.0, LineMotion([0.0, 0.5, 0.0], [0.0, -0.5, 0.0])))
            self.motions.append(
                (0.5, BezierMotion(np.array([[0, 0, 0.0, 0.0], [-0.5, 0.5, 1.5, 0.5], [0.0, 1.0, 0.5, 0.0]]))))

    def evaluate(self, progress):
        # for-loop to loop around every motion to return motion for a given amount of progress
        for j in range(len(self.motions) - 1, -1, -1):
            # print(f'j: {j}')
            motion_start_time = self.motions[j][0]
            next_time = 1
            if j < (len(self.motions) - 1):
                next_time = self.motions[j + 1][0]
            if progress >= motion_start_time:

                # Convert global progress into local-progress of given motion
                local_progress = (progress - motion_start_time) / (next_time - motion_start_time)
                return self.motions[j][1].evaluate(local_progress)

        return [[0.0], [0.0], [0.0]]


class Motion(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def evaluate(self, progress):
        pass


class BezierMotion(Motion):
    def __init__(self, knots):
        self.knots = knots
        self.curve = bezier.Curve(self.knots, degree=3)
        self.velocity_curve = bezier.Curve(np.array([[0.0, 0.5, 0.5, 1.0], [0.0, 0.5, 0.5, 1.0]]), degree=3)

    def evaluate(self, progress):
        # velocity curve: y=a+\frac{b}{\left(sx+1\right)^{7}}
        # progress = 1 + -(1 / math.pow((progress + 1), 7))
        curved_progress = self.velocity_curve.evaluate(progress)
        return self.curve.evaluate(curved_progress[1][0] % 1)


class LineMotion(Motion):
    def __init__(self, startPoint, endPoint):
        self.startPoint = startPoint
        self.endPoint = endPoint
        self.velocity_curve = bezier.Curve(np.array([[0.0, 1.0, 1.0, 1.0], [0.0, 0.0, 0.0, 1.0]]), degree=3)

    # Parametric equation of a straight line given a progression percentage
    def evaluate(self, progress):

        # velocity curve: y=a+\frac{b}{\left(sx+1\right)^{7}}
        # progress = 1 + -(1 / math.pow((progress + 1), 7))

        curved_progress = self.velocity_curve.evaluate(progress)
        x = self.startPoint[0] + (self.endPoint[0] - self.startPoint[0]) * curved_progress[1][0]
        y = self.startPoint[1] + (self.endPoint[1] - self.startPoint[1]) * curved_progress[1][0]
        z = self.startPoint[2] + (self.endPoint[2] - self.startPoint[2]) * curved_progress[1][0]
        return [x, y, z]


def init_debug_parameters():
    for j in list(range(0, 6)):
        control_IDs.append(p.addUserDebugParameter(f"Pelvis {j}", -servoRangeOfMotion / 2, servoRangeOfMotion / 2, 0))
        control_IDs.append(p.addUserDebugParameter(f"Hip {j}", -servoRangeOfMotion / 2, servoRangeOfMotion / 2, 0))
        control_IDs.append(p.addUserDebugParameter(f"Knee {j}", -servoRangeOfMotion / 2, servoRangeOfMotion / 2, 0))


def read_debug_parameters():
    angles = []
    for x in control_IDs:
        angles.append(p.readUserDebugParameter(x))
    return angles


def calculateIK3(feet_positions):
    debug_parameters = np.array([
        p.readUserDebugParameter(xPara),
        p.readUserDebugParameter(yPara),
        p.readUserDebugParameter(zPara)])

    pos_body = np.array(p.getBasePositionAndOrientation(hexapod_ID)[0])
    orn_body = p.getBasePositionAndOrientation(hexapod_ID)[1]

    rest_poses = []
    local_target_pos = []
    translated_pos = []
    target_pos = []

    for j in range(6):
        rest_poses.append(
            pos_body + p.multiplyTransforms([0, 0, 0], orn_body, baseToEndEffectorConstVec[j], [0, 0, 0, 1])[0])
        # if j == 0 or j == 2 or j == 4:
        #     local_target_pos.append(feet_positions[j])
        # else:
        #     local_target_pos.append(debug_parameters)
        local_target_pos.append(feet_positions[j])

        translated_pos.append(p.multiplyTransforms(rest_poses[j], orn_body, local_target_pos[j], [0, 0, 0, 1]))
        target_pos.append(translated_pos[j][0])

    ik = p.calculateInverseKinematics2(
        hexapod_ID,
        ([x for x in range(3, 24, 4)]),
        target_pos,
        solver=p.IK_DLS,
        lowerLimits=ll,
        upperLimits=ul,
        jointRanges=jr,
        restPoses=rest_poses,
        jointDamping=jd
    )
    return ik


def debugDisplay():
    return 0


def setServoStatesManual():
    p.setJointMotorControlArray(
        hexapod_ID,
        ([x for x in list(range(0, 24)) if x not in list(range(3, 24, 4))]),
        p.POSITION_CONTROL,
        targetPositions=read_debug_parameters())


def setServoStatesLegs(feet_positions):
    p.setJointMotorControlArray(
        hexapod_ID,
        ([x for x in list(range(0, 24)) if x not in list(range(3, 24, 4))]),
        p.POSITION_CONTROL,
        targetPositions=calculateIK3(feet_positions),
        forces=([150] * 18)
    )


physicsClient = p.connect(p.GUI)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.setGravity(0, 0, -9.8)
planeId = p.loadURDF("plane.urdf")
hexapod_ID = p.loadURDF("robot.urdf", [0, 0, 1.4], p.getQuaternionFromEuler([0, 0, 0]))

control_IDs = []
servoRangeOfMotion = math.pi * 3 / 4
# init_debug_parameters()

# setup IK parameters
ll = ([-servoRangeOfMotion] * 3) + ([0] * 15)  # lowerLimit
ul = ([servoRangeOfMotion] * 3) + ([0] * 15)  # upperLimit
jr = ([servoRangeOfMotion] * 3) + ([0] * 15)  # jointRange
rp = ([0] * 18)  # restPos
jd = ([5] * 18)  # jointDamping (like a PID controller)

baseToEndEffectorConstVec = []
for i in range(3, 24, 4):
    baseToEndEffectorConstVec.append(
        np.array(p.getLinkState(hexapod_ID, i)[4]) - np.array(p.getBasePositionAndOrientation(hexapod_ID)[0]))

testLegID = 3

xPara = p.addUserDebugParameter("X", -3, 3, 0)
yPara = p.addUserDebugParameter("Y", -3, 3, 0)
zPara = p.addUserDebugParameter("Z", -3, 3, 0)
rotationPara = p.addUserDebugParameter("Rotation", -math.pi, math.pi, 0)

prevPos = []
currentPos = [0, 0, 0, 0, 0, 0]
for i in range(6):
    prevPos.append(p.getLinkState(hexapod_ID, (4 * i) + 3)[0])

lastTime = time.time()

# Gait test
gaitDuration = 3
testGait = Gait(gaitDuration)

while True:
    dt = time.time() - lastTime
    setServoStatesLegs(testGait.evaluate(dt))

    for i in range(6):
        currentPos[i] = p.getLinkState(hexapod_ID, (4 * i) + 3)[0]
        p.addUserDebugLine(prevPos[i], currentPos[i], [0, 0, 0.3], 4, gaitDuration)
        prevPos[i] = currentPos[i]
    p.setRealTimeSimulation(1)
    # p.stepSimulation()
    # time.sleep(1. / 240.)

p.disconnect(physicsClient)
