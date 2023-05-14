#!/usr/bin/env python3

from typing import Optional, Any
import cv2
import sys
import rospy
import numpy as np
import math
import os
from sensor_msgs.msg import CompressedImage, Image
from duckietown.dtros import DTROS, DTParam, NodeType, TopicType
from cv_bridge import CvBridge
import apriltag
from duckietown_msgs.msg import Twist2DStamped, BoolStamped, FSMState


class BotCamera(DTROS):
    def __init__(self, node_name):
        super().__init__(node_name, node_type=NodeType.PERCEPTION)
        self.bridge = CvBridge()

        # subscribers
        self.sub_img = rospy.Subscriber("~image_in", CompressedImage, self.cb_image, queue_size=1, buff_size="10MB")
        self.sub_start_parking = rospy.Subscriber("~parking_start", BoolStamped, self.parking_start, queue_size=1)
        self.sub_fsm_mode = rospy.Subscriber("fsm_node/mode", FSMState, self.cbMode, queue_size=1)
        self.sub_connection_status = rospy.Subscriber("~connection_status", BoolStamped, self.get_connection_status,
                                                      queue_size=1)

        # publishers
        self.pub = rospy.Publisher("~car_cmd", Twist2DStamped, queue_size=1)
        self.pub_state = rospy.Publisher("fsm_node/mode", FSMState, queue_size=1, latch=True)

        # logic helper
        self.mode = None  # change state for bot
        self.bool_start = False  # false if press button "J" on joystick and true if press button "F" on joystick
        self.cant_find_counter = 0  # for count how many times we can's tag
        self.is_connected = False  # for checking connection status
        self.deltaLR = 0

    def parking_start(self, msg):
        self.bool_start = msg.data
        new_state = FSMState()
        if msg.data:
            new_state.state = "PARKING"
        else:
            new_state.state = "NORMAL_JOYSTICK_CONTROL"
        self.pub_state.publish(new_state)  # set a new state

    def cbMode(self, fsm_state_msg):
        self.mode = fsm_state_msg.state  # String of the current FSM state

    def cb_image(self, msg):
        img = self.bridge.compressed_imgmsg_to_cv2(msg)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self.bool_start and not self.is_connected:
            self.marker_detecting(img)

    def get_connection_status(self, msg):
        self.is_connected = msg.data
        if self.is_connected:
            self.message_print(0, 0, "Connected ura! ura! ura!")
            new_state = FSMState()
            new_state.state = "NORMAL_JOYSTICK_CONTROL"
            self.pub_state.publish(new_state)
        else:
            rospy.loginfo("NOT_connected")

    def marker_detecting(self, in_image):
        options = apriltag.DetectorOptions(families="tag36h11")
        detector = apriltag.Detector(options)
        gray_img = cv2.cvtColor(in_image, cv2.COLOR_RGB2GRAY)
        x_center_image = in_image.shape[1] // 2
        tags = detector.detect(gray_img)
        if len(tags) == 0:
            self.cant_find()
            return
        for tag in tags:
            if tag.tag_id == 20:  # there gotta be special value
                self.message_print(0, 0, "Find marker, stop")

                (topLeft, topRight, bottomRight, bottomLeft) = tag.corners

                topRight = (int(topRight[0]), int(topRight[1]))
                bottomRight = (int(bottomRight[0]), int(bottomRight[1]))
                bottomLeft = (int(bottomLeft[0]), int(bottomLeft[1]))
                topLeft = (int(topLeft[0]), int(topLeft[1]))

                length_left = math.sqrt((bottomLeft[1] - topLeft[1]) ** 2 + (bottomLeft[0] - topLeft[0]) ** 2)
                length_right = math.sqrt((bottomRight[1] - topRight[1]) ** 2 + (bottomRight[0] - topRight[0]) ** 2)
                rospy.loginfo(f"length left and right side marker: left {length_left} right {length_right}\n")
                self.deltaLR = length_left - length_right

                self.cant_find_counter = 0
                coordinates = tuple(map(int, tag.center))
                x_center_marker = coordinates[0]
                rospy.loginfo(f"center image {x_center_image} \t center marker {x_center_marker} \n")
                if x_center_image > x_center_marker:
                    self.message_print(0.1, 1, "\t\tturning left")
                elif x_center_image <= x_center_marker:
                    self.message_print(0.1, -1, "\t\tturning right")
        return

    def cant_find(self):
        if self.cant_find_counter == 0:
            self.cant_find_counter += 1
            self.message_print(0.5, 0, "Try to connect")
            rospy.sleep(0.2)
            self.message_print(0, 0, "Checking charging sleeping time")
            rospy.sleep(0.2)
        elif self.cant_find_counter == 1:
            self.cant_find_counter += 1
            # self.message_print(-0.5, 0, "\tBack riding ahead")
            if self.deltaLR < 0:
                self.message_print(-1, -0.5, "ahead and left")
            else:
                self.message_print(-1, 0.5, "ahead and right")
            rospy.sleep(1)
            self.message_print(0, 0, "Look around time")
            rospy.sleep(0.2)
        else:
            self.message_print(0, 0.5, f"\tTurning №{self.cant_find_counter} and try to find marker")
            self.cant_find_counter += 1

    def message_print(self, v, omega, message):
        msg = Twist2DStamped()
        msg.v = v
        msg.omega = omega
        rospy.loginfo(message)
        self.pub.publish(msg)


if __name__ == "__main__":
    node_cmd = BotCamera("bot_camera")
    rospy.spin()
