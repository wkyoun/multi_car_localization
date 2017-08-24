#!/usr/bin/env python

import math
import rospy
from std_msgs.msg import Header
from sensor_msgs.msg import Range
from geometry_msgs.msg import PoseStamped
from multi_car_msgs.msg import CarMeasurement
from multi_car_msgs.msg import UWBRange
from multi_car_msgs.msg import CarControl
from sensor_msgs.msg import NavSatFix
from nav_msgs.msg import Odometry

import dict_to_graph
import networkx as nx

class Measurements(object):

	def __init__(self):

		self.rate = rospy.Rate(rospy.get_param("~frequency", 20))
		self.Ncars = rospy.get_param("~num_cars", 3)
		self.frame_id = rospy.get_param("~car_frame_id", "car0")
		self.id_dict = rospy.get_param("/id_dict", None)
		self.connections = rospy.get_param("/connections", None)
		self.own_connections = self.connections[self.frame_id[-1]]
		self.Nconn = len(self.own_connections)

		self.full_graph = dict_to_graph.convert(self.connections)
		self.graph = dict_to_graph.prune(self.full_graph, int(self.frame_id[-1]))

		self.meas = CarMeasurement()
		self.meas.header = Header()
		self.meas.header.frame_id = self.frame_id
		self.meas.car_id = int(self.frame_id[-1])

		self.uwb_ranges = self.init_uwb()
		self.gps = [None]*self.Nconn
		self.control = [None] * self.Nconn

		self.uwb_sub = rospy.Subscriber("/ranges", UWBRange, self.range_cb, queue_size=1)
		#self.gps_sub = rospy.Subscriber("gps", NavSatFix, self.gps_cb, queue_size=1)
		self.gps_sub = []
		for i, ID in enumerate(self.own_connections):
			self.gps_sub.append(
				rospy.Subscriber(
				"odom" + str(ID), Odometry, self.gps_cb, (i,), queue_size=1))
		#self.initial_gps = None

		self.control_sub = rospy.Subscriber("/controls", CarControl, self.control_cb, queue_size=1)

		self.meas_pub = rospy.Publisher(
			"measurements", CarMeasurement, queue_size=1)

		#self.br = tf.TransformBroadcaster()

	def init_uwb(self):
		uwbs = {}
		for j in self.own_connections:
			for k in self.own_connections:
				if (j, k) in self.graph.edges():
					null_uwb = UWBRange()
					null_uwb.distance = -1
					null_uwb.to_id = j
					null_uwb.from_id = k
					uwbs[(j, k)] = null_uwb
		return uwbs

	def control_cb(self, control):
		car_id = self.id_dict[str(control.car_id)]
		if car_id in self.own_connections:
			control.car_id = car_id
			self.control[self.own_connections.index(car_id)] = control

	def range_cb(self, uwb):
		uwb.to_id = self.id_dict[str(uwb.to_id)]
		uwb.from_id = self.id_dict[str(uwb.from_id)]
		if (uwb.to_id, uwb.from_id) in self.graph.edges():
			self.uwb_ranges[(uwb.to_id, uwb.from_id)] = uwb

	def gps_cb(self, gps, args):
		num = args[0]
		self.gps[num] = gps

	def publish_measurements(self):
		gps_good = None not in self.gps
		control_good = None not in self.control

		uwb_good = True
		for i in self.own_connections:
			for j in self.own_connections:
				if i < j and (i, j) in self.graph.edges():
					if self.uwb_ranges[(i, j)].distance == -1 and self.uwb_ranges[(j, i)].distance == -1:
						uwb_good = False

		if gps_good and uwb_good and control_good:
			num_uwb = 0
			for uwb in self.uwb_ranges:
				if self.uwb_ranges[uwb].distance != -1:
					num_uwb += 1
			print "%s: NUM UWB: %d" % (self.frame_id, num_uwb)
			self.meas.header.stamp = rospy.Time.now()

			for ID in self.uwb_ranges:
				self.meas.range.append(self.uwb_ranges[ID])
			self.meas.gps = self.gps
			self.meas.control = self.control

			self.meas_pub.publish(self.meas)

			self.meas.range = []
			self.gps = [None]*self.Nconn
			self.uwb_ranges = self.init_uwb()
			self.control = [None]*self.Nconn
		else:
			num_uwb = 0
			for uwb in self.uwb_ranges:
				if self.uwb_ranges[uwb].distance != -1:
					num_uwb += 1
			num_gps = 0
			for gps in self.gps:
				if gps is not None:
					num_gps += 1
			print "NUM UWB: %d" % (num_uwb)
			print "NUM GPS: %d" % (num_gps)
			num_control = 0
			for cont in self.control:
				if cont is not None:
					num_control += 1
			print "NUM CON: %d" % (num_control)


	def run(self):
		while not rospy.is_shutdown():
			self.publish_measurements()
			self.rate.sleep()

if __name__ == "__main__":
	rospy.init_node("measurements", anonymous=False)
	measurements = Measurements()
	measurements.run()