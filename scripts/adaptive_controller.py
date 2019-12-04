"""
This auxiliary file contains the adaptive controller used in main.py.
"""

import plugins.actuators.CompliantHandEmulator  # TODO: Does this work? Specify this to be imported from other package
import plugins.reflex  # TODO: Does this work? Specify this to be imported from other package
import plugins.soft_hand  # TODO: Does this work? Specify this to be imported from other package
from klampt.math import se3, so3, vectorops
import math as sym
import numpy as np

from geometry_msgs.msg import Pose
from tf import transformations

import global_vars
import move_elements as mv_el

DEBUG = False

int_const_syn = 100
int_const_t = 1
int_const_eul = 1


def integrate_velocities(controller, sim, dt, xform):
    """The make() function returns a 1-argument function that takes a SimRobotController and performs whatever
    processing is needed when it is invoked."""

    syn_curr = controller.getSensedConfig()
    palm_curr = mv_el.get_moving_base_xform(sim.controller(0).model())
    R = palm_curr[0]
    t = palm_curr[1]

    if DEBUG:
        print 'The current palm rotation is ', R
        print 'The current palm translation is ', t
        print 'The simulation dt is ', dt

    # Converting to rpy
    euler = so3.rpy(R)

    # Checking if list empty and returning false
    if not syn_curr:
        return (False, None, None)
    else:
        syn_curr = syn_curr[34]

    if DEBUG or True:
        print 'The adaptive velocity of hand is ', global_vars.hand_command
        print 'The adaptive twist of palm is \n', global_vars.arm_command
        print 'The present position of the hand encoder is ', syn_curr
        print 'The present pose of the palm is \n', palm_curr
        # print 'The present position of the palm is ', t, 'and its orientation is', euler

    # Getting linear and angular velocities
    lin_vel_vec = global_vars.arm_command.linear
    ang_vel_vec = global_vars.arm_command.angular
    lin_vel = [lin_vel_vec.x, lin_vel_vec.y, lin_vel_vec.z]
    # lin_vel = [0.0, 0.0, 0.0]                                 # for debugging rotation vel
    ang_vel = [ang_vel_vec.x, ang_vel_vec.y, ang_vel_vec.z]
    # ang_vel = [0.0, 0.0, 0.2]                                 # for debugging rotation vel
    ang_vel_loc = so3.apply(so3.inv(R), ang_vel)

    # Transform ang vel into rpy vel
    euler_vel = transform_ang_vel(euler, ang_vel_loc)

    # Integrating
    syn_next = syn_curr + global_vars.hand_command * int_const_syn * dt
    t_next = vectorops.madd(t, lin_vel, int_const_t * dt)
    euler_next = vectorops.madd(euler, euler_vel, int_const_eul * dt)

    # Convert back for send xform
    palm_R_next = so3.from_rpy(euler_next)
    palm_t_next = t_next
    palm_next = (palm_R_next, palm_t_next)

    if DEBUG:
        print 'euler is ', euler, ' and is of type ', type(euler)
        print 'euler_vel is ', euler_vel, ' and is of type ', type(euler_vel)
        print 'euler_next is ', euler_next, ' and is of type ', type(euler_next)

        print 't is ', t, ' and is of type ', type(t)
        print 't_next is ', t_next, ' and is of type ', type(t_next)

        print 'R is ', R, ' and is of type ', type(R)
        print 'palm_R_next is ', palm_R_next, ' and is of type ', type(palm_R_next)

        print 'palm_curr is ', palm_curr, ' and is of type ', type(palm_curr)
        print 'palm_next is ', palm_next, ' and is of type ', type(palm_next)

    return (True, syn_next, palm_next)

def transform_ang_vel(euler, ang_vel):
    """ Transforms an omega (ang. vel.) into rpy or ypr parametrization """

    r = euler[0]
    p = euler[1]
    y = euler[2]

    # Transformation matrix (ref. https://davidbrown3.github.io/2017-07-25/EulerAngles/)
    # YPR
    Typr = np.array([[1, sym.tan(p)*sym.sin(r), sym.cos(r)*sym.tan(p)],
                  [0, sym.cos(r), -sym.sin(r)],
                  [0, sym.sin(r)/sym.cos(p), sym.cos(r)/sym.cos(p)]])

    # RPY
    Trpy = np.array([[sym.cos(y)/sym.cos(p), -sym.sin(y)/sym.cos(p), 0],
                  [sym.sin(y), sym.cos(y), 0],
                  [-(sym.cos(y)*sym.sin(p))/sym.cos(p), (sym.sin(p)*sym.sin(y))/sym.cos(p), 1]])


    vec = np.array([ang_vel[0], ang_vel[1], ang_vel[2]])
    vec_transformed = np.matmul(Typr, vec)
    vec_tup = totuple(vec_transformed) # conversion to tuple for xform

    return vec_tup

def totuple(a):
    try:
        return tuple(totuple(i) for i in a)
    except TypeError:
        return a

def make(sim, hand, dt):
    """The make() function returns a 1-argument function that takes a SimRobotController and performs whatever
    processing is needed when it is invoked."""

    is_reflex_col = False
    is_reflex = False
    is_soft_hand = False

    if not isinstance(hand, plugins.actuators.CompliantHandEmulator.CompliantHandEmulator):
        is_reflex_col = True
    else:
        if isinstance(hand, plugins.soft_hand.HandEmulator):
            is_soft_hand = True
        else:
            is_reflex = True

    if not is_soft_hand:
        # get references to the robot's sensors (not properly functioning in Klamp't 0.6.x)
        f1_proximal_tactile_sensors = [sim.controller(0).sensor("f1_proximal_tactile_%d" % (i,)) for i in range(1, 6)]
        f1_distal_tactile_sensors = [sim.controller(0).sensor("f1_distal_tactile_%d" % (i,)) for i in range(1, 6)]
        f2_proximal_tactile_sensors = [sim.controller(0).sensor("f2_proximal_tactile_%d" % (i,)) for i in range(1, 6)]
        f2_distal_tactile_sensors = [sim.controller(0).sensor("f2_distal_tactile_%d" % (i,)) for i in range(1, 6)]
        f3_proximal_tactile_sensors = [sim.controller(0).sensor("f3_proximal_tactile_%d" % (i,)) for i in range(1, 6)]
        f3_distal_tactile_sensors = [sim.controller(0).sensor("f3_distal_tactile_%d" % (i,)) for i in range(1, 6)]
        contact_sensors = f1_proximal_tactile_sensors + f1_distal_tactile_sensors + f2_proximal_tactile_sensors + \
            f2_distal_tactile_sensors + f3_proximal_tactile_sensors + f3_distal_tactile_sensors

    sim.updateWorld()
    xform = mv_el.get_moving_base_xform(sim.controller(0).model())

    def control_func(controller):
        """
        Place your code here... for a more sophisticated controller you could also create a class
        where the control loop goes in the __call__ method.
        """
        if not is_soft_hand:
            # print the contact sensors... you can safely take this out if you don't want to use it
            try:
                f1_contact = [s.getMeasurements()[0] for s in f1_proximal_tactile_sensors] + [s.getMeasurements()[0] for
                                                                                              s in
                                                                                              f1_distal_tactile_sensors]
                f2_contact = [s.getMeasurements()[0] for s in f2_proximal_tactile_sensors] + [s.getMeasurements()[0] for
                                                                                              s in
                                                                                              f2_distal_tactile_sensors]
                f3_contact = [s.getMeasurements()[0] for s in f3_proximal_tactile_sensors] + [s.getMeasurements()[0] for
                                                                                              s in
                                                                                              f3_distal_tactile_sensors]
                if DEBUG:
                    print "Contact sensors"
                    print "  finger 1:", [int(v) for v in f1_contact]
                    print "  finger 2:", [int(v) for v in f2_contact]
                    print "  finger 3:", [int(v) for v in f3_contact]
            except:
                pass

        # Integrating the velocities
        (success, syn_comm, palm_comm) = integrate_velocities(controller, sim, dt, xform)

        # print 'The integration of velocity -> success = ', success

        t_lift = 10.0
        if sim.getTime() < t_lift:
            if is_soft_hand:
                if success:
                    if DEBUG or True:
                        print 'The commanded position of the hand encoder is ', syn_comm
                        print 'The commanded pose of the palm is \n', palm_comm
                    hand.setCommand([syn_comm])
                    mv_el.send_moving_base_xform_PID(controller, palm_comm[0], palm_comm[1])
            else:
                # the controller sends a command to the hand: f1,f2,f3, pre-shape
                hand.setCommand([0.2, 0.2, 0.2, 0])

        lift_traj_duration = 0.5
        if sim.getTime() > t_lift:
            # the controller sends a command to the base after 1 s to lift the object
            t_traj = min(1, max(0, (sim.getTime() - t_lift) / lift_traj_duration))
            desired = se3.mul((so3.identity(), [0, 0, 0.10 * t_traj]), xform)
            mv_el.send_moving_base_xform_PID(controller, desired[0], desired[1])
        # need to manually call the hand emulator
        hand.process({}, dt)

        if DEBUG:
            print "The simulation time is " + str(sim.getTime())

    return control_func
