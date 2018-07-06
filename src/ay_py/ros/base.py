#! /usr/bin/env python
#ROS basic tools.
import rospy
import actionlib as al
import geometry_msgs.msg
import trajectory_msgs.msg
import dynamic_reconfigure.client

from ..core.util import *

'''Exception class for ROS operation (e.g. FK, IK).
    ROSError.Kind: 'fk','ik',etc. '''
class ROSError(Exception):
  def __init__(self, kind, msg):
    self.Kind= kind
    self.Msg= msg
  def __str__(self):
    return 'ROSError({kind},{msg})'.format(kind=repr(self.Kind), msg=repr(self.Msg))
  def __repr__(self):
    return 'ROSError({kind},{msg})'.format(kind=repr(self.Kind), msg=repr(self.Msg))

'''Block the execution of action client.
  act_client: action client that is executing an action.
  blocking: False: not block, True: wait until action ends, 'time': wait until duration.
  duration: duration in seconds.
  accuracy: accuracy to check duration.
'''
def BlockAction(act_client, blocking, duration, accuracy=0.02):
  if blocking==False:  return
  if blocking=='time':
    end_time= rospy.Time.now() + rospy.Duration(duration)
    dt= duration*accuracy
    while rospy.Time.now() < end_time:
      time.sleep(dt)
    return
  if blocking==True:
    act_client.wait_for_result()
    return
  raise Exception('BlockAction: invalid blocking type: %r'%blocking)


def SetupServiceProxy(name, srv_type, persistent=False, time_out=None):
  print 'Waiting for %s... (t/o: %r)' % (name, time_out)
  try:
    rospy.wait_for_service(name, time_out)
  except rospy.exceptions.ROSException as e:
    print 'Failed to connect the service %s' % name
    print '  Error:',str(e)
    return None
  srvp= rospy.ServiceProxy(name, srv_type, persistent=persistent)
  return srvp


'''Setup an instance of SimpleActionClient.
  e.g.
    SimpleActionClient(name, act_type, time_out=5.0, num_wait=None)
      Waiting for [name]... (up to 5.0s)
      Waiting for [name]... (up to 5.0s)
      (until connection is established)
    SimpleActionClient(name, act_type, time_out=5.0)
      Waiting for [name]... (up to 5.0s)
      (return None if connection is not established)
'''
def SetupSimpleActionClient(name, act_type, time_out=None, num_wait=1):
  actc= al.SimpleActionClient(name, act_type)
  if time_out is None:  time_out= rospy.Duration()
  elif not isinstance(time_out, rospy.Duration):  time_out= rospy.Duration(time_out)
  while num_wait is None or num_wait>0:
    print 'Waiting for %s... (t/o: %r, #: %r)' % (name, time_out.to_sec(), num_wait)
    if actc.wait_for_server(time_out):
      return actc
    num_wait-= 1
  print 'Failed to connect the action service %s' % name


def SetupDynamicReconfigureClient(name, time_out=None):
  print 'Waiting for %s... (t/o: %r)' % (name, time_out)
  try:
    client= dynamic_reconfigure.client.Client(name, timeout=time_out)
    return client
  except rospy.exceptions.ROSException as e:
    print 'Failed to connect the dynamic_reconfigure.client %s' % name
    print '  Error:',str(e)
    return None


#Convert p to geometry_msgs/Point
def PToGPoint(p):
  point= geometry_msgs.msg.Point()
  point.x= p[0]
  point.y= p[1]
  point.z= p[2]
  return point

#Convert x to geometry_msgs/Pose
def XToGPose(x):
  pose= geometry_msgs.msg.Pose()
  pose.position.x= x[0]
  pose.position.y= x[1]
  pose.position.z= x[2]
  pose.orientation.x= x[3]
  pose.orientation.y= x[4]
  pose.orientation.z= x[5]
  pose.orientation.w= x[6]
  return pose

#Convert geometry_msgs/Pose to x
def GPoseToX(pose):
  x= [0]*7
  x[0]= pose.position.x
  x[1]= pose.position.y
  x[2]= pose.position.z
  x[3]= pose.orientation.x
  x[4]= pose.orientation.y
  x[5]= pose.orientation.z
  x[6]= pose.orientation.w
  return x


'''Support function to generate trajectory_msgs/JointTrajectoryPoint.
    q: Joint positions, t: Time from start, dq: Joint velocities.'''
def ROSGetJTP(q,t,dq=None):
  jp= trajectory_msgs.msg.JointTrajectoryPoint()
  jp.positions= q
  jp.time_from_start= rospy.Duration(t)
  if dq is not None:  jp.velocities= dq
  return jp

'''Get trajectory_msgs/JointTrajectory from a joint angle trajectory.
  joint_names: joint names.
  q_traj: joint angle trajectory [q0,...,qD]*N.
  t_traj: corresponding times in seconds from start [t1,t2,...,tN].
  dq_traj: corresponding velocity trajectory [dq0,...,dqD]*N. '''
def ToROSTrajectory(joint_names, q_traj, t_traj, dq_traj=None):
  assert(len(q_traj)==len(t_traj))
  if dq_traj is not None:  (len(dq_traj)==len(t_traj))
  traj= trajectory_msgs.msg.JointTrajectory()
  traj.joint_names= joint_names
  if dq_traj is not None:
    traj.points= [ROSGetJTP(q,t,dq) for q,t,dq in zip(q_traj, t_traj, dq_traj)]
  else:
    traj.points= [ROSGetJTP(q,t) for q,t in zip(q_traj, t_traj)]
  traj.header.stamp= rospy.Time.now()
  return traj


'''Basic ROS utility class.'''
class TROSUtil(object):
  def __init__(self):
    self._is_initialized= False

    #Container for Publishers
    self.pub= TContainer(debug=True)
    #Container for Subscribers
    self.sub= TContainer(debug=True)
    #Container for Service proxies
    self.srvp= TContainer(debug=True)
    #Container for SimpleActionClient
    self.actc= TContainer(debug=True)
    #Container for dynamic reconfigure client
    self.dynconfig= TContainer(debug=True)

  def __del__(self):
    self.Cleanup()

  def Init(self):
    self._is_initialized= False
    '''Example:
    res= []
    ra= lambda r: res.append(r)

    ra(self.AddPub(...))
    ra(self.AddPub(...))
    ra(self.AddSrvP(...))

    if False not in res:  self._is_initialized= True
    return self._is_initialized
    '''

  def Cleanup(self):
    #NOTE: cleaning-up order is important. consider dependency

    for k in self.sub.keys():
      print 'Stop subscribing %r...' % k,
      self.sub[k].unregister()
      del self.sub[k]
      print 'ok'

    for k in self.pub.keys():
      print 'Stop publishing %r...' % k,
      self.pub[k].publish()
      self.pub[k].unregister()
      del self.pub[k]
      print 'ok'

    for k in self.srvp.keys():
      print 'Delete service proxy %r...' % k,
      del self.srvp[k]
      print 'ok'

    for k in self.actc.keys():
      print 'Delete action client %r...' % k,
      del self.actc[k]
      print 'ok'

    for k in self.dynconfig.keys():
      print 'Delete dynamic reconfigure client %r...' % k,
      del self.dynconfig[k]
      print 'ok'

  @property
  def IsInitialized(self):
    return self._is_initialized

  def AddSub(self, name, port_name, port_type, call_back, callback_args=None, queue_size=None, buff_size=65536, tcp_nodelay=False):
    if name not in self.sub:
      self.sub[name]= rospy.Subscriber(port_name, port_type, call_back, callback_args, queue_size, buff_size, tcp_nodelay)
    return True

  def AddPub(self, name, port_name, port_type, subscriber_listener=None, tcp_nodelay=False, latch=False, headers=None, queue_size=10):
    if name not in self.pub:
      self.pub[name]= rospy.Publisher(port_name, port_type, subscriber_listener, tcp_nodelay, latch, headers, queue_size)
    return True

  def AddSrvP(self, name, port_name, port_type, persistent=False, time_out=None):
    if name not in self.srvp:
      srvp= SetupServiceProxy(port_name, port_type, persistent, time_out)
      if srvp is None:  return False
      else:  self.srvp[name]= srvp
    return True

  def AddActC(self, name, port_name, port_type, time_out=None, num_wait=1):
    if name not in self.actc:
      actc= SetupSimpleActionClient(port_name, port_type, time_out, num_wait)
      if actc is None:  return False
      else:  self.actc[name]= actc
    return True

  def AddDynConfig(self, name, node_name, time_out=None):
    if name not in self.dynconfig:
      client= SetupDynamicReconfigureClient(node_name, time_out=time_out)
      if client is None:  return False
      else:  self.dynconfig[name]= client
    return True

  def DelSub(self, name):
    if name in self.sub:
      self.sub[name].unregister()
      del self.sub[name]

  def DelPub(self, name):
    if name in self.pub:
      self.pub[name].publish()
      self.pub[name].unregister()
      del self.pub[name]

  def DelSrvP(self, name):
    if name in self.srvp:
      del self.srvp[name]

  def DelActC(self, name):
    if name in self.actc:
      del self.actc[name]

  def DelDynConfig(self, name):
    if name in self.dynconfig:
      del self.dynconfig[name]

